#!/usr/bin/env python3
"""
calibrate_process_bands.py — empirical Low/Moderate/High band thresholds for PROCESSED-FOOD
single scores, the processing counterpart to calibrate_bands.py.

Farm-gate crop scores are not comparable to processed-product scores (a processed product
carries its raw material plus the processing), so the processor report needs its own
benchmark. We compute the single score for a basket of ecoinvent 3.11 processed-food
products (1 kg, Cutoff) through the IDENTICAL pipeline and set the cutoffs at the tertiles.

Output: engine/process_single_score_bands.json (same shape as single_score_bands.json).
Run:  python -m engine.calibrate_process_bands   (from repo root)
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ingestion.canonical_store import DEFAULT_DB           # noqa: E402
from ingestion.query import CanonicalQuery                  # noqa: E402
from engine.adapter import MIDPOINT_MAP, single_score       # noqa: E402
from engine.calibrate_bands import _percentile              # noqa: E402  (reuse)

METHOD = "ReCiPe 2016 v1.03, midpoint (H)"
BANDS_FILE = Path(__file__).resolve().parent / "process_single_score_bands.json"

# label -> (name substring, reference-product token). The token screens co-products that
# share a process name (whey, buttermilk, meal).
BASKET = {
    "maize starch":     ("maize starch production", "maize starch"),
    "glucose":          ("glucose production", "glucose"),
    "soybean oil":      ("soybean meal and crude oil production, mechanical extraction", "soybean oil, crude"),
    "butter":           ("butter production, from cow milk", "butter, from cow milk"),
    "cheese (soft)":    ("cheese production, soft, from cow milk", "cheese, from cow milk"),
    "breadcrumbs":      ("breadcrumbs production", "breadcrumbs"),
    "sugar (beet)":     ("sugar production, from sugar beet", "sugar"),
    "sugar (cane)":     ("sugar production, from sugarcane", "sugar"),
    "rape oil":         ("rape oil production", "rape oil"),
    "palm oil":         ("palm oil production", "palm oil"),
    "margarine":        ("margarine production", "margarine"),
    "fatty acid":       ("fatty acid production, from vegetable oil", "fatty acid"),
    "wheat flour mix":  ("batter wheat mix production", "wheat flour mix"),
    "potato starch":    ("potato starch production", "potato starch"),
    "wheat starch":     ("wheat starch production", "wheat starch"),
    "isolated soy protein": ("protein production, isolated, soy", "protein"),
    "beer":             ("beer production", "beer"),
    "wine":             ("wine production", "wine"),
    "fish fillet":      ("fish fillet production", "fish"),
    "chocolate":        ("dark chocolate production", "chocolate"),
}

_EXCLUDE = ("treatment of", "market for", "market group", "residues", "sewage", "bottom ash",
            "waste ", "wastewater", "organic")
_LOC_RANK = {"Rest of World": 0, "RoW": 0, "Global": 1, "GLO": 1}


def _pick(conn: sqlite3.Connection, name_like: str, ref_token: str):
    rows = conn.execute(
        "SELECT uid, name, location FROM processes "
        "WHERE source_id=2 AND name LIKE ? AND name LIKE '%production%'",
        (f"%{name_like}%",),
    ).fetchall()
    cands = []
    for r in rows:
        nm = (r["name"] or "").lower()
        if any(x in nm for x in _EXCLUDE):
            continue
        ref = conn.execute(
            "SELECT unit, flow_name FROM exchanges WHERE process_uid=? AND is_reference=1 LIMIT 1",
            (r["uid"],)).fetchone()
        if not ref or (ref["unit"] or "").lower() not in ("kg", "kilogram"):
            continue
        if ref_token.lower() not in (ref["flow_name"] or "").lower():
            continue
        cands.append(r)
    if not cands:
        return None
    cands.sort(key=lambda r: (_LOC_RANK.get(r["location"] or "", 9), r["name"], r["uid"]))
    return cands[0]


def _score_product(q: CanonicalQuery, uid: str) -> float:
    res = q.cradle_to_gate(uid, METHOD, amount=1.0)
    midpoints = {MIDPOINT_MAP[c][0]: {"value": v["value"]}
                 for c, v in res.impacts.items() if c in MIDPOINT_MAP}
    micro, _ = single_score(midpoints, {})
    return micro


def calibrate(write: bool = True) -> dict:
    conn = sqlite3.connect(str(DEFAULT_DB)); conn.row_factory = sqlite3.Row
    q = CanonicalQuery(DEFAULT_DB)
    basket = []
    for label, (name_like, ref_token) in BASKET.items():
        p = _pick(conn, name_like, ref_token)
        if not p:
            print(f"  MISS  {label:22s}")
            continue
        try:
            micro = _score_product(q, p["uid"])
        except Exception as e:
            print(f"  FAIL  {label:22s} {type(e).__name__}: {e}")
            continue
        basket.append({"product": label, "uid": p["uid"], "process": p["name"],
                       "location": p["location"], "single_score_upt_per_kg": round(micro, 2)})
        print(f"  OK    {label:22s} {micro:8.1f} µPt/kg  [{p['location']}]")
    conn.close(); q.close()

    vals = sorted(b["single_score_upt_per_kg"] for b in basket)
    t33, t67 = _percentile(vals, 1/3), _percentile(vals, 2/3)
    out = {
        "methodology": (
            "Empirical band calibration for processed-food products: single score computed for a "
            "benchmark basket of ecoinvent 3.11 processed-food products (1 kg, Cutoff) through the "
            "identical pipeline (cradle-to-gate solve -> ReCiPe 2016 v1.03 midpoint (H) -> "
            "normalization). Bands are the basket's tertiles."),
        "method": METHOD, "n_products": len(basket),
        "low_cut_upt_per_kg": round(t33, -1), "high_cut_upt_per_kg": round(t67, -1),
        "percentiles": {"p33": round(t33, 1), "p67": round(t67, 1),
                        "min": vals[0] if vals else None, "max": vals[-1] if vals else None,
                        "median": round(_percentile(vals, 0.5), 1) if vals else None},
        "basket": sorted(basket, key=lambda b: b["single_score_upt_per_kg"]),
    }
    if write:
        BANDS_FILE.write_text(json.dumps(out, indent=2))
        print(f"\nwrote {BANDS_FILE}")
    print(f"\nn={out['n_products']}  Low<{out['low_cut_upt_per_kg']}  "
          f"Moderate<{out['high_cut_upt_per_kg']}  High  (µPt/kg)")
    return out


if __name__ == "__main__":
    calibrate()
