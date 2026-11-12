"""Matcher defects exposed by the six-region mapping run (WS4 follow-up). One test per defect,
on a faked matcher (no store or API needed); the end-to-end check is the golden regression
in engine/test_matcher_regression.py."""
from __future__ import annotations

import pytest

from engine import orchestrator as orch
from engine import product_identity as pid
from engine.regions import get_region, location_rank
from engine.test_matcher_identity import _FakeMatcher, _FakeQ


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    monkeypatch.setenv("GMG_LLM_ADJUDICATE", "0")


def _c(uid, name, loc, score, ref=None, unit="kg", hidden=False):
    return {"uid": uid, "name": name, "location": loc, "score": score,
            "reference_product": ref or name, "ref_unit": unit, "hidden": hidden}


def _engine(region, cands):
    eng = orch.FarmLCA.__new__(orch.FarmLCA)
    eng.region = get_region(region)
    eng.matcher = _FakeMatcher(cands)
    eng.q = _FakeQ()
    return eng


# 1. a burned-fuel input must match a combustion dataset, in every region ------------------
def test_burned_fuel_never_takes_a_supply_dataset():
    pool = [_c("imp-za", "diesel, import from RoW", "South Africa", 0.80, "diesel"),
            _c("mkt-za", "market for diesel", "South Africa", 0.79, "diesel"),
            _c("burn-glo", "Diesel, burned in agricultural machinery {GLO} - Adapted from WFLDB U",
               "Global", 0.76, unit="MJ")]
    m = _engine("ZA", pool)._match_input("diesel, burned in agricultural machinery",
                                         context={"amount_unit": "MJ"})
    assert m["uid"] == "burn-glo"


def test_supply_query_never_takes_a_combustion_dataset():
    pool = [_c("burn", "propane, burned in building machine", "Global", 0.80,
               "propane, burned in building machine", unit="MJ"),
            _c("lpg", "market for liquefied petroleum gas", "Rest of World", 0.75,
               "liquefied petroleum gas")]
    m = _engine("GH", pool)._match_input("market for liquefied petroleum gas")
    assert m["uid"] == "lpg"


def test_diesel_pump_needs_pump_operation():
    pool = [_c("mkt-za", "market for diesel", "South Africa", 0.80, "diesel"),
            _c("pump-za", "water pump operation, diesel", "South Africa", 0.70,
               "water pump operation, diesel", unit="MJ")]
    m = _engine("ZA", pool)._match_input(
        "market for water pump operation, diesel | water pump operation, diesel")
    assert m["uid"] == "pump-za"


# 2. BF grid: RAF / "Africa" market group, never South Africa --------------------------------
def test_bf_grid_steps_down_to_africa_market_group():
    pool = [_c("za-tr", "electricity voltage transformation from medium to low voltage",
               "South Africa", 0.70, "electricity, low voltage", unit="kWh"),
            _c("row", "Electricity, low voltage {RoW}| electricity voltage transformation",
               "Rest of World", 0.62, unit="kWh", hidden=True),
            _c("raf", "market group for electricity, low voltage", "Africa", 0.55,
               "electricity, low voltage", unit="kWh", hidden=True)]
    m = _engine("BF", pool)._match_input("electricity low voltage", context={"amount_unit": "kWh"})
    assert m["uid"] == "raf" and m["location"] != "South Africa"
    bf = get_region("BF")
    assert location_rank(bf, "South Africa") == location_rank(bf, "Narnia")


# 3. copper fungicide, packaging and treated water ---------------------------------------------
def test_copper_oxide_is_not_copper_metal():
    pool = [_c("pgm", "platinum group metal, extraction and refinery operations", "South Africa",
               0.70, "copper, cathode"),
            _c("cuo", "copper oxide production", "Rest of World", 0.66, "copper oxide")]
    assert _engine("ZA", pool)._match_input("market for copper oxide")["uid"] == "cuo"


@pytest.mark.parametrize("query,waste_name,waste_ref,good_name,good_ref", [
    ("market for packaging glass, white", "market for waste glass", "waste glass",
     "packaging glass production, white", "packaging glass, white"),
    ("market for packaging film, low density polyethylene",
     "Waste polyethylene {ZA}| market for waste polyethylene", None,
     "packaging film production, low density polyethylene",
     "packaging film, low density polyethylene"),
])
def test_packaging_never_takes_a_waste_stream(query, waste_name, waste_ref, good_name, good_ref):
    pool = [_c("waste", waste_name, "South Africa", 0.75, waste_ref),
            _c("good", good_name, "Rest of World", 0.72, good_ref)]
    assert _engine("ZA", pool)._match_input(query)["uid"] == "good"


