#!/usr/bin/env python3
"""
pedigree.py: Weidema/ecoinvent data-quality pedigree matrix, used to derive a per-source
geometric standard deviation (GSD) for the screening Monte Carlo.

Instead of three hand-set class GSDs, each contribution source is scored on the five
pedigree indicators (reliability, completeness, temporal / geographical / further
technological correlation) from what we actually know about the match (estimated flag,
match similarity, region fit, IPCC-modelled field emission), and combined with a
basic-uncertainty term the ecoinvent way:

    sigma_g = exp( sqrt( ln(UF_basic)^2 + sum_i ln(UF_i)^2 ) )

The indicator uncertainty factors are the ecoinvent 2013 defaults (Weidema et al., "Data
quality guideline for the ecoinvent database version 3", Table 10.4). This is a screening
approximation, not a full inventory MC: characterization-factor uncertainty is NOT included
(disclosed in the MC basis string and the ISO limitations).
"""
from __future__ import annotations

import math

# Uncertainty factors per indicator, scores 1 (best) .. 5 (worst). ecoinvent 2013 defaults.
PEDIGREE_UF: dict[str, list[float]] = {
    "reliability":   [1.00, 1.05, 1.10, 1.20, 1.50],
    "completeness":  [1.00, 1.02, 1.05, 1.10, 1.20],
    "temporal":      [1.00, 1.03, 1.10, 1.20, 1.50],
    "geographical":  [1.00, 1.01, 1.02, 1.10, 1.50],
    "technological": [1.00, 1.10, 1.20, 1.50, 2.00],
}

# Basic uncertainty (GSD) before pedigree, by the kind of source. Field emission factors
# (IPCC Tier 1) carry the largest intrinsic spread: the IPCC 2019 EF1 default of 0.01 with
# a 0.001-0.018 range implies a lognormal GSD near 2.1 for direct N2O. 1.90 here, combined
# with the field pedigree scores below, lands the field source's aggregate GSD near 2.0,
# reflecting that on-farm emissions dominate farm-LCA uncertainty.
BASIC_UNCERTAINTY: dict[str, float] = {
    "field_ef":   1.90,   # IPCC Tier-1 field emission factors (N2O EF1 spread)
    "estimated":  1.20,   # operator amount was an activity default, not reported
    "background": 1.10,   # a matched ecoinvent-style background dataset
}


def _clamp_score(s: int) -> int:
    return 1 if s < 1 else 5 if s > 5 else int(s)


def gsd_from_pedigree(scores: dict[str, int], basic_gsd: float) -> float:
    """Combine indicator scores + basic uncertainty into a geometric SD (median 1)."""
    var = math.log(basic_gsd) ** 2
    for indicator, table in PEDIGREE_UF.items():
        s = _clamp_score(scores.get(indicator, 1))
        var += math.log(table[s - 1]) ** 2
    return math.exp(math.sqrt(var))


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
