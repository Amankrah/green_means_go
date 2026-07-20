#!/usr/bin/env python3
"""
uncertainty.py: pedigree screening Monte Carlo for farm and facility assessments.

Each contribution source (a matched purchased input, or the IPCC-modelled on-farm field
emissions) is scored on the Weidema/ecoinvent pedigree matrix and gets its OWN geometric
standard deviation (see pedigree.py). Every source is then sampled INDEPENDENTLY with a
lognormal multiplier (median 1), and a source's draw scales its contribution across every
impact category at once (an input's activity-amount uncertainty is shared across the
categories it drives, but is independent of other inputs). Category totals are re-summed
from the sampled sources, so intra-class correlation is no longer forced to 1 the way a
single per-class multiplier did.

Screening scope: this samples inventory (activity + emission-factor) magnitude only.
Characterization-factor uncertainty is NOT propagated (disclosed in the basis string and
the ISO limitations). The LCI is not re-solved per iteration.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

try:
    from .adapter import MIDPOINT_MAP, single_score
    from .pedigree import BASIC_UNCERTAINTY, field_scores, gsd_from_pedigree, match_scores
except ImportError:
    from adapter import MIDPOINT_MAP, single_score
    from pedigree import BASIC_UNCERTAINTY, field_scores, gsd_from_pedigree, match_scores

DEFAULT_N = 1000  # screening MC default: stabilises the p5/p95 tail percentiles

# Retained for backward compatibility / coarse study-level summaries. The live sampler no
# longer uses these; per-source GSDs come from the pedigree matrix (see pedigree.py).
GSD_BY_CLASS = {
    "measured_match": 1.10,
    "estimated_activity": 1.30,
    "field_ef": 1.80,
}

FIELD_SOURCE_LABEL = "Field emissions (on-farm)"

_ENGINE_TO_FRONT = {eng: front for eng, (front, _unit) in MIDPOINT_MAP.items()}


def _is_field_source(src: str) -> bool:
    low = (src or "").lower()
    return src == FIELD_SOURCE_LABEL or "field emission" in low


def classify_match(match: dict) -> str:
    """Classify one input_matches row into a coarse data class (kept for callers/tests)."""
    if match.get("estimated") is True:
        return "estimated_activity"
    kind = (match.get("kind") or "").lower()
    name = str(match.get("matched") or match.get("input") or "").lower()
    if "field" in kind or "emission" in kind or "n2o" in name or "on-farm" in name:
        return "field_ef"
    if match.get("matched"):
        return "measured_match"
    return "estimated_activity"


def _match_gsd(match: dict, region_name: str) -> float:
    """Per-source GSD from the pedigree matrix for a matched purchased input."""
    basic = BASIC_UNCERTAINTY["estimated"] if match.get("estimated") else BASIC_UNCERTAINTY["background"]
    return gsd_from_pedigree(match_scores(match, region_name), basic)


def study_gsd(input_matches: list | None, region_name: str = "") -> float:
    """Aggregate study GSD: geometric mean of per-input pedigree GSDs. Higher when inputs
    are estimated / poorly matched, so estimated studies read as more uncertain."""
    matches = list(input_matches or [])
    if not matches:
        return _match_gsd({}, region_name)
    logs = [math.log(_match_gsd(m, region_name)) for m in matches]
    return math.exp(sum(logs) / len(logs))


def _region_name(result, engine) -> str:
    region = getattr(engine, "region", None)
    return (getattr(region, "name", None) or getattr(result, "region", None) or "") or ""


def _source_gsds(result, region_name: str) -> dict[str, float]:
    """GSD per contribution source, from the pedigree matrix."""
    matches_by_input = {
        m.get("input"): m for m in (getattr(result, "input_matches", None) or []) if isinstance(m, dict)
    }
    out: dict[str, float] = {}
    for src in (getattr(result, "contribution_by_source", None) or {}):
        if _is_field_source(src):
            out[src] = gsd_from_pedigree(field_scores(), BASIC_UNCERTAINTY["field_ef"])
        else:
            out[src] = _match_gsd(matches_by_input.get(src) or {}, region_name)
    return out


def _source_contributions(result, total_kg: float, categories: list[str]) -> dict[str, dict[str, float]]:
    """Per source, its per-kg contribution to each (frontend-named) category."""
    per_kg = total_kg or 1.0
    out: dict[str, dict[str, float]] = {}
    for src, impacts in (getattr(result, "contribution_by_source", None) or {}).items():
        d: dict[str, float] = {}
        for eng_cat, v in (impacts or {}).items():
            front = _ENGINE_TO_FRONT.get(eng_cat, eng_cat)
            if front in categories:
                d[front] = d.get(front, 0.0) + (v.get("value") or 0.0) / per_kg
        out[src] = d
    return out


def _lognormal(rng: np.random.Generator, gsd: float, n: int) -> np.ndarray:
    return rng.lognormal(mean=0.0, sigma=math.log(gsd) if gsd > 1 else 0.0, size=n)


def run_pedigree_mc(
    result,
    midpoints: dict,
    engine=None,
    total_kg: float = 1.0,
    *,
    n: int = DEFAULT_N,
    seed: int = 42,
) -> dict[str, Any]:
    """Run per-source pedigree screening Monte Carlo; return a percentile summary."""
    categories = [
        c for c in midpoints
        if c != "Biodiversity loss" and (midpoints[c].get("value") or 0.0) != 0.0
    ]
    if not categories:
        categories = [c for c in midpoints if c != "Biodiversity loss"]

    region_name = _region_name(result, engine)
    contribs = _source_contributions(result, total_kg, categories)
    gsds = _source_gsds(result, region_name)
    # Stable source order so sampling is deterministic regardless of dict ordering.
    sources = sorted(contribs)

    rng = np.random.default_rng(seed)
    src_mult = {src: _lognormal(rng, gsds.get(src, GSD_BY_CLASS["measured_match"]), n) for src in sources}
    # Fallback multiplier for a category with no attributed sources (e.g. only in midpoints).
    study_g = study_gsd(getattr(result, "input_matches", None), region_name)
    fallback_mult = _lognormal(rng, study_g, n)

    samples: dict[str, np.ndarray] = {}
    for cat in categories:
        base = float(midpoints[cat].get("value") or 0.0)
        contribution_sum = sum(contribs[src].get(cat, 0.0) for src in sources)
        if contribution_sum > 0:
            arr = np.zeros(n, dtype=float)
            for src in sources:
                c = contribs[src].get(cat, 0.0)
                if c:
                    arr = arr + c * src_mult[src]
            # Anchor to the reported midpoint: the per-source contributions may not sum
            # exactly to it (grid calibration, cut-off flows), so scale the whole sample.
            if base:
                arr = arr * (base / contribution_sum)
        elif base:
            arr = base * fallback_mult
        else:
            arr = np.zeros(n, dtype=float)
        samples[cat] = arr

    percentiles: dict[str, dict[str, float]] = {}
    for cat in categories:
        p5, p50, p95 = np.percentile(samples[cat], [5, 50, 95])
        percentiles[cat] = {
            "p5": float(p5),
            "p50": float(p50),
            "p95": float(p95),
            "base": float(midpoints[cat].get("value") or 0.0),
        }

    method = getattr(engine, "method", None) or ""
    single_draws = []
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
        "method": "pedigree screening Monte Carlo (per-source, Weidema/ecoinvent matrix)",
        "gsd": study_g,
        "gsd_by_source": {src: round(g, 3) for src, g in sorted(gsds.items())},
        "gsd_by_class": dict(GSD_BY_CLASS),
        "percentiles": percentiles,
        "single_score": {"p5": float(sp5), "p50": float(sp50), "p95": float(sp95)},
        "basis": (
            "Each source scored on the ecoinvent 2013 pedigree matrix (reliability, "
            "completeness, temporal / geographical / technological correlation) plus a "
            "basic-uncertainty term, giving a per-source lognormal GSD; sources sampled "
            "independently and category totals re-summed, without re-solving the LCI. "
            "Screening scope: characterization-factor uncertainty is not propagated, so "
            "p5-p95 reflects inventory (activity and emission-factor) magnitude only."
        ),
    }


def apply_mc_to_midpoints(midpoints: dict, mc: dict) -> None:
    """Replace flat uncertainty_range on midpoints with MC p5-p95 (in place)."""
    for cat, pct in (mc.get("percentiles") or {}).items():
        slot = midpoints.get(cat)
        if not slot:
            continue
        slot["uncertainty_range"] = [pct["p5"], pct["p95"]]
