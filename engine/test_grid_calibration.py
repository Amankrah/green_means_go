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


def test_calibration_is_climate_only() -> int:
    db = _store()
    if not db:
        print("[skip] canonical store not present")
        return 0
    q = CanonicalQuery(db)
    gh = get_region("GH")
    method = gh.default_method
    uid = sqlite3.connect(db).cursor().execute(
        "select uid from processes where name like 'Electricity, low voltage {GH}%' limit 1"
    ).fetchone()[0]

    sc = q.cradle_to_gate(uid, amount=1.0)
    before = q.characterize_flows(sc.elementary_flows, method)
    info = grid_calibration.apply(q, {"kind": "electricity", "amount": 1.0},
                                  sc.elementary_flows, gh, method)
    after = q.characterize_flows(sc.elementary_flows, method)

    def climate(d):
        return next(v["value"] for c, v in d.items() if "climate" in c.lower())

    assert info is not None, "calibration did not fire for GH grid electricity"
    assert abs(climate(after) - 0.35) < 1e-6, f"climate landed at {climate(after)}, not 0.35"
    assert climate(before) < 0.35, "expected ecoinvent GH to understate before calibration"

    # every non-climate category is byte-identical
    moved = []
    for cat, vb in before.items():
        if "climate" in cat.lower():
            continue
        va = after.get(cat, {}).get("value")
        if va is None or abs(va - vb["value"]) > 1e-9:
            moved.append(cat)
    assert not moved, f"calibration moved non-climate categories: {moved}"

    # a region with no official EF (Canada) is left untouched
    sc2 = q.cradle_to_gate(uid, amount=1.0)
    none_info = grid_calibration.apply(q, {"kind": "electricity", "amount": 1.0},
                                       sc2.elementary_flows, get_region("CA"), method)
    assert none_info is None, "calibration fired for a region with no official EF"

    print(f"[ok] GH grid electricity climate {climate(before):.4f} -> {climate(after):.4f} "
          f"(official 0.35); {len(before)-1} other categories unchanged; CA untouched")
    return 0


if __name__ == "__main__":
    sys.exit(test_calibration_is_climate_only())
