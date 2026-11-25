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

Field emissions are NOT one shared multiplier: the on-farm flows are split into parameter
groups (N2O via EF1, nitrate via FracLEACH, NH3 via FracGASF, rice CH4 via EFc, land
occupation, other) and each group is sampled from its own IPCC 2019 range (FIELD_PARAMETERS),
independently, when the engine can characterise the groups separately.

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
    from .pedigree import (BASIC_UNCERTAINTY, field_scores, gsd_from_pedigree, land_scores,
                           match_scores)
except ImportError:
    from adapter import MIDPOINT_MAP, single_score
    from pedigree import (BASIC_UNCERTAINTY, field_scores, gsd_from_pedigree, land_scores,
                          match_scores)

# IPCC 2019 Refinement 95 % ranges for the Tier-1 field parameters, used as triangular
# (lower, mode = default, upper) distributions on a multiplier of the modelled flow. A
# triangular form is used because several lower bounds are zero (not representable by a
# lognormal); the mode is the IPCC default, so the sampled median sits slightly off 1 for
# skewed ranges (disclosed). Indirect N2O (EF4, EF5) is merged with direct N2O in the
# inventory and is therefore sampled with the EF1 range (perfectly correlated, disclosed).
FIELD_PARAMETERS: dict[str, dict] = {
    "EF1_wet": {"default": 0.016, "range": (0.013, 0.019),
                "source": "IPCC 2019 Vol 4 Ch 11 Table 11.1, EF1 synthetic N, wet climate"},
    "EF1_dry": {"default": 0.005, "range": (0.000, 0.011),
                "source": "IPCC 2019 Vol 4 Ch 11 Table 11.1, EF1 all N inputs, dry climate"},
    "EF1_aggregated": {"default": 0.010, "range": (0.001, 0.018),
                       "source": "IPCC 2019 Vol 4 Ch 11 Table 11.1, EF1 aggregated default"},
    "FracLEACH": {"default": 0.24, "range": (0.01, 0.73),
                  "source": "IPCC 2019 Vol 4 Ch 11 Table 11.3, FracLEACH-(H)"},
    "FracGASF": {"default": 0.11, "range": (0.02, 0.33),
                 "source": "IPCC 2019 Vol 4 Ch 11 Table 11.3, FracGASF aggregated"},
    "EFc_rice": {"default": 1.19, "range": (0.80, 1.76),
                 "source": "IPCC 2019 Vol 4 Ch 5 Table 5.11, rice CH4 baseline EFc (kg CH4/ha/day)"},
    # FracGASF by fertiliser type, IPCC 2019 Vol 4 Ch 11 Table 11.3 (values as used by the
    # kernel, african_lca_backend; ranges from the same table).
    "FracGASF_urea": {"default": 0.15, "range": (0.03, 0.43),
                      "source": "IPCC 2019 Vol 4 Ch 11 Table 11.3, FracGASF urea"},
    "FracGASF_ammonium": {"default": 0.08, "range": (0.02, 0.30),
                          "source": "IPCC 2019 Vol 4 Ch 11 Table 11.3, FracGASF ammonium-based"},
    "FracGASF_nitrate": {"default": 0.01, "range": (0.00, 0.02),
                         "source": "IPCC 2019 Vol 4 Ch 11 Table 11.3, FracGASF nitrate-based"},
    "FracGASF_AN": {"default": 0.05, "range": (0.00, 0.20),
                    "source": "IPCC 2019 Vol 4 Ch 11 Table 11.3, FracGASF ammonium-nitrate-based"},
    "FracGASM": {"default": 0.21, "range": (0.00, 0.31),
                 "source": "IPCC 2019 Vol 4 Ch 11 Table 11.3, FracGASM organic N"},
}


def _fertiliser_class(ftype: str) -> str | None:
    t = (ftype or "").lower()
    if not t or t == "none":
        return None
    if "urea" in t:
        return "FracGASF_urea"
    if "ammonium nitrate" in t or "can" == t.strip() or "calcium ammonium" in t:
        return "FracGASF_AN"
    if "ammonium" in t or "dap" in t or "map" in t or "sulphate of ammonia" in t:
        return "FracGASF_ammonium"
    if "nitrate" in t:
        return "FracGASF_nitrate"
    return "FracGASF"          # NPK / unknown N form -> aggregated


