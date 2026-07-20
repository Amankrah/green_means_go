#!/usr/bin/env python3
"""
uncertainty.py — pedigree screening Monte Carlo for farm assessments.

Assigns a geometric standard deviation (GSD) by data class, then samples lognormal
multipliers at category level (one draw scales all contributions in a pedigree class)
so the LCI is not re-solved each iteration.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

try:
    from .adapter import MIDPOINT_MAP, single_score
except ImportError:
    from adapter import MIDPOINT_MAP, single_score

DEFAULT_N = 500

# Screening GSD by pedigree data class (median multiplier = 1).
GSD_BY_CLASS = {
    "measured_match": 1.05,       # matched background dataset, operator-supplied amount
    "estimated_activity": 2.0,    # activity defaults (see ghana_farm_activity_defaults.json)
    "field_ef": 1.5,              # IPCC Tier 1 field emission factors
}

FIELD_SOURCE_LABEL = "Field emissions (on-farm)"

_ENGINE_TO_FRONT = {eng: front for eng, (front, _unit) in MIDPOINT_MAP.items()}


def classify_match(match: dict) -> str:
    """Classify one input_matches row (used by tests and study-level helpers)."""
    if match.get("estimated") is True:
        return "estimated_activity"
    kind = (match.get("kind") or "").lower()
    name = str(match.get("matched") or match.get("input") or "").lower()
    if "field" in kind or "emission" in kind or "n2o" in name or "on-farm" in name:
        return "field_ef"
    if match.get("matched"):
        return "measured_match"
    return "estimated_activity"


def study_gsd(input_matches: list | None) -> float:
    """Aggregate study GSD as geometric mean of per-input class GSDs."""
    matches = list(input_matches or [])
    if not matches:
        return GSD_BY_CLASS["estimated_activity"]
    logs = [math.log(GSD_BY_CLASS[classify_match(m)]) for m in matches]
    return math.exp(sum(logs) / len(logs))


def _classify_sources(result) -> dict[str, str]:
    """Map each contribution source label to a pedigree data class."""
    estimated = {
        m.get("input")
        for m in (getattr(result, "input_matches", None) or [])
        if m.get("estimated")
    }
    out: dict[str, str] = {}
    for src in (getattr(result, "contribution_by_source", None) or {}):
        low = (src or "").lower()
        if src == FIELD_SOURCE_LABEL or "field emission" in low:
            out[src] = "field_ef"
        elif src in estimated:
            out[src] = "estimated_activity"
        else:
            out[src] = "measured_match"
    return out


def _category_decomposition(result, total_kg: float, frontend_categories: list[str]) -> dict[str, dict[str, float]]:
    """Per frontend category, split the per-kg total into pedigree-class parts."""
    per_kg = total_kg or 1.0
    classes = _classify_sources(result)
    decomp = {cat: {k: 0.0 for k in GSD_BY_CLASS} for cat in frontend_categories}
    for src, impacts in (getattr(result, "contribution_by_source", None) or {}).items():
        cls = classes.get(src, "measured_match")
        for eng_cat, v in impacts.items():
            front = _ENGINE_TO_FRONT.get(eng_cat)
            if not front or front not in decomp:
                continue
            decomp[front][cls] += (v.get("value") or 0.0) / per_kg
    return decomp


def _lognormal_multipliers(rng: np.random.Generator, gsd: float, n: int) -> np.ndarray:
    """Sample n multipliers with median 1 and the given GSD."""
    sigma = math.log(gsd)
    return rng.lognormal(mean=0.0, sigma=sigma, size=n)


def run_pedigree_mc(
    result,
    midpoints: dict,
    engine=None,
    total_kg: float = 1.0,
    *,
    n: int = DEFAULT_N,
    seed: int = 42,
) -> dict[str, Any]:
    """Run category-level pedigree screening Monte Carlo; return percentile summary."""
    categories = [
        c for c in midpoints
        if c != "Biodiversity loss" and (midpoints[c].get("value") or 0.0) != 0.0
    ]
    if not categories:
        categories = [c for c in midpoints if c != "Biodiversity loss"]

    decomp = _category_decomposition(result, total_kg, categories)
    rng = np.random.default_rng(seed)

    class_mult = {
        cls: _lognormal_multipliers(rng, gsd, n)
        for cls, gsd in GSD_BY_CLASS.items()
    }

    samples: dict[str, np.ndarray] = {}
    for cat in categories:
        parts = decomp.get(cat) or {}
        total = (
            parts.get("field_ef", 0.0) * class_mult["field_ef"]
            + parts.get("estimated_activity", 0.0) * class_mult["estimated_activity"]
            + parts.get("measured_match", 0.0) * class_mult["measured_match"]
        )
        samples[cat] = total

    percentiles: dict[str, dict[str, float]] = {}
    for cat in categories:
        arr = samples[cat]
        p5, p50, p95 = np.percentile(arr, [5, 50, 95])
        percentiles[cat] = {
            "p5": float(p5),
            "p50": float(p50),
            "p95": float(p95),
            "base": float(midpoints[cat].get("value") or 0.0),
        }

    method = getattr(engine, "method", None) or ""
    single_draws: list[float] = []
    for i in range(n):
        trial = {
            cat: {"value": float(samples[cat][i]), "unit": (midpoints[cat].get("unit") or "")}
            for cat in categories
        }
        sc, _meta = single_score(trial, {}, method)
        single_draws.append(sc)
    sarr = np.asarray(single_draws, dtype=float)
    sp5, sp50, sp95 = np.percentile(sarr, [5, 50, 95])

    return {
        "n": n,
        "seed": seed,
        "method": "pedigree screening Monte Carlo (category-level scaling)",
        "gsd": study_gsd(getattr(result, "input_matches", None)),
        "gsd_by_class": dict(GSD_BY_CLASS),
        "percentiles": percentiles,
        "single_score": {"p5": float(sp5), "p50": float(sp50), "p95": float(sp95)},
        "basis": (
            "Category totals scaled lognormally by pedigree data class "
            "(measured match / estimated activity / field EF) without re-solving the LCI."
        ),
        "decomposition": decomp,
    }


def apply_mc_to_midpoints(midpoints: dict, mc: dict) -> None:
    """Replace flat uncertainty_range on midpoints with MC p5–p95 (in place)."""
    for cat, pct in (mc.get("percentiles") or {}).items():
        slot = midpoints.get(cat)
        if not slot:
            continue
        slot["uncertainty_range"] = [pct["p5"], pct["p95"]]
