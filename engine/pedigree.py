#!/usr/bin/env python3
"""
pedigree.py: Weidema/ecoinvent data-quality pedigree matrix, used to derive a per-source
geometric standard deviation (GSD) for the screening Monte Carlo.

Instead of three hand-set class GSDs, each contribution source is scored on the five
pedigree indicators (reliability, completeness, temporal / geographical / further
technological correlation) from what we actually know about the match (estimated flag,
match similarity, region fit, IPCC-modelled field emission), and combined with a
basic-uncertainty term the ecoinvent v3 way (Weidema et al. 2013, "Data quality guideline
for the ecoinvent database version 3", ecoinvent Report 1 (v3), §10.2, Eq. 10.1 and
Table 10.5; Muller et al. 2016, Int J LCA 21:1327):

    sigma^2 = sigma_b^2 + sum_i sigma_i^2          (variances of ln(x))
    GSD     = exp(sigma)

The pedigree additions sigma_i^2 are tabulated by Weidema et al. 2013 Table 10.5 directly as
variances of the underlying normal. They equal (ln U_i / 2)^2 of the older ecoinvent v2
uncertainty factors U_i (Frischknecht et al. 2007), because those U_i were factors on the
SQUARED geometric standard deviation (the 95 % interval, GSD^2). The previous code summed
ln(U_i)^2 and treated the result as GSD, i.e. it used the 95 % factor as a 1-sigma factor and
over-stated every pedigree term's sigma by 2x ("squared twice"). Example: reliability score
5, U = 1.50 -> (ln 1.5 / 2)^2 = 0.041 = Table 10.5's 0.04.

This is a screening approximation, not a full inventory MC: characterization-factor
uncertainty is NOT included (disclosed in the MC basis string and the ISO limitations).
"""
from __future__ import annotations

import math

# Pedigree variance additions sigma_i^2 (variance of ln x), scores 1 (best) .. 5 (worst).
# Weidema et al. 2013, ecoinvent v3 data quality guideline, Table 10.5.
PEDIGREE_VARIANCE: dict[str, list[float]] = {
    "reliability":   [0.0, 0.0006, 0.002, 0.008, 0.04],
    "completeness":  [0.0, 0.0001, 0.0006, 0.002, 0.008],
    "temporal":      [0.0, 0.0002, 0.002, 0.008, 0.04],
    "geographical":  [0.0, 0.000025, 0.0001, 0.0006, 0.002],
    "technological": [0.0, 0.0006, 0.008, 0.04, 0.12],
}
# Equivalent v2-style uncertainty factors on GSD^2 (U = exp(2*sqrt(variance))), kept for
# callers/tests that display them.
PEDIGREE_UF: dict[str, list[float]] = {
    k: [round(math.exp(2.0 * math.sqrt(v)), 3) for v in vals] for k, vals in PEDIGREE_VARIANCE.items()
}

# Basic uncertainty, as a true 1-sigma GSD (sigma_b = ln GSD_b), by the kind of source.
# These are screening judgements, not tabulated values. "field_ef" now applies only to the
# field flows that have no parameter-specific IPCC range (see uncertainty.FIELD_PARAMETERS:
# N2O, NO3, NH3, rice CH4 and land occupation get their own distributions); 1.90 reflects
# the IPCC 2019 EF1 default 0.010 with a 0.001-0.018 95 % range (Table 11.1).
BASIC_UNCERTAINTY: dict[str, float] = {
    "field_ef":   1.90,   # IPCC Tier-1 field emission factors (N2O EF1 spread)
    "estimated":  1.20,   # operator amount was an activity default, not reported
    "background": 1.10,   # a matched ecoinvent-style background dataset
    "measured_area": 1.0,  # farmer-reported area x 1 year (land occupation): pedigree only
}


def _clamp_score(s: int) -> int:
    return 1 if s < 1 else 5 if s > 5 else int(s)


def gsd_from_pedigree(scores: dict[str, int], basic_gsd: float) -> float:
    """Combine indicator scores + basic uncertainty into a geometric SD (median 1):
    sigma^2 = ln(GSD_b)^2 + sum of Weidema 2013 Table 10.5 variances."""
    var = math.log(basic_gsd) ** 2 if basic_gsd > 0 else 0.0
    for indicator, table in PEDIGREE_VARIANCE.items():
        s = _clamp_score(scores.get(indicator, 1))
        var += table[s - 1]
    return math.exp(math.sqrt(var))


def land_scores() -> dict[str, int]:
    """Land occupation = farmer-reported area x one year: reliability 2 (reported, not
    verified), otherwise exact for this farm."""
    return {"reliability": 2, "completeness": 1, "temporal": 1, "geographical": 1,
            "technological": 1}


def field_scores() -> dict[str, int]:
    """Pedigree scores for IPCC-modelled on-farm field emissions: reliable method but
    modelled (not measured on site), recent, region-adjusted, technology-generic."""
    return {
        "reliability": 4,     # modelled from a documented method, not measured here
        "completeness": 2,
        "temporal": 2,
        "geographical": 2,    # climate-adjusted for the region
        "technological": 3,
    }


def match_scores(match: dict, region_name: str) -> dict[str, int]:
    """Pedigree scores for a matched purchased input, derived from the match metadata."""
    estimated = bool(match.get("estimated"))
    sim = match.get("score")            # semantic match similarity in [0, 1]
    sim = float(sim) if isinstance(sim, (int, float)) else None
    location = str(match.get("location") or "").lower()
    rn = (region_name or "").lower()
    region_specific = bool(rn) and (location == rn or location.startswith(rn) or rn in location)

    # Reliability: verified match vs an estimated activity amount.
    reliability = 4 if estimated else 2
    # Completeness: an estimated amount is a weaker representation of the real activity.
    completeness = 3 if estimated else 2
    # Temporal: backgrounds are the current ecoinvent release.
    temporal = 2
    # Geographical: a region-specific dataset (e.g. the national grid) vs a RoW/GLO proxy.
    geographical = 1 if region_specific else 4
    # Further technological correlation: driven by how good the semantic match is.
    if sim is None:
        technological = 3
    elif sim >= 0.8:
        technological = 2
    elif sim >= 0.65:
        technological = 3
    else:
        technological = 4
    return {
        "reliability": reliability,
        "completeness": completeness,
        "temporal": temporal,
        "geographical": geographical,
        "technological": technological,
    }