def _nh3_parameter(assessment: dict | None) -> str:
    """Per-type FracGASF range when all declared synthetic N is one class; FracGASM when
    only organic N (compost/manure) is declared; otherwise the aggregated FracGASF range."""
    if not assessment:
        return "FracGASF"
    mp = assessment.get("management_practices") or {}
    rows = ((mp.get("fertilization") or {}).get("fertilizer_applications")) or []
    classes = {_fertiliser_class(r.get("fertilizer_type") or r.get("type") or "")
               for r in rows if (r.get("application_rate") or 0) > 0}
    classes.discard(None)
    organic = bool((mp.get("soil_management") or {}).get("uses_compost"))
    if not classes:
        return "FracGASM" if organic else "FracGASF"
    if len(classes) == 1 and not organic:
        return classes.pop()
    return "FracGASF"

# Field-flow name keyword -> parameter group. Names are the kernel/flowmap keys stored in
# the field source (e.g. "N2O", "NO3", "NH3", "CH4_bio", "land_occ") or store names.
_FIELD_GROUP_RULES = (
    ("N2O", ("n2o", "dinitrogen monoxide", "nox", "nitrogen oxides")),   # NOx = 0.21 x N2O
    ("NO3", ("no3", "nitrate")),
    ("NH3", ("nh3", "ammonia")),
    ("CH4", ("ch4", "methane")),
    ("land", ("land_occ", "occupation", "transformation")),
)


def _field_group(name: str) -> str:
    low = (name or "").lower()
    for group, keys in _FIELD_GROUP_RULES:
        if any(low.startswith(k) or k in low for k in keys):
            return group
    return "other"


def _ef1_parameter(engine) -> str:
    region = getattr(engine, "region", None)
    zone = (getattr(region, "climate_zone", "") or "").lower()
    if zone.startswith("dry"):
        return "EF1_dry"
    if zone.startswith("wet"):
        return "EF1_wet"
    return "EF1_aggregated"


def _group_parameter(group: str, engine, assessment: dict | None = None) -> str | None:
    return {"N2O": _ef1_parameter(engine), "NO3": "FracLEACH", "NH3": _nh3_parameter(assessment),
            "CH4": "EFc_rice"}.get(group)


def _triangular_multiplier(rng: np.random.Generator, param: str, n: int) -> np.ndarray:
    p = FIELD_PARAMETERS[param]
    d = p["default"]
    lo, hi = p["range"]
    if d <= 0:
        return np.ones(n)
    return rng.triangular(lo / d, 1.0, hi / d, size=n)


