#!/usr/bin/env python3
"""Soil carbon from management (IPCC 2019 Tier 1, Table 5.5), reported separately."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

import soil_carbon as soc

GH = SimpleNamespace(code="GH", name="Ghana", climate_zone="wet tropical", ipcc_n2o_ef1=0.016)
SN = SimpleNamespace(code="SN", name="Senegal", climate_zone="dry tropical", ipcc_n2o_ef1=0.005)


def _farm(practices=(), years=5, cover=False, residues=None, compost=False, food=None, soil=None):
    f = food or {"id": "m", "name": "Maize", "area_allocated": 2.0}
    if residues is not None:
        f["residue_management"] = residues
    sm = {"conservation_practices": list(practices), "practices_adopted_years_ago": years,
          "cover_crops": cover}
    if soil:
        sm["soil_type"] = soil
    if compost:
        sm.update({"uses_compost": True, "compost_source": "Farm-made compost",
                   "compost_application_rate": 3.0})
    return {"foods": [f], "management_practices": {"soil_management": sm}}


def test_not_booked_without_adoption_year_or_outside_window():
    rec = soc.soc_management(_farm(["No-till"], years=None), GH)
    assert rec["booked"] is False and rec["value"] is None
    assert rec["reported_separately"] and not rec["included_in_headline"]
    assert soc.soc_management(_farm(["No-till"], years=20), GH)["booked"] is False
    assert soc.soc_management(_farm(["No-till"], years=25), GH)["value"] is None


def test_no_till_tropical_wet_hand_calculated():
    # Ghana -> tropical wet, LAC: SOC_REF 52 t C/ha; F_LU 0.83; no-till F_MG 1.10 (Table 5.5)
    rec = soc.soc_management(_farm(["No-till"], years=5), GH)
    d = 52 * 0.83 * (1.10 * 1.0 - 1.0) / 20                  # 0.2158 t C/ha/yr
    assert rec["per_crop"][0]["delta_soc_t_c_per_ha_yr"] == pytest.approx(d)
    assert rec["value"] == pytest.approx(-d * 44 / 12 * 1000 * 2.0)   # -1582.5 kg CO2/yr
    assert rec["value"] == pytest.approx(-1582.53, rel=1e-4)
    assert rec["years_remaining_in_transition"] == 15
    assert "NOT in the headline" in soc.note(rec)


def _pc(a, region=GH):
    return soc.soc_management(a, region)["per_crop"][0]


def _with(a, source=None, fert=None, irrigation=None):
    sm = a["management_practices"]["soil_management"]
    if source:
        sm.update({"uses_compost": True, "compost_source": source, "compost_application_rate": 3.0})
    if fert:
        a["management_practices"]["fertilization"] = {"fertilizer_applications": fert}
    if irrigation:
        a["management_practices"]["water_management"] = {"irrigation_system": irrigation}
    return a


def test_tillage_classes_and_definitions_quoted():
    pc = _pc(_farm(["Minimum Tillage"], years=3))
    assert pc["tillage"] == "reduced tillage" and pc["f_mg"] == 1.04
    assert set(soc.INPUT_DEFINITIONS) == set(soc.INPUT)
    assert "regular addition of animal manure" in soc.INPUT_DEFINITIONS["high input with manure"]
    assert pc["input_definition"] == soc.INPUT_DEFINITIONS["medium input"]


def test_medium_all_residues_returned_no_range():
    pc = _pc(_farm(years=3))
    assert pc["input"] == "medium input" and pc["input_alternatives"] == []
    assert pc["value_range"] == [pc["value"], pc["value"]]


def test_non_manure_compost_and_mulch_are_medium_with_high_alternative():
    for a in (_farm(compost=True, years=3), _farm(["Mulching"], years=3)):
        pc = _pc(a)
        assert pc["input"] == "medium input" and pc["f_i"] == 1.0
        assert [x["input"] for x in pc["input_alternatives"]] == ["high input without manure"]
        # GH tropical wet LAC, F_I 1.11 alternative: 52 x 0.83 x 0.11 / 20 x 44/12 x 1000 x 2
        assert pc["value_range"][0] == pytest.approx(-52 * 0.83 * 0.11 / 20 * 44 / 12 * 1000 * 2)


def test_high_without_manure_from_listed_practices():
    assert _pc(_farm(cover=True, years=3))["input"] == "high input without manure"
    pc = _pc(_with(_farm(years=3), irrigation="Drip Irrigation"))
    assert pc["input"] == "high input without manure" and "irrigation" in pc["input_reason"]
    assert _pc(_with(_farm(years=3), irrigation="None (Rainfed)"))["input"] == "medium input"


def test_with_manure_needs_animal_manure_and_high_input():
    pc = _pc(_with(_farm(cover=True, years=3), source="Animal manure"))
    assert pc["input"] == "high input with manure" and pc["f_i"] == 1.44
    # farm-made compost is not animal manure
    assert _pc(_farm(cover=True, compost=True, years=3))["input"] == "high input without manure"
    # manure fertiliser row counts as manure
    fert = [{"fertilizer_type": "Poultry manure", "application_rate": 500, "applications_per_season": 1}]
    assert _pc(_with(_farm(cover=True, years=3), fert=fert))["f_i"] == 1.44
    # manure alone (no other high-input practice): medium, with-manure only as the alternative
    pc = _pc(_with(_farm(years=3), source="Animal manure"))
    assert pc["input"] == "medium input"
    assert [x["input"] for x in pc["input_alternatives"]] == ["high input with manure"]


def test_low_input_classes():
    # all residues removed/burnt, no organic matter -> low, no ambiguity
    pc = _pc(_farm(years=3, residues={"fraction_removed": 0.7, "fraction_burnt": 0.3}))
    assert pc["input"] == "low input" and pc["input_alternatives"] == []
    # residues removed but supplemental organic matter added -> medium (Table 5.5 medium)
    pc = _pc(_farm(years=3, compost=True, residues={"fraction_removed": 1.0}))
    assert pc["input"] == "medium input"
    # low-residue crop (vegetables) without mineral fertiliser or legume -> low
    veg = {"id": "t", "name": "Tomato", "category": "Vegetables", "area_allocated": 1.0}
    assert _pc(_farm(years=3, food=veg))["input"] == "low input"
    fert = [{"fertilizer_type": "NPK", "npk_ratio": "15-15-15", "application_rate": 100,
             "applications_per_season": 1}]
    veg2 = {"id": "t", "name": "Tomato", "category": "Vegetables", "area_allocated": 1.0}
    assert _pc(_with(_farm(years=3, food=veg2), fert=fert))["input"] == "medium input"


def test_partial_removal_threshold_disclosed_and_reported_as_range():
    """Audit R3: 0.30 vs 0.45 removed (+0.1 burnt) used to flip the class silently."""
    below = soc.soc_management(_farm(years=3, residues={"fraction_removed": 0.30,
                                                         "fraction_burnt": 0.1}), GH)
    above = soc.soc_management(_farm(years=3, residues={"fraction_removed": 0.45,
                                                         "fraction_burnt": 0.1}), GH)
    assert below["per_crop"][0]["input"] == "medium input"
    assert above["per_crop"][0]["input"] == "low input"
    # both report the same two-class range, so the flip is visible, not silent
    assert below["value_range"] == pytest.approx(above["value_range"])
    low_value = -52 * 0.83 * (0.92 - 1.0) / 20 * 44 / 12 * 1000 * 2
    assert below["value_range"] == pytest.approx([0.0, low_value])
    assert any("majority" in s and "0.5" in s for s in below["assumptions"])
    assert "sensitivity range" in soc.note(below)


def test_residue_removal_is_low_input_emission_in_dry_climate():
    rec = soc.soc_management(_farm(residues={"fraction_removed": 0.5, "fraction_burnt": 0.3},
                                   years=10, soil="Sandy"), SN)
    pc = rec["per_crop"][0]
    # tropical dry, SAN: SOC_REF 9; F_LU 0.92; F_I low 0.95
    d = 9 * 0.92 * (0.95 - 1.0) / 20
    assert pc["input"] == "low input" and pc["soc_ref_t_c_per_ha"] == 9.0
    assert [x["input"] for x in pc["input_alternatives"]] == ["medium input"]   # 80% partial
    assert rec["value"] == pytest.approx(-d * 44 / 12 * 1000 * 2.0)
    assert rec["value"] > 0                                   # SOC loss = emission


def test_baseline_practice_has_zero_change_and_perennial_skipped():
    assert soc.soc_management(_farm(years=5), GH)["value"] == pytest.approx(0.0)
    rec = soc.soc_management(_farm(["No-till"], years=5,
                                   food={"id": "c", "name": "Cocoa", "area_allocated": 1.0}), GH)
    assert rec["value"] == 0.0 and rec["per_crop"][0]["value"] is None


def test_flooded_rice_uses_paddy_flu():
    rec = soc.soc_management(_farm(["No-till"], years=5,
                                   food={"id": "r", "name": "Rice", "area_allocated": 1.0}), GH)
    assert rec["per_crop"][0]["f_lu"] == 1.35


def test_table_values_match_region_reference_file():
    import json
    data = json.loads((ROOT / "recommend" / "reference" / "ipcc_stock_change_factors_gh.json")
                      .read_text(encoding="utf-8"))["factors"]
    t = soc.TABLE_5_5["tropical wet"]
    assert t["fmg"] == (data["FMG_full_tillage"], data["FMG_reduced_tillage"], data["FMG_no_tillage"])
    assert t["fi"] == (data["FI_low_input"], data["FI_medium_input"],
                       data["FI_high_input_no_manure"], data["FI_high_input_with_manure"])
