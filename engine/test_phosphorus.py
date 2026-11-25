#!/usr/bin/env python3
"""SALCA-P field phosphorus (engine/phosphorus.py), Cd disclosure, and their wiring into
engine/farm_flows.py. Hand-calculated checks."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))

import pytest

import phosphorus as phos
import heavy_metals as hm

DB = ROOT.parent / "data" / "canonical" / "lca_engineer.sqlite"


def _farm(apps, practices=(), erosion=None, area=2.0, cpy=1):
    a = {"foods": [{"id": "m", "name": "Maize", "area_allocated": area, "crops_per_year": cpy},
                   {"id": "s", "name": "Sorghum", "area_allocated": 1.0}],
         "management_practices": {
             "fertilization": {"uses_fertilizers": True, "fertilizer_applications": apps},
             "soil_management": {"conservation_practices": list(practices)}}}
    if erosion:
        a["erosion"] = erosion
    return a


def test_p2o5_grades():
    assert phos.p2o5_fraction("NPK", "15-15-15")[:2] == (0.15, "min")
    assert phos.p2o5_fraction("NPK", "20-10-10")[0] == 0.10          # declared grade wins
    assert phos.p2o5_fraction("Diammonium Phosphate (DAP)", None)[0] == 0.46
    assert phos.p2o5_fraction("TSP", None)[0] == 0.46
    assert phos.p2o5_fraction("Urea", None)[0] == 0.0
    assert phos.p2o5_fraction("Muriate of Potash", None)[0] == 0.0
    assert phos.p2o5_fraction("Poultry manure", None)[:2] == (0.0, "man")
    assert phos.p2o5_fraction("Liquid slurry", "3-2-3")[:2] == (0.02, "sl")


def test_leaching_and_runoff_hand_calculated():
    # NPK 15-15-15, 100 kg/ha x 2 applications, maize only (crop_ids), 2 crops per year:
    # P2O5_min = 100 x 2 x 2 x 0.15 = 60 kg/ha/yr on maize; sorghum 0.
    apps = [{"fertilizer_type": "NPK", "npk_ratio": "15-15-15", "application_rate": 100,
             "applications_per_season": 2, "crop_ids": ["m"]}]
    out, notes = phos.field_p_losses(_farm(apps, cpy=2))
    leach = 0.07 * 2.0 + 0.07 * 1.0                                   # no slurry: Fgw = 1
    runoff = 0.175 * (1 + 0.2 / 80 * 60) * 2.0 + 0.175 * 1.0          # 0.4025 + 0.175
    assert out["p_leach"] == pytest.approx(leach)
    assert out["p_runoff"] == pytest.approx(runoff) and runoff == pytest.approx(0.5775)
    assert out["po4_groundwater"] == pytest.approx(leach * 94.971 / 30.974)
    assert out["po4_surface"] == pytest.approx(runoff * 94.971 / 30.974)
    assert out["p_erosion"] == 0.0 and not out["erosion_modelled"]
    assert any("erosion P not modelled" in n for n in notes)


def test_manure_and_slurry_terms():
    apps = [{"fertilizer_type": "Cattle slurry", "npk_ratio": "4-2-4", "application_rate": 1000,
             "applications_per_season": 1, "crop_ids": ["m"]}]
    out, _ = phos.field_p_losses(_farm(apps))
    # P2O5_sl = 1000 x 0.02 = 20 kg/ha
    assert out["p_leach"] == pytest.approx(0.07 * (1 + 0.2 / 80 * 20) * 2 + 0.07)
    assert out["p_runoff"] == pytest.approx(0.175 * (1 + 0.7 / 80 * 20) * 2 + 0.175)


def test_erosion_rusle_with_contour_support_practice():
    e = {"rusle_r": 500.0, "rusle_k": 0.02, "rusle_ls": 1.0, "rusle_c": 0.4, "slope_pct": 5.0}
    out, notes = phos.field_p_losses(_farm([], practices=["Contour Plowing"], erosion=e))
    a = 500 * 0.02 * 1.0 * 0.4 * 0.5                    # = 2 t/ha/yr, P = 0.5 at 3-8 % slope
    assert out["p_erosion"] == pytest.approx(a * 1000 * 0.00095 * 1.86 * 0.2 * 3.0)
    assert out["erosion_modelled"]
    assert phos.support_practice_factor(["Terracing"], 15.0)[0] == 0.70
    assert phos.support_practice_factor(["None"], 5.0)[0] == 1.0
    assert phos.support_practice_factor(["Bunds/Ridges"], None)[0] == 1.0      # slope unknown


def test_cadmium_is_disclosed_not_booked():
    apps = [{"fertilizer_type": "TSP", "application_rate": 50, "applications_per_season": 1}]
    rec, notes = hm.cadmium_disclosure(_farm(apps))
    assert rec["booked"] is False
    assert rec["mineral_p2o5_kg"] == pytest.approx(50 * 0.46 * 3.0)          # all crops, 3 ha
    assert rec["cd_upper_bound_g"] == pytest.approx(69.0 * 60 / 1000)
    assert notes and "not booked" in notes[0]


@pytest.mark.skipif(not DB.exists(), reason="canonical store not available")
def test_farm_flows_books_p_to_ecoinvent_water_compartments_and_soc_separately():
    import farm_flows

    apps = [{"fertilizer_type": "NPK", "npk_ratio": "15-15-15", "application_rate": 100,
             "applications_per_season": 1}]
    a = _farm(apps)
    a["management_practices"]["soil_management"].update(
        {"conservation_practices": ["No-till"], "practices_adopted_years_ago": 4})
    conn = sqlite3.connect(str(DB))
    try:
        flows, notes, _ = farm_flows.extra_flows(a, conn, None, None)
        cats = {r[0]: r[1] for r in conn.execute(
            "SELECT uid, category FROM flows WHERE uid IN (%s)" % ",".join("?" * len(flows)),
            [f["uid"] for f in flows])}

        class Q:
            def __init__(self):
                self.conn = conn

            def characterize_flows(self, fl, method):
                return {"total": {"value": sum(r["amount"] for r in fl.values()), "unit": "x"}}

        eng = SimpleNamespace(q=Q(), fmap=None, method="m",
                              region=SimpleNamespace(code="GH", climate_zone="wet tropical"))
        res = SimpleNamespace(contribution_flows_by_source={}, inventory={}, contribution={},
                              contribution_by_source={}, impacts={}, notes=[])
        farm_flows.apply(res, eng, a)
    finally:
        conn.close()
    po4 = [f for f in flows if f["name"].startswith("Phosphate")]
    assert {cats[f["uid"]] for f in po4} == {"Elementary flows/Emission to water/ground water",
                                             "Elementary flows/Emission to water/surface water"}
    assert sum(f["amount"] for f in po4) == pytest.approx(
        (0.07 * 3 + 0.175 * (1 + 0.2 / 80 * 15) * 3) * 94.971 / 30.974)
    # SOC is attached separately and never enters the inventory
    assert res.soc_management["booked"] and res.soc_management["value"] < 0
    assert not any("soil" in (r.get("name") or "").lower() for r in res.inventory.values())