def field_group_contributions(result, engine, total_kg: float, categories: list[str]) -> dict:
    """Split the field source into parameter groups, each characterised separately with
    the engine's method, per kg, rescaled so the groups sum to the field source's own
    per-category contribution. Returns {} when the engine cannot characterise flows."""
    flows = (getattr(result, "contribution_flows_by_source", None) or {}).get(FIELD_SOURCE_LABEL) or {}
    q = getattr(engine, "q", None)
    if not flows or q is None or not hasattr(q, "characterize_flows"):
        return {}
    grouped: dict[str, dict] = {}
    for uid, r in flows.items():
        grouped.setdefault(_field_group(r.get("name") or ""), {})[uid] = r
    per_kg = total_kg or 1.0
    out: dict[str, dict[str, float]] = {}
    try:
        for g, gf in grouped.items():
            imp = q.characterize_flows(gf, engine.method) or {}
            d: dict[str, float] = {}
            for eng_cat, v in imp.items():
                front = _ENGINE_TO_FRONT.get(eng_cat)
                if front in categories:
                    d[front] = d.get(front, 0.0) + (v.get("value") or 0.0) / per_kg
            out[g] = d
    except Exception:
        return {}
    field_src = _source_contributions(result, total_kg, categories).get(FIELD_SOURCE_LABEL, {})
    for cat in categories:
        s = sum(out[g].get(cat, 0.0) for g in out)
        target = field_src.get(cat)
        if s and target is not None:
            for g in out:
                if cat in out[g]:
                    out[g][cat] *= target / s
    return out

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
    assessment: dict | None = None,
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

    # Field source -> parameter groups with their own distributions, when available.
    groups = field_group_contributions(result, engine, total_kg, categories)
    field_params_used: dict[str, str] = {}
    if groups and FIELD_SOURCE_LABEL in contribs:
        contribs.pop(FIELD_SOURCE_LABEL)
        field_gsd = gsds.pop(FIELD_SOURCE_LABEL, None)
        for g, d in groups.items():
            key = f"{FIELD_SOURCE_LABEL} :: {g}"
            contribs[key] = d
            param = _group_parameter(g, engine, assessment)
            if param:
                field_params_used[key] = param
            elif g == "land":
                gsds[key] = gsd_from_pedigree(land_scores(), BASIC_UNCERTAINTY["measured_area"])
            else:
                gsds[key] = field_gsd or gsd_from_pedigree(field_scores(), BASIC_UNCERTAINTY["field_ef"])
    # Stable source order so sampling is deterministic regardless of dict ordering.
    sources = sorted(contribs)

    rng = np.random.default_rng(seed)
    src_mult = {}
    for src in sources:
        if src in field_params_used:
            src_mult[src] = _triangular_multiplier(rng, field_params_used[src], n)
        else:
            src_mult[src] = _lognormal(rng, gsds.get(src, GSD_BY_CLASS["measured_match"]), n)
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
        "field_parameter_distributions": {
            src: {"parameter": p, "distribution": "triangular",
                  "default": FIELD_PARAMETERS[p]["default"], "range": list(FIELD_PARAMETERS[p]["range"]),
                  "source": FIELD_PARAMETERS[p]["source"]}
            for src, p in sorted(field_params_used.items())},
        "percentiles": percentiles,
        "single_score": {"p5": float(sp5), "p50": float(sp50), "p95": float(sp95)},
        "basis": (
            "Each purchased-input source scored on the ecoinvent v3 pedigree matrix "
            "(Weidema et al. 2013 Table 10.5 variances: reliability, completeness, temporal / "
            "geographical / technological correlation) plus a basic-uncertainty term, giving a "
            "per-source lognormal GSD. "
            + ("On-farm field flows are split by parameter and sampled from IPCC 2019 ranges "
               "(triangular: EF1 for N2O incl. indirect N2O, FracLEACH for nitrate, FracGASF for "
               "NH3, EFc for rice CH4); land occupation is treated as near-certain (reported "
               "area). " if field_params_used else
               "On-farm field emissions share one pedigree lognormal (per-flow split unavailable "
               "for this result). ")
            + "Sources sampled independently and category totals re-summed, without re-solving "
            "the LCI. Screening scope: characterization-factor uncertainty is not propagated, so "
            "p5-p95 reflects inventory (activity and emission-factor) magnitude only."
        ),
    }


