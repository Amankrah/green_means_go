#!/usr/bin/env python3
"""WS1 foreground model: region field parameters, legume treatment, perennials, dLUC,
honey rejection, kernel output parsing, and the real Rust kernel end to end."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

import field_params
import perennials
import land_use_change as luc
from field_model import adjust_field_emissions, LEGUME_N2O_CREDIT
from commodities import (reject_unsupported_farm_commodities, UnsupportedCommodityError,
                         flag_processing_raw_materials)
import rust_kernel

GH = SimpleNamespace(code="GH", name="Ghana", climate_zone="wet tropical", ipcc_n2o_ef1=0.016)
DRY = SimpleNamespace(code="SN", name="Senegal", climate_zone="dry tropical", ipcc_n2o_ef1=0.005)
CA = SimpleNamespace(code="CA", name="Canada", climate_zone="cool temperate", ipcc_n2o_ef1=0.010)


# ---- field parameters -------------------------------------------------------------------

def test_wet_region_uses_disaggregated_ipcc_2019_values():
    p, _ = field_params.field_parameters(GH, {})
    assert p["ef1_synthetic"] == 0.016
    assert p["ef1_other"] == 0.006          # Table 11.1: other N inputs, wet
    assert p["ef4"] == 0.014                # Table 11.3: wet
    assert p["frac_leach"] == 0.24


def test_dry_region_has_no_leaching_unless_irrigated():
    p, _ = field_params.field_parameters(DRY, {})
    assert p["frac_leach"] == 0.0 and p["ef1_other"] == 0.005 and p["ef4"] == 0.005
    irrigated = {"management_practices": {"water_management": {"irrigation_system": "Furrow irrigation"}}}
    p2, notes = field_params.field_parameters(DRY, irrigated)
    assert p2["frac_leach"] == 0.24 and any("irrigated" in n for n in notes)
    drip = {"management_practices": {"water_management": {"irrigation_system": "Drip irrigation"}}}
    assert field_params.field_parameters(DRY, drip)[0]["frac_leach"] == 0.0


def test_explicit_region_fields_win_and_scale_applies():
    r = SimpleNamespace(**vars(GH), frac_leach=0.1, ef5=0.008, frac_gasf=0.15)
    p, _ = field_params.field_parameters(r, {"ipcc_ef1_scale": 2.0})
    assert (p["frac_leach"], p["ef5"], p["frac_gasf"]) == (0.1, 0.008, 0.15)
    assert p["ef1_synthetic"] == pytest.approx(0.032) and p["ef1_other"] == pytest.approx(0.012)


def test_prepare_kernel_assessment_sets_perennial_renewal():
    a = {"foods": [{"name": "Cocoa", "quantity_kg": 450, "area_allocated": 1}]}
    k, _ = field_params.prepare_kernel_assessment(a, GH)
    assert k["field_parameters"]["ef1_other"] == 0.006
    assert k["foods"][0]["residue_management"]["frac_renew"] == pytest.approx(1 / 25)
    assert "field_parameters" not in a                     # input not mutated


# ---- legume treatment / field model -----------------------------------------------------

def _flows():
    return [{"substance": "N2O", "quantity": 1.0, "origin": "synthetic_fertiliser"},
            {"substance": "N2O", "quantity": 1.0, "origin": "crop_residues"},
            {"substance": "NO3", "quantity": 1.0}]


def test_legume_credit_only_on_synthetic_n2o():
    a = {"field_parameters": {"ef1_synthetic": 0.016},
         "foods": [{"name": "Maize", "cropping_pattern": "Intercropping",
                    "intercropping_partners": ["Cowpea"], "area_allocated": 1}]}
    out, notes = adjust_field_emissions(_flows(), a, GH)
    syn = [f for f in out if f.get("origin") == "synthetic_fertiliser"][0]
    res = [f for f in out if f.get("origin") == "crop_residues"][0]
    assert syn["quantity"] == pytest.approx(1 - LEGUME_N2O_CREDIT)
    assert res["quantity"] == pytest.approx(1.0)       # residue N2O never credited


def test_legume_crop_does_not_self_credit():
    a = {"field_parameters": {}, "foods": [{"name": "Groundnut", "area_allocated": 1}]}
    out, _ = adjust_field_emissions(_flows(), a, GH)
    assert sum(f["quantity"] for f in out if f["substance"] == "N2O") == pytest.approx(2.0)


def test_kernel_params_present_means_no_post_scaling():
    out, _ = adjust_field_emissions(_flows(), {"field_parameters": {"ef1_synthetic": 0.016}}, GH)
    assert [f["quantity"] for f in out if f["substance"] == "N2O"] == [1.0, 1.0]


def test_legacy_path_scales_residue_by_other_ef1():
    out, _ = adjust_field_emissions(_flows(), {}, GH)
    syn, res = [f["quantity"] for f in out if f["substance"] == "N2O"]
    assert syn == pytest.approx(1.6) and res == pytest.approx(0.6)


# ---- perennials ---------------------------------------------------------------------------

def test_establishment_factor_and_permanent_land():
    a = {"foods": [{"name": "Cocoa", "quantity_kg": 450, "area_allocated": 1}],
         "field_parameters": {}}
    f, p, _ = perennials.establishment_factor(a["foods"][0])
    assert p["crop"] == "cocoa" and f == pytest.approx(25 / 22)
    out, _ = adjust_field_emissions([{"substance": "land_occ", "quantity": 10000.0}], a, GH)
    land = [x for x in out if x["substance"].startswith("land_occ")][0]
    assert land["substance"] == "land_occ_perm"
    assert land["quantity"] == pytest.approx(10000 * 25 / 22)
    ins, _ = perennials.scale_purchased_inputs([{"name": "urea", "amount": 22.0}], a)
    assert ins[0]["amount"] == pytest.approx(25.0)


def test_annual_crop_untouched():
    a = {"foods": [{"name": "Maize", "quantity_kg": 3000, "area_allocated": 1}]}
    ins, notes = perennials.scale_purchased_inputs([{"name": "urea", "amount": 10.0}], a)
    assert ins[0]["amount"] == 10.0 and notes == []


# ---- land-use change ----------------------------------------------------------------------

def test_no_dluc_by_default_but_assumption_recorded():
    flows, notes = luc.dluc_flows({"foods": [{"name": "Cocoa", "area_allocated": 1}]}, GH, 0.006, 0.24)
    assert flows == []
    assert any("no land conversion within the last 20 years" in n for n in notes)


def test_forest_to_cocoa_in_ghana():
    a = {"foods": [{"name": "Cocoa", "area_allocated": 2.0,
                    "land_use_change": {"previous_land_use": "forest", "years_since_conversion": 5}}]}
    flows, notes = luc.dluc_flows(a, GH, 0.006, 0.24)
    co2 = [f for f in flows if f["substance"] == "CO2_luc"][0]["quantity"]
    forest = luc.FOREST["tropical moist"]                 # GH override: moist deciduous
    bio = forest["agb"] * (1 + forest["r"]) * 0.47 + forest["litter"] + forest["deadwood"] - 24.0
    factors, src, region_specific = luc.load_stock_change_factors(GH)
    assert region_specific and "ipcc_stock_change_factors_gh.json" in src
    soc = 52.0 * (1.0 - factors["FLU_perennial_tree_crop"])   # tropical wet LAC, gain (negative)
    expect = (bio + soc) * 44 / 12 * 1000 * 2.0 / 20
    assert co2 == pytest.approx(expect)
    assert not any(f["substance"] == "N2O" for f in flows)    # SOC gained, no F_SOM


def test_dluc_outside_window_and_fallback_region():
    old = {"foods": [{"name": "Maize", "area_allocated": 1,
                      "land_use_change": {"previous_land_use": "forest", "years_since_conversion": 25}}]}
    assert luc.dluc_flows(old, GH, 0.006, 0.24)[0] == []
    grass = {"foods": [{"name": "Maize", "area_allocated": 1,
                        "land_use_change": {"previous_land_use": "grassland", "years_since_conversion": 3}}]}
    flows, notes = luc.dluc_flows(grass, DRY, 0.005, 0.0)
    assert any(f["substance"] == "CO2_luc" for f in flows)
    assert any(f["substance"] == "N2O" for f in flows)        # SOC loss mineralises N
    assert any("not region-specific" in n for n in notes)
    factors, src, region_specific = luc.load_stock_change_factors(DRY)
    assert not region_specific and factors["FLU_long_term_cultivated"] == 0.92


# ---- honey --------------------------------------------------------------------------------

def test_honey_is_rejected_on_the_farm_path():
    with pytest.raises(UnsupportedCommodityError):
        reject_unsupported_farm_commodities({"foods": [{"name": "Raw honey"}]})
    reject_unsupported_farm_commodities({"foods": [{"name": "Maize"}]})


def test_service_rejects_honey_before_building_an_engine():
    import service
    with pytest.raises(UnsupportedCommodityError):
        service.run_farm_assessment({"country": "Ghana", "foods": [{"name": "Honey"}]},
                                    run_uncertainty=False)


def test_processing_honey_raw_material_flagged():
    out, notes = flag_processing_raw_materials(
        [{"name": "Raw honey", "kind": "raw_material", "amount": 1, "unit": "kg"}])
    assert out[0]["match_as"].startswith("Honey, raw")
    assert notes[0].startswith("validation warning:")


# ---- kernel output parsing ----------------------------------------------------------------

def test_extract_tags_origins_and_surfaces_warnings():
    result = {"results": {"lci_warnings": ["fertiliser type 'X' is not recognised"],
                          "lci_inventory": [
        {"substance": "Dinitrogen monoxide (N2O)", "quantity": 1, "unit": "kg", "source": "Direct"},
        {"substance": "Dinitrogen monoxide (N2O) - crop residues", "quantity": 2, "unit": "kg",
         "source": "Crop residue N2O ... production of something"},
        {"substance": "Methane (CH4) - residue burning", "quantity": 3, "unit": "kg", "source": "burn"},
    ]}}
    lci, notes = rust_kernel.extract_onfarm_lci(result)
    origins = {f.get("origin") for f in lci}
    assert origins == {"synthetic_fertiliser", "crop_residues", "residue_burning"}
    assert any(n.startswith(rust_kernel.WARNING_PREFIX) for n in notes)


def test_lift_validation_warnings():
    import service
    out = service.lift_validation_warnings(
        {"data_quality": {"warnings": [], "notes": ["validation warning: abc", "other"]}})
    assert out["data_quality"]["warnings"] == ["abc"]


# ---- real Rust kernel, end to end ---------------------------------------------------------

needs_kernel = pytest.mark.skipif(rust_kernel._binary() is None, reason="Rust binary not built")


def _farm(name="Maize", fert="Urea", irrigation="None (Rainfed)", qty=3000.0):
    return {
        "company_name": "t", "country": "Ghana",
        "foods": [{"id": "1", "name": name, "quantity_kg": qty, "category": "Cereals",
                   "area_allocated": 1.0}],
        "management_practices": {
            "soil_management": {}, "pest_management": {},
            "water_management": {"irrigation_system": irrigation},
            "fertilization": {"uses_fertilizers": True, "fertilizer_applications": [
                {"fertilizer_type": fert, "application_rate": 100.0, "applications_per_season": 1}]},
        },
    }


@needs_kernel
def test_kernel_honours_dry_parameters_end_to_end():
    a, _ = field_params.prepare_kernel_assessment(_farm(), DRY)
    lci, _ = rust_kernel.onfarm_lci_from_assessment(a)
    assert sum(f["quantity"] for f in lci if f["substance"] == "NO3") == 0.0   # FracLEACH = 0
    direct = [f for f in lci if f.get("origin") == "synthetic_fertiliser"]
    total_syn = sum(f["quantity"] for f in direct)
    expect = 46 * (0.005 + 0.11 * 0.005) * 44 / 28
    assert total_syn == pytest.approx(expect)
    assert any(f.get("origin") == "crop_residues" for f in lci)


@needs_kernel
def test_kernel_unknown_fertiliser_zero_n_with_warning():
    a, _ = field_params.prepare_kernel_assessment(_farm(fert="Foliar Fertilizer"), GH)
    lci, notes = rust_kernel.onfarm_lci_from_assessment(a)
    assert not [f for f in lci if f.get("origin") == "synthetic_fertiliser" and f["quantity"] > 0]
    assert any(n.startswith(rust_kernel.WARNING_PREFIX) and "not recognised" in n for n in notes)


@needs_kernel
def test_kernel_legume_residue_n2o_without_bnf():
    a = _farm(name="Groundnut", fert="None", qty=1500.0)
    a["foods"][0]["category"] = "Legumes"
    k, _ = field_params.prepare_kernel_assessment(a, GH)
    lci, _ = rust_kernel.onfarm_lci_from_assessment(k)
    res = sum(f["quantity"] for f in lci if f.get("origin") == "crop_residues")
    crop = 1500 * 0.94
    f_cr = crop * 1.0 * 0.016 + (crop + crop) * 0.19 * 0.008
    assert res == pytest.approx(f_cr * (0.006 + 0.24 * 0.011) * 44 / 28)
    assert not [f for f in lci if f.get("origin") == "synthetic_fertiliser" and f["quantity"] > 0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
