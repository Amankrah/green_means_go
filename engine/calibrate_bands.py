#!/usr/bin/env python3
"""
calibrate_bands.py — derive the single-score band thresholds EMPIRICALLY instead of
hardcoding them.

Rationale: there is no standard Low/Moderate/High cutoff for a ReCiPe single score in
the literature, and ISO 14044 (§4.4.3.3) flags weighting-based single scores as value
choices. So a defensible band must be *relative to a benchmark*: we compute our own
single score for a basket of farm-gate crop products, run through the IDENTICAL pipeline
(cradle-to-gate solve -> ReCiPe 2016 midpoint (H) characterization -> normalization),
and set the band cutoffs at the distribution's tertiles.

Basket: ecoinvent 3.11 "<crop> production" processes, 1 kg reference at farm gate,
"Cutoff, U". Pure ecoinvent so every score is ReCiPe-exact (no nomenclature bridge).
The reference product must be the crop itself (not "straw"/"seed for sowing", which are
co-product-allocation artifacts), and we prefer a Rest-of-World / Global location for
representativeness, falling back deterministically.

Output: engine/single_score_bands.json — the basket, each product's µPt/kg score, and
the derived cutoffs, with full provenance so the thresholds are auditable and regenerate
if the basket or pipeline changes. adapter.single_score() loads this file.

Run:  python -m engine.calibrate_bands       (from repo root)
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
from engine.adapter import MIDPOINT_MAP, RECIPE_NF, single_score  # noqa: E402

METHOD = "ReCiPe 2016 v1.03, midpoint (H)"
BANDS_FILE = Path(__file__).resolve().parent / "single_score_bands.json"

# crop label -> (name substring to search, token the reference product must contain)
# The reference-product token screens out straw/seed co-products sharing a process name.
BASKET = {
    "maize grain":          ("maize grain production", "maize grain"),
    "wheat grain":          ("wheat grain production", "wheat grain"),
    "rice (non-basmati)":   ("rice production, non-basmati", "rice, non-basmati"),
    "potato":               ("potato production", "potato"),
    "soybean":              ("soybean production", "soybean"),
    "sugarcane":            ("sugarcane production", "sugarcane"),
    "barley grain":         ("barley grain production", "barley grain"),
    "sunflower seed":       ("sunflower production", "sunflower seed"),
    "rye grain":            ("rye production", "rye grain"),
    "oat grain":            ("oat grain production", "oat grain"),
    "tomato (open field)":  ("tomato production, fresh grade, open field", "tomato"),
    "onion":                ("onion production", "onion"),
    "carrot":               ("carrot production", "carrot"),
    "white cabbage":        ("white cabbage production", "white cabbage"),
    "banana":               ("banana production", "banana"),
    "rape seed":            ("rape seed production", "rape seed"),
    "fava bean":            ("fava bean production", "fava bean"),
    "sweet sorghum grain":  ("sweet sorghum production", "sweet sorghum grain"),
    "millet":               ("millet production", "millet"),
    "protein pea":          ("protein pea production", "protein pea"),
}

# location preference for a representative single pick
_LOC_RANK = {"Rest of World": 0, "RoW": 0, "Global": 1, "GLO": 1}


def _pick(conn: sqlite3.Connection, name_like: str, ref_token: str):
    """Choose one ecoinvent kg-reference process whose reference product matches the
    crop, preferring a RoW/Global location, else deterministic (sorted)."""
    rows = conn.execute(
        "SELECT uid, name, location FROM processes "
        "WHERE source_id=2 AND name LIKE ? AND name LIKE '%production%'",
        (f"%{name_like}%",),
    ).fetchall()
    cands = []
    for r in rows:
        ref = conn.execute(
            "SELECT unit, flow_name FROM exchanges "
            "WHERE process_uid=? AND is_reference=1 LIMIT 1", (r["uid"],),
        ).fetchone()
        if not ref or (ref["unit"] or "").lower() not in ("kg", "kilogram"):
            continue
        fn = (ref["flow_name"] or "").lower()
        if ref_token.lower() not in fn:
            continue
        if "organic" in (r["name"] or "").lower():   # baseline = conventional
            continue
        cands.append(r)
    if not cands:
        return None
    cands.sort(key=lambda r: (_LOC_RANK.get(r["location"] or "", 9), r["name"], r["uid"]))
    return cands[0]


def _score_product(q: CanonicalQuery, uid: str) -> tuple[float, dict]:
    """cradle-to-gate (per kg) -> ReCiPe midpoints -> single score µPt/kg."""
    res = q.cradle_to_gate(uid, METHOD, amount=1.0)   # amount=1.0 => per kg
    midpoints: dict = {}
    for cat, v in res.impacts.items():
        m = MIDPOINT_MAP.get(cat)
        if m:
            midpoints[m[0]] = {"value": v["value"]}
    micro, meta = single_score(midpoints, {})
    return micro, meta.get("contributions", {})


def _percentile(sorted_vals: list[float], p: float) -> float:
    """Linear-interpolation percentile (p in [0,1]) over a pre-sorted list."""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    idx = p * (len(sorted_vals) - 1)
    lo = int(idx)
    frac = idx - lo
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def calibrate(write: bool = True) -> dict:
    conn = sqlite3.connect(str(DEFAULT_DB))
    conn.row_factory = sqlite3.Row
    q = CanonicalQuery(DEFAULT_DB)
    basket = []
    for label, (name_like, ref_token) in BASKET.items():
        p = _pick(conn, name_like, ref_token)
        if not p:
            print(f"  MISS  {label:22s} (no ecoinvent kg farm-gate match)")
            continue
        try:
            micro, _ = _score_product(q, p["uid"])
        except Exception as e:
            print(f"  FAIL  {label:22s} {type(e).__name__}: {e}")
            continue
        basket.append({"crop": label, "uid": p["uid"], "process": p["name"],
                       "location": p["location"], "single_score_upt_per_kg": round(micro, 2)})
        print(f"  OK    {label:22s} {micro:8.1f} µPt/kg  [{p['location']}]")
    conn.close(); q.close()

    vals = sorted(b["single_score_upt_per_kg"] for b in basket)
    t33 = _percentile(vals, 1 / 3)
    t67 = _percentile(vals, 2 / 3)
    # round to 2 significant-ish figures for a clean, human-readable threshold
    low_cut = round(t33, -1)
    high_cut = round(t67, -1)
    out = {
        "methodology": (
            "Empirical band calibration: single score computed for a benchmark basket of "
            "ecoinvent 3.11 farm-gate crop products (1 kg, Cutoff) through the identical "
            "pipeline (cradle-to-gate solve -> ReCiPe 2016 v1.03 midpoint (H) -> "
            "normalization). Bands are the basket's tertiles: Low = below the 33rd "
            "percentile, Moderate = 33rd-67th, High = above the 67th percentile."),
        "method": METHOD,
        "n_products": len(basket),
        "low_cut_upt_per_kg": low_cut,
        "high_cut_upt_per_kg": high_cut,
        "percentiles": {"p33": round(t33, 1), "p67": round(t67, 1),
                        "min": vals[0] if vals else None, "max": vals[-1] if vals else None,
                        "median": round(_percentile(vals, 0.5), 1) if vals else None},
        "basket": sorted(basket, key=lambda b: b["single_score_upt_per_kg"]),
    }
    if write:
        BANDS_FILE.write_text(json.dumps(out, indent=2))
        print(f"\nwrote {BANDS_FILE}")
    print(f"\nn={out['n_products']}  Low<{low_cut}  Moderate<{high_cut}  High>={high_cut}  (µPt/kg)")
    print(f"distribution: min={vals[0]:.0f}  p33={t33:.0f}  median={_percentile(vals,0.5):.0f}  "
          f"p67={t67:.0f}  max={vals[-1]:.0f}")
    return out


if __name__ == "__main__":
    calibrate()