def one_at_a_time_sensitivity(result, midpoints: dict, engine, total_kg: float,
                              yield_change: float = 0.20) -> dict:
    """Packaged one-at-a-time (OAT) sensitivity on the per-kg results, no LCI re-solve.

    * EF1 and FracLEACH at their IPCC 2019 low / high bounds: rescale the N2O and nitrate
      field groups (linear Tier-1 model). Indirect N2O from leaching is in the N2O group and
      is not moved by the FracLEACH case (understates that case; disclosed).
    * Yield ±`yield_change`: per-kg results scale by 1/(1 ± change) with inputs held fixed
      (residue-N feedback ignored; a screening bound).
    * Method: the same merged inventory re-characterised with the other default method
      (ReCiPe 2016 midpoint (H) vs EF v3.1); climate change per kg is compared."""
    cats = [c for c in midpoints if c != "Biodiversity loss"]
    base = {c: (midpoints[c].get("value") or 0.0) for c in cats}
    cases: list[dict] = []
    groups = field_group_contributions(result, engine, total_kg, cats)

    def _case(name, param, bound, group, factor):
        d = groups.get(group) or {}
        if not d:
            return
        delta = {c: d.get(c, 0.0) * (factor - 1.0) for c in cats}
        res = {c: base[c] + delta[c] for c in cats}
        cases.append({
            "case": name, "parameter": param, "value": bound,
            "source": FIELD_PARAMETERS[param]["source"],
            "global_warming_change_pct": (100.0 * delta.get("Global warming", 0.0) / base["Global warming"]
                                          if base.get("Global warming") else None),
            "changes_pct": {c: (100.0 * delta[c] / base[c]) for c in cats if base[c] and delta[c]},
            "result": res,
        })

    ef1 = _ef1_parameter(engine)
    p = FIELD_PARAMETERS[ef1]
    for label, bound in (("low", p["range"][0]), ("high", p["range"][1])):
        _case(f"EF1 {label}", ef1, bound, "N2O", bound / p["default"])
    p = FIELD_PARAMETERS["FracLEACH"]
    for label, bound in (("low", p["range"][0]), ("high", p["range"][1])):
        _case(f"FracLEACH {label}", "FracLEACH", bound, "NO3", bound / p["default"])

    for sign, label in ((+1, "+"), (-1, "-")):
        f = 1.0 / (1.0 + sign * yield_change)
        cases.append({"case": f"yield {label}{yield_change*100:.0f}%", "parameter": "yield",
                      "value": 1.0 + sign * yield_change,
                      "source": "functional-unit denominator (inputs held fixed)",
                      "global_warming_change_pct": 100.0 * (f - 1.0),
                      "changes_pct": {c: 100.0 * (f - 1.0) for c in cats if base[c]},
                      "result": {c: base[c] * f for c in cats}})

    method_case = None
    q = getattr(engine, "q", None)
    inv = getattr(result, "inventory", None) or {}
    cur = getattr(engine, "method", "") or ""
    other = ("ReCiPe 2016 v1.03, midpoint (H)" if ("EF" in cur and "ReCiPe" not in cur)
             else "EF v3.1")
    if q is not None and hasattr(q, "characterize_flows") and inv:
        try:
            imp = q.characterize_flows(inv, other) or {}
            gw = next((v.get("value") for k, v in imp.items() if k == "Climate change"), None)
            if gw is not None:
                gw_kg = gw / (total_kg or 1.0)
                method_case = {
                    "current_method": cur, "alternative_method": other,
                    "global_warming_current": base.get("Global warming"),
                    "global_warming_alternative": gw_kg,
                    "change_pct": (100.0 * (gw_kg - base["Global warming"]) / base["Global warming"]
                                   if base.get("Global warming") else None),
                    "note": ("Same inventory re-characterised. ReCiPe 2016 (H) uses AR5 GWP100 incl. "
                             "climate-carbon feedback (N2O 298, CH4 34), EF 3.1 uses AR6 (N2O 273, "
                             "CH4 27.0); on-site refrigerant, allocation and AWARE adjustments made "
                             "after characterisation are not re-applied in this comparison."),
                }
        except Exception:
            method_case = None
    return {
        "method": "one-at-a-time (OAT), linear Tier-1 rescaling of the cached result",
        "cases": cases,
        "method_sensitivity": method_case,
        "note": ("No LCI re-solve: field-parameter cases rescale the N2O / nitrate field groups "
                 "linearly (Tier-1 is linear in EF1 and FracLEACH); indirect N2O moves with EF1 "
                 "only. Yield cases hold all inputs fixed."),
    }


def apply_mc_to_midpoints(midpoints: dict, mc: dict) -> None:
    """Replace flat uncertainty_range on midpoints with MC p5-p95 (in place)."""
    for cat, pct in (mc.get("percentiles") or {}).items():
        slot = midpoints.get(cat)
        if not slot:
            continue
        slot["uncertainty_range"] = [pct["p5"], pct["p95"]]
