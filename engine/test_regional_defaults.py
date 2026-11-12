#!/usr/bin/env python3
"""Per-region activity defaults and grid calibration factors (generic loading, Nigeria
tables, no silent Ghana inheritance)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

import activity_defaults as ad        # noqa: E402
import grid_calibration as gc         # noqa: E402
from regions import get_region        # noqa: E402

REF = ROOT / "recommend" / "reference"


def _farm(country, production_system="Rainfed", equipment=None):
    return {"country": country, "foods": [{"name": "Maize", "quantity_kg": 3000, "area_allocated": 2.0,
                                            "production_system": production_system}],
            "management_practices": {"water_management": {"irrigation_system": "None (Rainfed)"}},
            "equipment_energy": {"equipment": equipment or [], "energy_sources": [], "fuel_consumption": []}}


def test_nigeria_table_mirrors_ghana_structure_with_sources():
    gh = json.loads((REF / "ghana_farm_activity_defaults.json").read_text(encoding="utf-8"))
    ng = json.loads((REF / "nigeria_farm_activity_defaults.json").read_text(encoding="utf-8"))
    assert [r["id"] for r in ng["rows"]] == [r["id"] for r in gh["rows"]]
    for r in ng["rows"]:
        p = r["provenance"]
        assert p.get("span") and p.get("yield_source"), r["id"]
        assert "inherited_from_ghana" in p
        assert r["yield_guides_kg_per_ha"]["maize"] == 1939      # FAOSTAT 2023 Nigeria
    text = (REF / "nigeria_farm_activity_defaults.json").read_text(encoding="utf-8")
    assert "\u2014" not in text


def test_nigeria_resolves_to_nigeria_table():
    a = _farm("Nigeria", equipment=[{"equipment_type": "Tractor", "hours_per_year": 50}])
    r = ad.resolve_energy_defaults(a)
    assert r["region"] == "NG" and r["table_id"] == "activity.defaults.farm.ng"
    assert r["row_id"] == "rainfed_partial" and r["diesel_l_per_ha"] == 24
    inputs, notes = [], []
    ad.apply_activity_defaults(a, inputs, notes)
    assert inputs and inputs[0]["estimated"] and abs(inputs[0]["amount"] - 24 * 2 * 38.7) < 1e-6


def test_ghana_unchanged():
    r = ad.resolve_energy_defaults(_farm("Ghana"))
    assert r["region"] == "GH" and r["row_id"] == "rainfed_manual" and r["table_file"] == "ghana_farm_activity_defaults.json"


def test_region_without_table_gets_no_defaults_and_a_flag():
    a = _farm("Canada", equipment=[{"equipment_type": "Tractor", "hours_per_year": 50}])
    assert ad.resolve_energy_defaults(a) is None
    inputs, notes = [], []
    ad.apply_activity_defaults(a, inputs, notes)
    assert inputs == []
    assert any("activity defaults unavailable for Canada" in n for n in notes)


def test_region_field_activity_defaults_file_wins():
    fake = SimpleNamespace(code="XX", name="Nowhere", activity_defaults_file="nigeria_farm_activity_defaults.json")
    assert ad.table_path_for(fake).name == "nigeria_farm_activity_defaults.json"
    assert ad.table_path_for(SimpleNamespace(code="XX", name="Nowhere")) is None


def test_inherited_values_are_flagged():
    a = _farm("Nigeria", production_system="Irrigated")
    a["management_practices"]["water_management"]["irrigation_system"] = "Flood irrigation"
    inputs, notes = [], []
    ad.apply_activity_defaults(a, inputs, notes)
    assert any("inherited from the Ghana table" in n for n in notes)


def test_grid_factor_resolution():
    ef, src = gc.grid_factor(get_region("GH"))
    assert ef == 0.35 and "Energy Commission" in src
    ef, src = gc.grid_factor(get_region("NG"))
    assert abs(ef - 0.496) < 1e-9 and "Ember" in src
    assert gc.grid_factor(get_region("CA")) == (None, None)
    fake = SimpleNamespace(code="ZZ", name="Zed", grid_ef_kgco2_per_kwh=0.9, grid_ef_source="test source")
    assert gc.grid_factor(fake) == (0.9, "test source")


class _Q:
    """Minimal query stub: climate of a flow dict = sum of amounts of 'co2' flows."""
    def characterize_flows(self, flows, method):
        return {"Climate change": {"value": sum(r["amount"] for r in flows.values())}}

    def search_flows(self, *a, **k):
        return [{"uid": "co2", "name": "Carbon dioxide, fossil"}]


def test_grid_calibration_applies_nigeria_factor():
    flows = {"co2": {"amount": 0.3, "name": "Carbon dioxide, fossil", "unit": "kg"}}
    info = gc.apply(_Q(), {"kind": "electricity", "amount": 10.0}, flows, get_region("NG"), "m")
    assert info and abs(flows["co2"]["amount"] - 4.96) < 1e-9 and "Ember" in info["source"]
