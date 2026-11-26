#!/usr/bin/env python3
"""
test_service_attribution.py - engine/service.py per-crop attribution (ISO 14044 §4.3.4.2,
audit 3.9), admin-region climate and season derivation, the needs_review publication gate,
and engine/perennials.py (blank establishment fields, extended crop table).

Pure-Python tests run everywhere; the full-assessment test skips without the canonical store
or the Rust kernel binary.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
for p in (str(ROOT), str(ROOT.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

import service  # noqa: E402
import perennials  # noqa: E402
import crop_defaults  # noqa: E402
from orchestrator import review_items, AssessmentResult  # noqa: E402

CASE = ROOT / "case_studies" / "ghana_maize_cowpea_intercrop.json"
DB = ROOT.parent / "data" / "canonical" / "lca_engineer.sqlite"


def _farm(maize_only=True) -> dict:
    a = json.loads(CASE.read_text(encoding="utf-8"))
    for row in a["management_practices"]["fertilization"]["fertilizer_applications"]:
        row["crop_ids"] = ["crop_maize"] if maize_only else []
    a["management_practices"]["pest_management"]["pesticides"][0]["crop_ids"] = ["crop_maize"]
    return a


def _food(a, fid):
    return next(f for f in a["foods"] if f["id"] == fid)


# ------------------------------------------------------------------ per-crop attribution
def test_maize_gets_npk_and_cowpea_does_not():
    a = _farm()
    maize, notes_m = service.attribute_to_crop(a, _food(a, "crop_maize"))
    cowpea, notes_c = service.attribute_to_crop(a, _food(a, "crop_cowpea"))
    fert = lambda x: x["management_practices"]["fertilization"]["fertilizer_applications"]  # noqa: E731
    pest = lambda x: x["management_practices"]["pest_management"]["pesticides"]  # noqa: E731
    assert {r["fertilizer_type"] for r in fert(maize)} == {"NPK Compound", "Urea"}
    assert fert(cowpea) == [] and pest(cowpea) == []
    assert len(pest(maize)) == 1
    assert not notes_m and any("fertiliser" in n for n in notes_c)
    # the farm assessment itself is untouched
    assert len(fert(a)) == 2


def test_empty_crop_ids_apply_to_every_crop():
    a = _farm(maize_only=False)
    cowpea, _ = service.attribute_to_crop(a, _food(a, "crop_cowpea"))
    assert len(cowpea["management_practices"]["fertilization"]["fertilizer_applications"]) == 2


def test_sub_assessment_keeps_attribution_and_partitions_energy():
    a = _farm()
    a["management_practices"]["water_management"]["irrigation_water_m3"] = 1000.0
    share = 1.7 / 4.2
    sub = service._sub_assessment(a, _food(a, "crop_cowpea"), share)
    assert sub["foods"] == [_food(a, "crop_cowpea")]
    assert sub["management_practices"]["fertilization"]["fertilizer_applications"] == []
    assert sub["management_practices"]["water_management"]["irrigation_water_m3"] == pytest.approx(1000 * share)
    assert sub["equipment_energy"]["fuel_consumption"][0]["monthly_consumption"] == pytest.approx(45 * share)


def test_purchased_inputs_follow_attribution():
    """The supply-chain inputs of the cowpea system carry no fertiliser; maize carries it."""
    from inputs import extract_purchased_inputs
    a = _farm()
    kinds = {}
    for fid, area in (("crop_maize", 2.5), ("crop_cowpea", 1.7)):
        sub = service._sub_assessment(a, _food(a, fid), area / 4.2)
        rows, _ = extract_purchased_inputs(sub)
        kinds[fid] = [r for r in rows if r.get("kind") == "fertiliser"]
    assert kinds["crop_maize"] and not kinds["crop_cowpea"]


def test_compost_crop_ids():
    a = _farm()
    a["management_practices"]["soil_management"]["compost_crop_ids"] = ["crop_maize"]
    cowpea, notes = service.attribute_to_crop(a, _food(a, "crop_cowpea"))
    maize, _ = service.attribute_to_crop(a, _food(a, "crop_maize"))
    assert cowpea["management_practices"]["soil_management"]["uses_compost"] is False
    assert maize["management_practices"]["soil_management"]["uses_compost"] is True
    assert any("compost" in n for n in notes)


def test_lime_rows_by_crop():
    a = _farm()
    a["management_practices"]["soil_management"]["lime_applications"] = [
        {"material": "limestone", "rate_t_per_ha_per_year": 1.0, "crop_ids": ["crop_cowpea"]}]
    maize, _ = service.attribute_to_crop(a, _food(a, "crop_maize"))
    assert maize["management_practices"]["soil_management"]["lime_applications"] == []


def test_rows_for_unknown_crops_are_flagged():
    a = _farm()
    a["management_practices"]["fertilization"]["fertilizer_applications"][0]["crop_ids"] = ["ghost"]
    warn = service._unassigned_rows(a)
    assert len(warn) == 1 and "ghost" in warn[0]


def test_none_and_zero_rate_fertiliser_rows_dropped():
    a = _farm(maize_only=False)
    rows = a["management_practices"]["fertilization"]["fertilizer_applications"]
    rows.append({"fertilizer_type": "None", "application_rate": 50, "applications_per_season": 1})
    rows.append({"fertilizer_type": "Urea", "application_rate": 0, "applications_per_season": 1})
    rows.append({"fertilizer_type": "Urea", "application_rate": 10, "applications_per_season": 0})
    out, notes = service.drop_null_fertiliser(a)
    assert len(out["management_practices"]["fertilization"]["fertilizer_applications"]) == 2
    assert notes and len(rows) == 5


def test_farm_headline_is_sum_of_crop_systems():
    def res(v):
        r = AssessmentResult(region="Ghana", method="m")
        r.impacts = {"Climate change": {"value": v, "unit": "kg CO2-eq"}}
        r.inventory = {"u": {"name": "CO2", "unit": "kg", "amount": v}}
        return r
    farm = service._sum_results({"Maize (3500kg)": res(100.0), "Cowpea (850kg)": res(20.0)})
    assert farm.impacts["Climate change"]["value"] == pytest.approx(120.0)
    assert farm.inventory["u"]["amount"] == pytest.approx(120.0)


def test_per_crop_functional_units_for_mixed_products():
    a = _farm()
    out = {"functional_units": {"per_kg": {"total_kg": 4350}},
           "breakdown_by_food": {
               "Maize (3500kg)": {"Global warming": {"value": 700.0, "unit": "kg CO2-eq"}},
               "Cowpea (850kg)": {"Global warming": {"value": 85.0, "unit": "kg CO2-eq"}}},
           "data_quality": {"warnings": []}}
    out = service._per_crop_units(out, a)
    fu = out["functional_units"]
    assert fu["headline"] == "per_ha" and fu["per_kg"]["mixed_products"] is True
    assert fu["per_crop"]["Maize (3500kg)"]["midpoint_impacts_per_kg"]["Global warming"]["value"] == pytest.approx(0.2)
    assert fu["per_crop"]["Cowpea (850kg)"]["midpoint_impacts_per_ha"]["Global warming"]["value"] == pytest.approx(50.0)
    assert any("different products" in w for w in out["data_quality"]["warnings"])


def test_single_product_keeps_per_kg_headline():
    a = _farm()
    a["foods"][1]["name"] = "Maize"
    out = service._per_crop_units({"functional_units": {"per_kg": {}}, "breakdown_by_food": {}}, a)
    assert out["functional_units"]["headline"] == "per_kg"


# ---------------------------------------------------------------------- review gate
def test_needs_review_sets_top_level_flag():
    matches = [{"input": "urea", "matched": "urea production", "needs_review": False},
               {"input": "neem extract", "matched": "pesticide, unspecified",
                "needs_review": True, "review_reason": "no dataset carries 'neem'"}]
    items = review_items(matches)
    assert [i["input"] for i in items] == ["neem extract"]
    out = service._review_flag({"input_matches": matches, "data_quality": {"warnings": []}})
    assert out["review_required"] is True and out["review_items"] == items
    assert any("need review" in w for w in out["data_quality"]["warnings"])
    clean = service._review_flag({"input_matches": matches[:1], "data_quality": {}})
    assert clean["review_required"] is False
    r = AssessmentResult(region="x", method="m", input_matches=matches)
    assert r.review_required


def test_review_items_list_an_input_once_across_crops():
    flagged = {"input": "neem extract", "matched": "pesticide, unspecified", "uid": "u1",
               "needs_review": True, "review_reason": "no dataset carries 'neem'"}
    items = review_items([flagged, dict(flagged), {**flagged, "input": "other"}])
    assert [i["input"] for i in items] == ["neem extract", "other"]


def test_season_note_only_when_it_matters():
    a = {"foods": [{"name": "Wheat", "planting_months": [5]}],
         "management_practices": {"water_management": {"irrigation_system": "None (Rainfed)"}}}
    _, notes = service.derive_seasons(a, "CA")
    assert not any("season not derived" in n for n in notes)
    a["management_practices"]["water_management"]["irrigation_system"] = "Sprinkler"
    _, notes = service.derive_seasons(a, "CA")
    assert any("season not derived" in n for n in notes)


# ------------------------------------------------------------- climate and season
def test_climate_engine_applies_admin_region_wet_dry():
    class Eng:
        pass
    eng = Eng()
    import regions
    eng.region = regions.REGIONS["NG"]
    view, note = service._climate_engine(eng, {"study_meta": {"admin_region": "Katsina"}})
    assert view is not eng and eng.region.ipcc_n2o_ef1 == 0.016            # cache untouched
    assert (view.region.ipcc_n2o_ef1, view.region.frac_leach) == (0.005, 0.0)
    assert "Katsina" in note and "597.5" in note
    same, note2 = service._climate_engine(eng, {})
    assert same is eng and "region default" in note2


def test_climate_engine_prefers_canadian_province():
    class Eng:
        pass
    import regions
    eng = Eng()
    eng.region = regions.REGIONS["CA"]
    view, _ = service._climate_engine(eng, {"study_meta": {"admin_region": "Alberta"}})
    assert view.region.location_prefer[2] == "Canada, Alberta"
    assert view.region.ipcc_n2o_ef1 == 0.005                                 # Prairie: dry


def test_derive_seasons_from_planting_months():
    a = {"study_meta": {"admin_region": "Upper East"},
         "foods": [{"name": "Rice", "planting_months": [12, 1]},
                   {"name": "Maize", "planting_months": [6]},
                   {"name": "Tomato", "planting_months": [2, 7]},
                   {"name": "Okra", "seasonal_factor": "DrySeason", "planting_months": [6]},
                   {"name": "Yam"}]}
    out, notes = service.derive_seasons(a, "GH")
    got = [f.get("seasonal_factor") for f in out["foods"]]
    assert got == ["DrySeason", "WetSeason", "YearRound", "DrySeason", None]
    assert "seasonal_factor" not in a["foods"][0]                            # input untouched
    assert any("no planting months" in n for n in notes)


def test_unknown_season_uses_full_water_need():
    food = {"name": "Maize", "area_allocated": 1.0}
    blank = crop_defaults.irrigation_default_m3(food, "Furrow")
    wet = crop_defaults.irrigation_default_m3({**food, "seasonal_factor": "WetSeason"}, "Furrow")
    dry = crop_defaults.irrigation_default_m3({**food, "seasonal_factor": "DrySeason"}, "Furrow")
    assert blank["m3"] == pytest.approx(dry["m3"]) == pytest.approx(2 * wet["m3"])
    assert "season unknown" in blank["source"] and "UNSOURCED" in blank["source"]
    double = crop_defaults.irrigation_default_m3({**food, "seasonal_factor": "DrySeason",
                                                  "crops_per_year": 2}, "Furrow")
    assert double["m3"] == pytest.approx(2 * dry["m3"])


def test_derive_seasonal_factor_rule():
    assert crop_defaults.derive_seasonal_factor([], {5, 6})[0] is None
    assert crop_defaults.derive_seasonal_factor([5], set())[0] is None
    assert crop_defaults.derive_seasonal_factor(["6", 7], {6, 7, 8})[0] == "WetSeason"


# ------------------------------------------------------------------------ perennials
def test_establishment_with_none_fields_does_not_crash():
    food = {"name": "Cocoa", "establishment": {"immature_years": None, "productive_years": None,
                                                "input_share": None}}
    f, p, note = perennials.establishment_factor(food)
    assert p["crop"] == "cocoa" and f == pytest.approx((3 + 22) / 22)
    f2, _, _ = perennials.establishment_factor(
        {"name": "Cocoa", "establishment": {"immature_years": 4, "input_share": None}})
    assert f2 == pytest.approx((4 + 22) / 22)


@pytest.mark.parametrize("name,crop", [("Mango", "mango"), ("Sweet orange", "citrus"),
                                       ("Cashew nuts", "cashew"), ("Robusta coffee", "coffee"),
                                       ("Plantain", "plantain"), ("Banana", "plantain"),
                                       ("Rubber (latex)", "rubber"), ("Coconut", "coconut")])
def test_extended_perennials(name, crop):
    p = perennials.perennial_for(name)
    assert p and p["crop"] == crop and p["source"]
    assert p["lifetime_years"] == p["immature_years"] + p["productive_years"]


def test_orange_fleshed_sweet_potato_is_not_citrus():
    assert perennials.perennial_for("Orange-fleshed sweet potato") is None


def test_farmer_declared_perennial():
    food = {"name": "Shea", "establishment": {"immature_years": 10, "productive_years": 40}}
    f, p, note = perennials.establishment_factor(food)
    assert p["source"].startswith("farmer-declared") and f == pytest.approx(50 / 40)
    assert perennials.establishment_factor({"name": "Shea"})[1] is None
    assert perennials.establishment_factor(
        {"name": "Shea", "establishment": {"immature_years": None, "productive_years": 40}})[1] is None


_EST = {"immature_years": 3, "productive_years": 20, "input_share": 0.5}


@pytest.mark.parametrize("food", [
    {"name": "Maize"}, {"name": "Cassava"}, {"name": "Yam"}, {"name": "Cowpea"},
    {"name": "Local grain", "category": "Cereals"}, {"name": "Okra", "category": "Other"},
    {"name": "Crop X", "crop_type": "hybrid maize"}])
def test_establishment_on_annual_crop_is_ignored_with_warning(food):
    """Audit wave-3 R2: establishment years on maize scaled every input by 1.075, collapsed
    residue N via frac_renew, booked permanent-crop land and zeroed SOC."""
    food = {**food, "establishment": dict(_EST)}
    assert perennials.known_annual(food)
    assert perennials.perennial_for_food(food) is None
    f, p, note = perennials.establishment_factor(food)
    assert f == 1.0 and p is None
    assert note.startswith("validation warning: ") and "annual crop" in note
    a = {"foods": [{**food, "quantity_kg": 3000, "area_allocated": 1}]}
    ins, notes = perennials.scale_purchased_inputs([{"name": "urea", "amount": 400.0}], a)
    assert ins[0]["amount"] == 400.0 and notes == [note]
    flows, fnotes = perennials.apply_to_field_flows([{"substance": "land_occ", "quantity": 1e4}], a)
    assert flows[0] == {"substance": "land_occ", "quantity": 1e4} and fnotes == []
    import field_params
    kernel_a, _ = field_params.prepare_kernel_assessment({**a, "field_parameters": {}}, None)
    assert "frac_renew" not in (kernel_a["foods"][0].get("residue_management") or {})


def test_annual_without_establishment_has_no_warning():
    assert perennials.establishment_factor({"name": "Maize"}) == (1.0, None, None)


@pytest.mark.parametrize("name", ["Shea", "African locust bean", "Kola nut"])
def test_unlisted_tree_crops_still_accept_declared_establishment(name):
    food = {"name": name, "category": "Nuts", "establishment": dict(_EST)}
    assert not perennials.known_annual(food)
    f, p, _ = perennials.establishment_factor(food)
    assert p is not None and f == pytest.approx((3 * 0.5 + 20) / 20)


def test_table_perennial_wins_over_annual_category():
    food = {"name": "Cocoa beans", "category": "Legumes"}
    assert not perennials.known_annual(food)
    assert perennials.perennial_for_food(food)["crop"] == "cocoa"


def test_perennial_scaling_is_disclosed_next_to_kernel_notes():
    a = {"foods": [{"name": "Cocoa", "quantity_kg": 450, "area_allocated": 1}]}
    _, notes = perennials.apply_to_field_flows([{"substance": "N2O", "quantity": 1.0}], a)
    assert any("mature-year (unamortised) amounts" in n and "1.136" in n for n in notes)


def test_plantain_has_no_establishment_amortisation():
    f, p, _ = perennials.establishment_factor({"name": "Plantain"})
    assert p and f == 1.0


# ------------------------------------------------------------- full run (store + kernel)
def _kernel_ready() -> bool:
    try:
        import rust_kernel
        return DB.exists() and rust_kernel._binary() is not None
    except Exception:
        return False


@pytest.mark.skipif(not _kernel_ready(), reason="canonical store or Rust kernel not available")
def test_full_run_cowpea_carries_no_fertiliser():
    """Restricting the fertiliser to maize lowers cowpea's burden, leaves maize's unchanged,
    and the farm total is the sum of the two crop systems."""
    runs = {}
    for maize_only in (True, False):
        a = _farm(maize_only)
        a["study_meta"] = {"admin_region": "Northern"}
        runs[maize_only] = service.run_farm_assessment(copy.deepcopy(a), region="GH",
                                                       run_uncertainty=False)

    def gwp(out, label):
        mids = out["breakdown_by_food"][label]
        return next(v["value"] for k, v in mids.items() if "warming" in k.lower())

    only, everywhere = runs[True], runs[False]
    assert gwp(only, "Cowpea (850kg)") < gwp(everywhere, "Cowpea (850kg)")
    assert gwp(only, "Maize (3500kg)") == pytest.approx(gwp(everywhere, "Maize (3500kg)"), rel=1e-6)
    total = next(v["value"] for k, v in only["midpoint_impacts"].items() if "warming" in k.lower())
    assert total * 4350 == pytest.approx(gwp(only, "Maize (3500kg)") + gwp(only, "Cowpea (850kg)"),
                                         rel=1e-6)
    assert only["functional_units"]["headline"] == "per_ha"
    assert "review_required" in only
    assert any("Northern" in n for n in only["data_quality"]["notes"])
