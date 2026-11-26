#!/usr/bin/env python3
"""
test_grid_calibration.py - proves the grid-EF correction lands climate on the official
national factor and moves NO other impact category.

Needs the canonical store (data/canonical/*.sqlite). Skips cleanly if it isn't present.

Run:  python3 test_grid_calibration.py   (from engine/)
"""
from __future__ import annotations

import glob
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import grid_calibration
from regions import get_region
from ingestion.query import CanonicalQuery


def _store() -> str | None:
    hits = glob.glob("data/canonical/*.sqlite") or glob.glob(
        str(Path(__file__).resolve().parents[1] / "data" / "canonical" / "*.sqlite"))
    return hits[0] if hits else None


def _climate(d):
    return next(v["value"] for c, v in d.items() if c.lower().startswith("climate change")
                and ":" not in c)


def _gh_setup():
    db = _store()
    if not db:
        return None
    q = CanonicalQuery(db)
    gh = get_region("GH")
    uid = sqlite3.connect(db).cursor().execute(
        "select uid from processes where name like 'Electricity, low voltage {GH}%' limit 1"
    ).fetchone()[0]
    return q, gh, gh.default_method, uid


def test_calibration_co2_only_mode_is_climate_only(monkeypatch=None) -> int:
    s = _gh_setup()
    if not s:
        print("[skip] canonical store not present")
        return 0
    q, gh, method, uid = s
    import os
    old = os.environ.get("GRID_CALIBRATION_MODE")
    os.environ["GRID_CALIBRATION_MODE"] = "co2_only"
    try:
        sc = q.cradle_to_gate(uid, amount=1.0)
        before = q.characterize_flows(sc.elementary_flows, method)
        info = grid_calibration.apply(q, {"kind": "electricity", "amount": 1.0},
                                      sc.elementary_flows, gh, method)
        after = q.characterize_flows(sc.elementary_flows, method)
    finally:
        if old is None:
            os.environ.pop("GRID_CALIBRATION_MODE", None)
        else:
            os.environ["GRID_CALIBRATION_MODE"] = old
    assert info is not None and info["mode"] == "co2_only"
    assert abs(_climate(after) - 0.35) < 1e-6
    moved = [c for c, vb in before.items() if "climate" not in c.lower()
             and abs((after.get(c, {}).get("value") or 0.0) - vb["value"]) > 1e-9]
    assert not moved, f"co2_only calibration moved non-climate categories: {moved}"
    return 0


def test_calibration_scales_down_when_dataset_exceeds_official() -> int:
    s = _gh_setup()
    if not s:
        print("[skip] canonical store not present")
        return 0
    q, gh, method, uid = s
    sc = q.cradle_to_gate(uid, amount=1.0)
    before = q.characterize_flows(sc.elementary_flows, method)
    info = grid_calibration.apply(q, {"kind": "electricity", "amount": 1.0},
                                  sc.elementary_flows, gh, method)
    after = q.characterize_flows(sc.elementary_flows, method)
    assert info is not None, "calibration did not fire for GH grid electricity"
    assert _climate(before) > 0.35, "ecoinvent GH low voltage (per kWh) is above the 0.35 factor"
    assert info["mode"] == "proportional_down"
    assert abs(_climate(after) - 0.35) < 1e-6, f"climate landed at {_climate(after)}, not 0.35"
    return 0


def test_calibration_thermal_topup_moves_copollutants() -> int:
    s = _gh_setup()
    if not s:
        print("[skip] canonical store not present")
        return 0
    q, gh, method, uid = s
    # 1 kWh solved but declared as 2 kWh: the target (0.70 kg CO2e) exceeds the dataset, so the
    # gap is filled with gas generation
    sc = q.cradle_to_gate(uid, amount=1.0)
    before = q.characterize_flows(sc.elementary_flows, method)
    info = grid_calibration.apply(q, {"kind": "electricity", "amount": 2.0},
                                  sc.elementary_flows, gh, method)
    after = q.characterize_flows(sc.elementary_flows, method)
    assert info is not None and info["mode"] == "thermal_topup"
    assert abs(_climate(after) - 0.70) < 1e-6, f"climate landed at {_climate(after)}, not 0.70"
    # gas generation brings NOx (photochemical ozone, acidification) and fossil resource use
    for key in ("Photochemical oxidant formation: human health", "Energy resources: non-renewable, fossil"):
        if key in before:
            assert after[key]["value"] > before[key]["value"], key
    return 0


def test_calibration_region_without_factor_untouched() -> int:
    s = _gh_setup()
    if not s:
        print("[skip] canonical store not present")
        return 0
    q, gh, method, uid = s

    # a region with no official EF (Canada) is left untouched
    sc2 = q.cradle_to_gate(uid, amount=1.0)
    none_info = grid_calibration.apply(q, {"kind": "electricity", "amount": 1.0},
                                       sc2.elementary_flows, get_region("CA"), method)
    assert none_info is None, "calibration fired for a region with no official EF"
    return 0


if __name__ == "__main__":
    test_calibration_co2_only_mode_is_climate_only()
    test_calibration_scales_down_when_dataset_exceeds_official()
    test_calibration_thermal_topup_moves_copollutants()
    sys.exit(test_calibration_region_without_factor_untouched())
