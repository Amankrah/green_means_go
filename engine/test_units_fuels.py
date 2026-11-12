#!/usr/bin/env python3
"""Unit conversion (engine/units.py), fuel combustion (engine/fuels.py) and the unit
enforcement at the solver hand-off in engine/orchestrator.py."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

import units
import fuels


def test_same_family_conversions():
    assert units.convert(1, "kWh", "MJ") == pytest.approx(3.6)
    assert units.convert(2, "t", "kg") == pytest.approx(2000)
    assert units.convert(500, "l", "m3") == pytest.approx(0.5)
    assert units.convert(10, "tkm", "t*km") == pytest.approx(10)


def test_energy_to_mass_uses_ipcc_ncv():
    # kerosene: IPCC 2006 Vol 2 Table 1.2 NCV 43.8 MJ/kg
    assert units.convert(438, "MJ", "kg", "kerosene") == pytest.approx(10.0)
    # diesel litres -> kg via density 0.837
    assert units.convert(100, "L", "kg", "diesel") == pytest.approx(83.7)
    # LPG litres -> MJ via density then NCV
    assert units.convert(1, "l", "MJ", "lpg") == pytest.approx(0.533 * 47.3)


def test_mismatch_raises_never_passes_through():
    with pytest.raises(units.UnitMismatchError):
        units.convert(5, "kg", "MJ")              # no substance
    with pytest.raises(units.UnitMismatchError):
        units.convert(5, "kg", "Item(s)", "diesel")  # count vs mass
    with pytest.raises(units.UnitMismatchError):
        units.to_ref_unit({"name": "mystery", "amount": 3, "unit": "kg"}, "ha")


def test_to_ref_unit_kerosene_mj_against_per_kg_dataset():
    inp = {"name": "kerosene, burned in agricultural machinery", "amount": 4380.0, "unit": "MJ"}
    amount, note = units.to_ref_unit(inp, "kg")
    assert amount == pytest.approx(100.0)
    assert "converted" in note
    same, none_note = units.to_ref_unit({"name": "x", "amount": 2, "unit": "kg"}, "kg")
    assert same == 2 and none_note is None


def test_lpg_combustion_factors():
    inputs = [{"name": "LPG", "amount": 10.0, "unit": "kg", "kind": "fuel"}]
    out, flows, notes = fuels.expand_fuel_inputs(inputs)
    assert out[0]["match_as"] == "market for liquefied petroleum gas"
    assert out[0]["unit"] == "kg" and out[0]["amount"] == pytest.approx(10.0)
    tj = 10.0 * 47.3 / 1e6
    by = {f["substance"]: f["quantity"] for f in flows}
    assert by["CO2"] == pytest.approx(tj * 63100)      # fossil
    assert by["CH4"] == pytest.approx(tj * 5)
    assert by["N2O"] == pytest.approx(tj * 0.1)


def test_biomass_co2_is_biogenic_ch4_n2o_counted():
    out, flows, _ = fuels.expand_fuel_inputs(
        [{"name": "firewood", "amount": 100.0, "unit": "kg", "kind": "fuel"},
         {"name": "charcoal", "amount": 295.0, "unit": "MJ", "kind": "fuel"}])
    subs = [f["substance"] for f in flows]
    assert "CO2" not in subs and "CH4" not in subs
    assert "CO2_bio" not in subs and subs.count("CH4_bio") == 2   # biogenic CO2 not emitted
    wood_ch4 = [f for f in flows if f["origin"] == "combustion:firewood" and f["substance"] == "CH4_bio"][0]
    assert wood_ch4["quantity"] == pytest.approx(100 * 15.6 / 1e6 * 300)
    # firewood production is per kg dry mass (15% moisture assumption); charcoal MJ -> kg
    assert out[0]["amount"] == pytest.approx(85.0)
    assert out[1]["amount"] == pytest.approx(10.0)


def test_kerosene_mj_redirected_to_production_kg():
    out, flows, _ = fuels.expand_fuel_inputs(
        [{"name": "kerosene, burned in agricultural machinery", "amount": 438.0, "unit": "MJ",
          "kind": "fuel"}])
    assert out[0]["match_as"] == "market for kerosene"
    assert out[0]["amount"] == pytest.approx(10.0) and out[0]["unit"] == "kg"
    assert {f["substance"] for f in flows} == {"CO2", "CH4", "N2O"}


def test_diesel_and_non_fuel_inputs_pass_through():
    inp = [{"name": "diesel, burned in agricultural machinery", "amount": 50, "unit": "MJ", "kind": "fuel"},
           {"name": "charcoal", "amount": 5, "unit": "kg", "kind": "raw_material"}]
    out, flows, _ = fuels.expand_fuel_inputs(inp)
    assert out == inp and flows == []


def test_unconvertible_fuel_excluded_with_warning():
    out, flows, notes = fuels.expand_fuel_inputs(
        [{"name": "firewood", "amount": 3, "unit": "bundle", "kind": "fuel"}])
    assert out == [] and flows == []
    assert notes and notes[0].startswith("validation warning:")


# ---- orchestrator hand-off: convert or exclude, never pass through --------------------

class _StubQ:
    def __init__(self, ref_unit):
        self.ref_unit = ref_unit
        self.solved = []

    def get_process(self, uid):
        return {"ref_unit": self.ref_unit}

    def cradle_to_gate(self, uid, amount):
        self.solved.append(amount)
        return SimpleNamespace(elementary_flows={})

    def characterize_flows(self, flows, method):
        return {}

    def source_label(self, uid):
        return "stub"


def _stub_engine(ref_unit):
    import orchestrator
    eng = object.__new__(orchestrator.FarmLCA)
    eng.region = SimpleNamespace(name="Ghana", code="GH", grid_ef_kgco2_per_kwh=None)
    eng.method = "m"
    eng.q = _StubQ(ref_unit)
    eng.fmap = SimpleNamespace(resolve=lambda s: None)
    eng._match_input = lambda text, expand=False, context=None: {"uid": "u", "name": "market for kerosene",
                                                   "score": 0.9, "location": "RoW"}
    return eng


def test_orchestrator_converts_amount_to_ref_unit():
    eng = _stub_engine("kg")
    res = eng.assess([], [{"name": "kerosene, burned in agricultural machinery",
                           "amount": 438.0, "unit": "MJ", "kind": "fuel"}])
    assert eng.q.solved == [pytest.approx(10.0)]
    assert res.input_matches[0]["solved_amount"] == pytest.approx(10.0)


def test_orchestrator_excludes_unconvertible_input():
    eng = _stub_engine("Item(s)")
    res = eng.assess([], [{"name": "mystery", "amount": 5.0, "unit": "kg"}])
    assert eng.q.solved == []
    assert res.input_matches[0]["excluded"] == "unit mismatch"
    assert any(n.startswith("validation warning: unit mismatch") for n in res.notes)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