def test_waste_stream_still_serves_waste_treatment():
    ident = pid.query_identity("treatment of waste paper, sorting")
    prov = pid.candidate_concepts("treatment of waste paper, unsorted, sorting", "waste paper, sorted")
    assert pid.passes(ident, prov)


def test_deionised_water_is_not_decarbonised():
    pool = [_c("dec", "market for water, decarbonised", "Canada", 0.80, "water, decarbonised"),
            _c("dei", "market for water, deionised", "Rest of World", 0.78, "water, deionised")]
    assert _engine("CA", pool)._match_input("market for water, deionised")["uid"] == "dei"


# 4. seed for sowing is a different product from grain -----------------------------------------
def test_maize_seed_for_sowing_is_not_grain():
    pool = [_c("grain", "market for maize grain", "South Africa", 0.80, "maize grain"),
            _c("seed", "market for maize seed, for sowing", "Global", 0.75, "maize seed, for sowing")]
    assert _engine("ZA", pool)._match_input("market for maize seed, for sowing")["uid"] == "seed"
    # and the grain query never takes the seed
    assert _engine("ZA", pool)._match_input("maize grain production")["uid"] == "grain"


# 5. biogas, incineration and anaerobic digestion ---------------------------------------------
def test_biogas_is_not_digestate():
    pool = [_c("dig", "Digestate, from anaerobic digestion of manure and slurry mix (fertilizer)",
               "Europe", 0.80),
            _c("bg", "anaerobic digestion of manure", "Rest of World", 0.74, "biogas", unit="m3")]
    m = _engine("GH", pool)._match_input("anaerobic digestion of manure | biogas | Cutoff, U",
                                         context={"amount_unit": "m3"})
    assert m["uid"] == "bg"


@pytest.mark.parametrize("query,product", [
    ("treatment of biowaste, municipal incineration", "biowaste"),
    ("treatment of biowaste by anaerobic digestion", "biowaste"),
])
def test_waste_treatment_takes_the_kg_referenced_output(query, product):
    name = query
    pool = [_c("heat", name, "Rest of World", 0.80,
               "heat, for reuse in municipal waste incineration only", unit="MJ"),
            _c("gas", name, "Rest of World", 0.80, "biogas", unit="m3"),
            _c("kg", name, "Rest of World", 0.79, product, unit="kg")]
    m = _engine("GH", pool)._match_input(query, context={"amount_unit": "kg",
                                                         "input_name": "solid waste"})
    assert m["uid"] == "kg"


def test_unit_filter_keeps_all_when_none_compatible():
    pool = [_c("a", "treatment of biowaste by anaerobic digestion", "Rest of World", 0.8, "biogas",
               unit="m3")]
    m = _engine("GH", pool)._match_input("treatment of biowaste by anaerobic digestion",
                                         context={"amount_unit": "kg"})
    assert m["uid"] == "a"


# 6. hydro and wind stay in the preference list when a RoW variant exists ---------------------
@pytest.mark.parametrize("tech", ["hydro, run-of-river", "wind, 1-3MW turbine, onshore"])
def test_renewables_fall_to_row_not_foreign(tech):
    name = f"electricity production, {tech}"
    pool = [_c("cn", name, "China, Fujian", 0.80, "electricity, high voltage", unit="kWh"),
            _c("row", name, "Rest of World", 0.78, "electricity, high voltage", unit="kWh",
               hidden=True)]
    m = _engine("BF", pool)._match_input(f"{name} | electricity, high voltage | Cutoff, U",
                                         context={"amount_unit": "kWh"})
    assert m["uid"] == "row"


def test_grid_query_never_takes_a_single_technology_plant():
    pool = [_c("hydro", "electricity production, hydro, run-of-river", "Ghana", 0.80,
               "electricity, high voltage", unit="kWh"),
            _c("grid", "market for electricity, low voltage", "Ghana", 0.75,
               "electricity, low voltage", unit="kWh")]
    assert _engine("GH", pool)._match_input("electricity low voltage")["uid"] == "grid"
