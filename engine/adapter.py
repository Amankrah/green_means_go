#!/usr/bin/env python3
"""
adapter.py — map the validated engine's output (whole-farm midpoint impacts, ReCiPe
category names) into the AssessmentResponse shape the existing frontend renders
(per-kg midpoints with the frontend's category names, endpoints, per-crop breakdown,
a transparent single score, data quality).

This lets us swap the Rust hardcoded-LCIA served path for the validated pipeline
without touching the frontend.
"""
from __future__ import annotations

# ReCiPe/EF category name  ->  (frontend category name, display unit)
MIDPOINT_MAP = {
    "Climate change":                               ("Global warming", "kg CO2-eq"),
    "Global warming":                               ("Global warming", "kg CO2-eq"),
    "Water consumption":                            ("Water consumption", "m3"),
    "Water use":                                    ("Water consumption", "m3"),
    "Land use":                                     ("Land use", "m2a crop-eq"),
    "Terrestrial acidification":                    ("Terrestrial acidification", "kg SO2-eq"),
    "Acidification: terrestrial":                   ("Terrestrial acidification", "kg SO2-eq"),   # ReCiPe 2016 name in the ecoinvent 3.11 pack
    "Acidification":                                ("Terrestrial acidification", "mol H+-eq"),
    "Eutrophication: freshwater":                   ("Freshwater eutrophication", "kg P-eq"),
    "Eutrophication, freshwater":                   ("Freshwater eutrophication", "kg P-eq"),
    "Eutrophication: marine":                       ("Marine eutrophication", "kg N-eq"),
    "Eutrophication, marine":                       ("Marine eutrophication", "kg N-eq"),
    "Fossil resource scarcity":                     ("Fossil depletion", "kg oil-eq"),
    "Energy resources: non-renewable, fossil":      ("Fossil depletion", "kg oil-eq"),   # ReCiPe 2016
    "Energy resources: non-renewable":              ("Fossil depletion", "MJ"),          # EF 3.1
    "Mineral resource scarcity":                    ("Mineral depletion", "kg Cu-eq"),
    "Material resources: metals/minerals":          ("Mineral depletion", "kg Sb-eq"),
    "Particulate matter formation":                 ("Particulate matter formation", "kg PM2.5-eq"),
    "Particulate matter":                           ("Particulate matter formation", "disease inc."),
    "Photochemical oxidant formation: human health": ("Photochemical oxidation", "kg NOx-eq"),
    "Photochemical ozone formation: human health":  ("Photochemical oxidation", "kg NMVOC-eq"),
    # ReCiPe 2016 terrestrial-ecosystem ozone (reported; not in the 10-category ReCiPe sum).
    "Photochemical oxidant formation: terrestrial ecosystems":
        ("Photochemical oxidation, terrestrial ecosystems", "kg NOx-eq"),
    # EF 3.1 terrestrial eutrophication (accumulated exceedance, mol N-eq).
    "Eutrophication: terrestrial":                  ("Terrestrial eutrophication", "mol N-eq"),
    # Toxicity / ozone depletion / ionising radiation: in the EF 3.1 weighted score (all 16
    # EF categories); reported but outside the ReCiPe equal-weighted 10-category sum.
    "Ecotoxicity: freshwater":                      ("Freshwater ecotoxicity", "kg 1,4-DCB-eq"),
    "Ecotoxicity: terrestrial":                     ("Terrestrial ecotoxicity", "kg 1,4-DCB-eq"),
    "Ecotoxicity: marine":                          ("Marine ecotoxicity", "kg 1,4-DCB-eq"),
    "Human toxicity: carcinogenic":                 ("Human toxicity, cancer", "kg 1,4-DCB-eq"),
    "Human toxicity: non-carcinogenic":             ("Human toxicity, non-cancer", "kg 1,4-DCB-eq"),
    "Ozone depletion":                              ("Ozone depletion", "kg CFC-11-eq"),
    "Ionising radiation":                           ("Ionising radiation", "kBq Co-60-eq"),
    "Ionising radiation: human health":             ("Ionising radiation", "kBq U235-eq"),
}
# Sub-indicators the store also returns (EF climate change split, EF toxicity organics /
# inorganics). They are components of a reported total, so they are deliberately not
# mapped to their own midpoint (that would double count in any sum); listed here so the
# "unmapped category" check below knows they were considered.
MIDPOINT_SUBINDICATORS = {
    "Climate change: fossil", "Climate change: biogenic",
    "Climate change: land use and land use change",
    "Human toxicity: carcinogenic, organics", "Human toxicity: carcinogenic, inorganics",
    "Human toxicity: non-carcinogenic, organics", "Human toxicity: non-carcinogenic, inorganics",
    "Ecotoxicity: freshwater, organics", "Ecotoxicity: freshwater, inorganics",
}


def is_ef_method(method: str | None) -> bool:
    m = method or ""
    return ("EF" in m) and ("ReCiPe" not in m)

# Separate AWARE water-scarcity midpoint reported for EVERY method (engine/water_scarcity.py).
AWARE_MIDPOINT = "Water scarcity (AWARE)"

SOURCES = ["ecoinvent 3.11 (supply chain)", "IPCC 2019 AFOLU (field emissions)",
           "ReCiPe 2016 / EF 3.1 (characterization)"]


def _provenance(engine, method: str) -> dict:
    """Reproducibility stamp (engine build, dataset editions, method, field model)."""
    try:
        from .provenance import build_provenance
    except ImportError:
        from provenance import build_provenance
    return build_provenance(engine, method)


def _norm_unit(unit) -> str:
    """Lightly tidy a store unit for display (keep it authoritative — it must match the
    number). e.g. 'kg CO2-Eq' -> 'kg CO2-eq', 'm2*a crop-Eq' -> 'm2a crop-eq'."""
    if not unit:
        return ""
    return str(unit).replace("-Eq", "-eq").replace("*a", "a").replace("m2*", "m2")


def _midpoint(value_per_kg: float, unit: str, uncertainty_range=None) -> dict:
    if uncertainty_range is None:
        uncertainty_range = [value_per_kg * 0.7, value_per_kg * 1.4]  # pedigree ~±30/40%
    return {
        "value": value_per_kg,
        "unit": unit,
        "uncertainty_range": uncertainty_range,
        "data_quality_score": 0.8,
        "contributing_sources": SOURCES,
    }


def _endpoints(engine, inventory: dict, method: str) -> dict:
    """Characterize with the matching ReCiPe endpoint method and aggregate to the three
    areas of protection by unit (DALY / species.yr / USD)."""
    ep_method = method.replace("midpoint", "endpoint") if "midpoint" in method else None
    out = {"Human Health": 0.0, "Ecosystem Quality": 0.0, "Resource Scarcity": 0.0}
    units = {"Human Health": "DALY", "Ecosystem Quality": "species.yr", "Resource Scarcity": "USD2013"}
    if not ep_method or not engine.q.find_method(ep_method):
        return {}
    imp = engine.characterize(inventory, ep_method)
    # The method has both per-impact sub-categories AND "Total:" roll-ups per area.
    # Use ONLY the roll-ups when present, else sum the sub-categories — never both,
    # or the areas double-count.
    has_totals = any(c.lower().startswith("total:") for c in imp)
    for cat, v in imp.items():
        if has_totals and not cat.lower().startswith("total:"):
            continue
        u = (v.get("unit") or "").lower()
        if "daly" in u:
            out["Human Health"] += v["value"]
        elif "species" in u:
            out["Ecosystem Quality"] += v["value"]
        elif "usd" in u or "$" in u:
            out["Resource Scarcity"] += v["value"]
    return {k: {"value": val, "unit": units[k],
                "uncertainty_range": [val * 0.5, val * 2.0]} for k, val in out.items()}


# Midpoint normalisation factors (impact per person per year). LOADED from the derived
# file engine/lcia_reference/normalisation_factors.json, which ingestion/gmg_reference.py
# builds from data/ReCipe2016/Normalization scores ReCiPe2016v1.1_20190514.xlsx (World 2010,
# Hierarchist, midpoint) and, for EF 3.1, from the JRC EF 3.1 normalisation table
# (Andreasson et al. 2024, JRC130796, Table 2; not in the EF 3.1 CF workbook on disk).
# A normalized single score = sum(impact / NF) = person-equivalents, then x1e6 -> uPt.
# The literals below are only the fallback if the derived file is missing; they equal the
# file values (checked by engine/test_normalisation.py).
_RECIPE_NF_FALLBACK = {
    "Global warming": 7990.0,          # kg CO2-eq / person / yr
    "Land use": 6167.0,                # m2a crop-eq
    "Water consumption": 266.6,        # m3
    "Terrestrial acidification": 40.98,  # kg SO2-eq
    "Freshwater eutrophication": 0.6499, # kg P
    "Marine eutrophication": 4.618,      # kg N
    "Fossil depletion": 983.3,         # kg oil-eq (crude+gas+hard+brown coal)
    "Mineral depletion": 1.201e5,      # kg Cu-eq
    "Particulate matter formation": 25.57,  # kg PM2.5
    "Photochemical oxidation": 20.57,       # kg NOx
}


def _load_nf() -> tuple[dict, dict, str]:
    import json as _j
    import os as _o
    path = _o.path.join(_o.path.dirname(__file__), "lcia_reference", "normalisation_factors.json")
    try:
        d = _j.loads(open(path, encoding="utf-8").read())
        return (dict(d["recipe_2016"]["factors"]), dict(d["ef_3_1"]["factors"]),
                "engine/lcia_reference/normalisation_factors.json")
    except (OSError, ValueError, KeyError):
        return dict(_RECIPE_NF_FALLBACK), dict(_EF_NF_FALLBACK), "fallback constants in engine/adapter.py"


def _load_nf_extras() -> tuple[dict, dict]:
    """(EF 3.1 weights as fractions, ReCiPe NFs for categories reported but not summed)."""
    import json as _j
    import os as _o
    path = _o.path.join(_o.path.dirname(__file__), "lcia_reference", "normalisation_factors.json")
    try:
        d = _j.loads(open(path, encoding="utf-8").read())
        w = {k: float(v) / 100.0 for k, v in (d["ef_3_1"].get("weighting_pct") or {}).items()}
        extra = dict(d["recipe_2016"].get("factors_reported_not_in_score") or {})
        return (w or {k: v / 100.0 for k, v in _EF_WEIGHT_PCT_FALLBACK.items()}), extra
    except (OSError, ValueError, KeyError):
        return {k: v / 100.0 for k, v in _EF_WEIGHT_PCT_FALLBACK.items()}, {}


# Band thresholds are calibrated EMPIRICALLY against a benchmark basket of farm-gate
# crop products run through this same pipeline (see engine/calibrate_bands.py). One band
# file PER METHOD, because the two scores are different quantities (ReCiPe equal-weighted
# sum vs EF 3.1 weighted score): single_score_bands.json (ReCiPe) and
# single_score_bands_ef.json (EF 3.1). Low/Moderate/High = below 33rd / 33rd-67th / above
# 67th percentile of the basket. When the method's file is absent the band is reported as
# unavailable (no cutoffs borrowed from the other method).
import json as _json
import os as _os

_BANDS_FILE = _os.path.join(_os.path.dirname(__file__), "single_score_bands.json")
_BANDS_FILE_EF = _os.path.join(_os.path.dirname(__file__), "single_score_bands_ef.json")
_BANDS_CACHE: dict | None = None
_BANDS_CACHE_EF: dict | None = None

# The benchmark basket is ecoinvent crop production, whose field inventories include NH3,
# NOx, phosphorus losses and heavy metals. Until the farm model emits the same set of field
# flows, a farm score is not strictly like-for-like with the basket (likely biased low in
# acidification / eutrophication).
BASKET_CONSISTENCY_NOTE = (
    "The benchmark basket is ecoinvent 3.11 crop production, whose field inventories include "
    "NH3, NOx, phosphorus losses and heavy metals. Field flows that this farm model does not "
    "(yet) emit make the farm result not strictly like-for-like with the basket, most likely "
    "biasing acidification and eutrophication low relative to the bands.")


def _read_bands(path: str, label: str) -> dict | None:
    try:
        d = _json.loads(open(path, encoding="utf-8").read())
        return {
            "low": float(d["low_cut_upt_per_kg"]),
            "high": float(d["high_cut_upt_per_kg"]),
            "calibrated": True,
            "basis": (f"tertiles of {d.get('n_products', '?')} benchmark farm-gate crop "
                      f"products via the identical pipeline ({label})"),
            "percentiles": d.get("percentiles"),
            "method": d.get("method"),
        }
    except (OSError, ValueError, KeyError):
        return None


def _bands(method: str | None = None) -> dict:
    """Calibrated band cutoffs for the method family (cached). ReCiPe falls back to the
    historic indicative 500/1500 defaults; EF never borrows ReCiPe cutoffs."""
    global _BANDS_CACHE, _BANDS_CACHE_EF
    if is_ef_method(method):
        if _BANDS_CACHE_EF is None:
            _BANDS_CACHE_EF = _read_bands(_BANDS_FILE_EF, "EF 3.1 weighted score") or {
                "low": None, "high": None, "calibrated": False, "unavailable": True,
                "basis": ("no EF 3.1 band calibration available (engine/single_score_bands_ef.json "
                          "absent); the band is not reported because ReCiPe-calibrated cutoffs "
                          "do not apply to the EF 3.1 weighted score"),
                "percentiles": None}
        return _BANDS_CACHE_EF
    if _BANDS_CACHE is None:
        _BANDS_CACHE = _read_bands(_BANDS_FILE, "ReCiPe 2016 equal-weighted sum") or {
            "low": 500.0, "high": 1500.0, "calibrated": False,
            "basis": "indicative defaults (no calibration file present)", "percentiles": None}
    return _BANDS_CACHE


# Environmental Footprint (EF) 3.1 global normalization factors, per person per year
# (Andreasson et al. 2024, JRC130796, Table 2). Fallback only; the derived file
# engine/lcia_reference/normalisation_factors.json is authoritative and carries the
# verification against AGRIBALYSE 3.2 published EF 3.1 single scores.
_EF_NF_FALLBACK = {
    "Global warming": 7550.0,            # kg CO2-eq
    "Ozone depletion": 0.0536,           # kg CFC-11-eq
    "Human toxicity, cancer": 1.73e-05,  # CTUh
    "Human toxicity, non-cancer": 1.29e-04,  # CTUh
    "Particulate matter formation": 5.95e-4,  # disease incidence
    "Ionising radiation": 4220.0,        # kBq U235-eq
    "Photochemical oxidation": 40.9,     # kg NMVOC-eq
    "Terrestrial acidification": 55.6,   # mol H+-eq (EF "Acidification")
    "Terrestrial eutrophication": 177.0, # mol N-eq
    "Freshwater eutrophication": 1.61,   # kg P-eq
    "Marine eutrophication": 19.5,       # kg N-eq
    "Freshwater ecotoxicity": 56700.0,   # CTUe
    "Land use": 819000.0,                # dimensionless points (Pt)
    "Water consumption": 11500.0,        # m3 world-eq deprived
    "Fossil depletion": 65000.0,         # MJ
    "Mineral depletion": 0.0636,         # kg Sb-eq
}
# EF 3.0/3.1 weighting incl. robustness, with toxicity (Sala et al. 2018, JRC109878), %.
_EF_WEIGHT_PCT_FALLBACK = {
    "Global warming": 21.06, "Particulate matter formation": 8.96, "Water consumption": 8.51,
    "Fossil depletion": 8.32, "Land use": 7.94, "Mineral depletion": 7.55,
    "Ozone depletion": 6.31, "Terrestrial acidification": 6.20, "Ionising radiation": 5.01,
    "Photochemical oxidation": 4.78, "Terrestrial eutrophication": 3.71,
    "Marine eutrophication": 2.96, "Freshwater eutrophication": 2.80,
    "Human toxicity, cancer": 2.13, "Freshwater ecotoxicity": 1.92,
    "Human toxicity, non-cancer": 1.84,
}


RECIPE_NF, EF_NF, NF_SOURCE = _load_nf()
EF_WEIGHTS, RECIPE_NF_REPORTED = _load_nf_extras()

# ISO 14044:2006 §4.4.5: weighting shall not be used for comparative assertions intended
# to be disclosed to the public. Stated on every single score.
WEIGHTING_DISCLOSURE = (
    "ISO 14044:2006 §4.4.5: weighting is an optional, value-based step and shall not be used "
    "in LCA studies intended to be used in comparative assertions intended to be disclosed to "
    "the public. This single score supports internal hotspot screening and scenario comparison "
    "for the same product only.")

SCORE_LABEL_EF = "EF 3.1 weighted single score"
SCORE_LABEL_RECIPE = ("Equal-weighted normalised midpoint sum (not an official ReCiPe 2016 "
                      "single score)")


def normalised_midpoints(midpoints: dict, method: str | None) -> dict:
    """Person-equivalents per kg for every midpoint with a matching-method NF (including
    categories that are reported but not part of the score)."""
    nfs = dict(EF_NF) if is_ef_method(method) else {**RECIPE_NF, **RECIPE_NF_REPORTED}
    out = {}
    for cat, nf in nfs.items():
        v = (midpoints.get(cat) or {}).get("value")
        if v is not None and nf:
            out[cat] = v / nf
    return out


def single_score(midpoints: dict, ep: dict, method: str = "ReCiPe 2016 v1.03, midpoint (H)",
                 bands: dict | None = None) -> tuple:
    """Normalised single score per kg, method-consistent:

    * EF 3.1: the official EF 3.1 single score = Σ_c (midpoint_c / NF_c) × w_c over the 16
      EF categories, global NFs (Andreasson et al. 2024) and the EF weighting set incl.
      toxicity (Sala et al. 2018), in micro-points (µPt; 1 Pt = one person-year, weighted).
    * ReCiPe 2016: ReCiPe has no official weighting, so this is an EQUAL-weighted sum of
      normalised midpoints over 10 categories (World 2010 H NFs), in µPt, a screening
      aggregate, labelled as such, not an official ReCiPe single score.

    Also returns a qualitative band whose cutoffs come from the METHOD's own calibration
    file; when none exists the band is "Unavailable". `bands` overrides the farm-gate
    benchmark (e.g. processed-food bands); it must have the shape of _bands()."""
    is_ef = is_ef_method(method)
    nf_set = EF_NF if is_ef else RECIPE_NF
    weights = {c: EF_WEIGHTS.get(c, 0.0) for c in nf_set} if is_ef else {c: 1.0 for c in nf_set}
    total = 0.0
    per_cat: dict = {}
    missing: list = []
    for cat, nf in nf_set.items():
        v = midpoints.get(cat, {}).get("value")
        if v is not None and nf:
            per_cat[cat] = (v / nf) * weights[cat]
            total += per_cat[cat]
        else:
            missing.append(cat)
    used = list(per_cat)
    micro = total * 1e6   # µPt per kg
    # Each category's SHARE of the single score (what actually drives it).
    contributions = {c: (pe / total if total else 0.0) for c, pe in per_cat.items()}
    b = bands or _bands(method)
    if b.get("low") is None or b.get("high") is None:
        band = "Unavailable"
    else:
        band = ("Low" if micro < b["low"] else "Moderate" if micro < b["high"] else "High")
    band_basis = b["basis"]
    if b.get("calibrated"):
        band_basis += ". " + BASKET_CONSISTENCY_NOTE
    if is_ef:
        label = SCORE_LABEL_EF
        methodology = (
            f"EF 3.1 single score = Σ(midpoint ÷ EF 3.1 global normalisation factor × EF 3.1 "
            f"weighting factor) over {len(used)} of the 16 EF 3.1 categories, in micro-points "
            f"(µPt) per kg product. Normalisation: Andreasson et al. 2024 (JRC130796, Table 2); "
            f"weighting: EF 3.0/3.1 set incl. robustness and toxicity (Sala et al. 2018, "
            f"JRC109878), e.g. climate change 21.06 %, particulate matter 8.96 %, water use "
            f"8.51 %. 1e6 µPt ≈ one person's weighted annual footprint.")
    else:
        label = SCORE_LABEL_RECIPE
        methodology = (
            f"Equal-weighted normalised midpoint sum = Σ(midpoint ÷ ReCiPe 2016 [World 2010, "
            f"Hierarchist] normalisation factor) over {len(used)} categories, each weighted "
            f"1, in micro-person-equivalents (µPt) per kg product. ReCiPe 2016 publishes no "
            f"weighting set, so this is a screening aggregate and NOT an official ReCiPe single "
            f"score. Toxicity, ozone depletion, ionising radiation and terrestrial ozone are "
            f"reported as midpoints but not summed. 1e6 µPt ≈ one person's annual footprint.")
    return micro, {
        "unit": "µPt per kg",
        "label": label,
        "band": band,
        "band_basis": band_basis,
        "band_cutoffs": {"low": b.get("low"), "high": b.get("high"), "calibrated": b.get("calibrated"),
                         "benchmark_min": (b.get("percentiles") or {}).get("min"),
                         "benchmark_max": (b.get("percentiles") or {}).get("max")},
        "person_equivalents_per_kg": total,
        "weighting_factors": {c: weights[c] for c in used},
        "weighting_basis": ("EF 3.1 official weighting (fractions summing to 1 over 16 categories)"
                            if is_ef else "equal weighting (value choice, 1 per category)"),
        "categories_missing": missing,
        "contributions": contributions,                # share of the single score per category
        "methodology": methodology,
        "iso_14044_disclosure": WEIGHTING_DISCLOSURE,
    }


# ---- co-product allocation: grain vs removed straw (ISO 14044:2006 §4.3.4.2) -------------
# Economic allocation needs (a) the straw:grain mass ratio and (b) the grain:straw price
# ratio. (a) IPCC 2019 Refinement Vol 4 Ch 11 Table 11.1A R_AG (above-ground residue d.m. /
# harvested yield d.m.) and DRY (d.m. fraction of the harvested product), the same rows the
# Rust kernel uses (african_lca_backend/src/production/field.rs residue_params). (b) Derived
# from ecoinvent 3.11 cut-off: grain and straw are separately allocated datasets of ONE
# multi-output activity, so for every exchange allocated economically the per-kg amount in
# the grain dataset divided by that in the straw dataset equals p_grain / p_straw. The modal
# ratio (shared by occupation, tillage, sowing, harvesting and pesticide exchanges; nutrient
# and heavy-metal exchanges are allocated by mass balance and differ) was read from the store
# on 2026-11-25. Crops absent here (e.g. maize: no stover co-product in ecoinvent) are NOT
# allocated, and the report says so.
STRAW_ALLOCATION = {
    # crop key: (R_AG, DRY, p_grain/p_straw, ecoinvent datasets the ratio was read from)
    "wheat":  (1.3, 0.89, 29.70, "wheat grain production | wheat grain / | straw, RoW (134 of 143 exchanges)"),
    "rice":   (1.4, 0.89, 30.83, "rice production, non-basmati | rice, non-basmati / | straw, RoW (64 of 76)"),
    "barley": (1.2, 0.89, 9.75,  "barley grain production, Swiss integrated production, intensive, CH (55 of 64)"),
    "oat":    (1.3, 0.89, 18.26, "oat grain production | oat grain / | straw, Canada without Quebec (42 of 47)"),
}
STRAW_ALLOCATION_SOURCE = (
    "Economic allocation (ISO 14044:2006 §4.3.4.2). Straw mass: IPCC 2019 Vol 4 Ch 11 Table "
    "11.1A R_AG x DRY x fraction removed (straw counted as dry matter; no straw moisture "
    "assumed). Price ratio grain:straw per kg: derived from the ecoinvent 3.11 cut-off allocated "
    "grain and straw datasets of the same activity.")
# Residue uses that make removed residue a co-product (sold or fed). Read defensively:
# the request schema does not yet carry this field (requested from B-api / A-frontend).
_COPRODUCT_USES = {"sold", "fed", "fed_to_livestock", "fed_to_own_livestock", "sold_or_fed", "feed"}


def _straw_key(name: str) -> str | None:
    n = (name or "").lower()
    if "buckwheat" in n:
        return None
    for k in ("wheat", "rice", "barley"):
        if k in n:
            return k
    if n == "oat" or n == "oats" or n.startswith("oat ") or n.startswith("oats ") or " oat" in n:
        return "oat"
    return None


def coproduct_allocation(food: dict) -> dict:
    """Grain share of the crop's burden when removed straw is a co-product.

    Returns {"factor": f (1.0 = all burden to the main product), "applied": bool, "note"}."""
    rm = food.get("residue_management") or {}
    try:
        removed = float(rm.get("fraction_removed") or 0.0)
    except (TypeError, ValueError):
        removed = 0.0
    name = food.get("name") or "crop"
    if removed <= 0:
        return {"factor": 1.0, "applied": False, "note": None}
    use = str(rm.get("removed_residue_use") or rm.get("residue_use") or "").strip().lower()
    if use not in _COPRODUCT_USES:
        return {"factor": 1.0, "applied": False, "note": (
            f"{name}: {removed*100:.0f}% of residues removed, but their use (sold / fed) was not "
            "stated, so they are not treated as a co-product and 100% of the burden stays with the "
            "main product.")}
    key = _straw_key(name)
    if key is None:
        return {"factor": 1.0, "applied": False, "note": (
            f"{name}: removed residues are a co-product, but no citable grain:residue price ratio "
            "is available for this crop, so no allocation was applied (100% to the main product).")}
    r_ag, dry, price_ratio, ds = STRAW_ALLOCATION[key]
    straw_per_kg = r_ag * dry * removed            # kg straw d.m. per kg grain (fresh)
    factor = 1.0 / (1.0 + straw_per_kg / price_ratio)
    return {"factor": factor, "applied": True, "straw_kg_dm_per_kg_product": straw_per_kg,
            "price_ratio_main_to_coproduct": price_ratio, "price_ratio_source": f"ecoinvent 3.11: {ds}",
            "note": (f"{name}: economic allocation between grain and removed straw "
                     f"({straw_per_kg:.2f} kg straw d.m. per kg grain; price ratio {price_ratio:g}:1); "
                     f"{factor*100:.1f}% of the crop's burden allocated to the grain. "
                     + STRAW_ALLOCATION_SOURCE)}


REFRIGERANT_SOURCE = "refrigerant leakage (cold storage)"


def _flow_meta(engine, uids) -> dict:
    """{uid: {"compartment", "cas", "flow_type"}} from the store's flows table (best effort)."""
    conn = getattr(getattr(engine, "q", None), "conn", None)
    uids = [u for u in uids if isinstance(u, str)]
    if conn is None or not uids:
        return {}
    out: dict = {}
    try:
        for i in range(0, len(uids), 500):
            chunk = uids[i:i + 500]
            rows = conn.execute(
                f"SELECT uid, category, cas, flow_type FROM flows WHERE uid IN ({','.join('?' * len(chunk))})",
                chunk).fetchall()
            for r in rows:
                cat = r[1] or ""
                comp = cat.replace("Elementary flows/", "", 1) if cat.startswith("Elementary flows/") else cat
                cas = (r[2] or "").strip() or None
                if cas:
                    cas = cas.lstrip("0") or cas     # ecoinvent pads CAS with leading zeros
                out[r[0]] = {"compartment": comp or None, "cas": cas, "flow_type": r[3]}
    except Exception:
        return out
    return out


def _engine_inventory(engine, inventory: dict) -> dict:
    meta = _flow_meta(engine, list(inventory))
    return {uid: {"name": r.get("name"), "unit": r.get("unit"), "amount": r.get("amount"),
                  "compartment": (meta.get(uid) or {}).get("compartment"),
                  "cas": (meta.get(uid) or {}).get("cas")}
            for uid, r in inventory.items()}


def to_assessment_response(result, assessment: dict, engine, total_kg: float,
                           assessment_id: str, extra_notes=None, per_crop=None,
                           run_uncertainty: bool = True,
                           uncertainty_n: int | None = None,
                           uncertainty_seed: int | None = None) -> dict:
    """`result` = whole-farm AssessmentResult (summed impacts + merged inventory).
    `per_crop` (optional) maps crop label -> that crop's OWN AssessmentResult (true
    per-crop product systems); if absent, the breakdown falls back to area allocation."""
    from datetime import datetime, timezone
    total_kg = total_kg or 1.0

    # midpoints: whole-farm -> per kg, mapped to frontend names.
    # NOTE: the unit MUST end in "per kg" — the frontend's isAlreadyPerKg() checks the
    # unit string and, if it lacks "per kg", divides by total production again (which
    # would make every value ~production-times too small).
    midpoints: dict = {}
    for cat, v in result.impacts.items():
        m = MIDPOINT_MAP.get(cat)
        if not m:
            continue
        fname, map_unit = m
        # Prefer the store's actual unit (it must match the number). The same category
        # name can carry different units under different methods (e.g. ReCiPe fossil is
        # kg oil-eq while EF's is MJ), so a hardcoded map unit can mislabel the value.
        unit = _norm_unit(v.get("unit")) or map_unit
        midpoints[fname] = _midpoint(v["value"] / total_kg, f"{unit} per kg")

    # AWARE water scarcity (m3 world-eq deprived) for every method: background with the
    # ecoinvent AWARE CFs, on-farm irrigation with the region's AWARE country CF.
    try:
        from .water_scarcity import aware_indicator
    except ImportError:
        from water_scarcity import aware_indicator
    # EF 3.1 "Water use" IS the AWARE indicator (m3 world-eq deprived), already reported as
    # "Water consumption"; a second AWARE row would show the same quantity twice.
    _ef = is_ef_method(engine.method)
    _aw = None if (_ef and "Water consumption" in midpoints) else \
        aware_indicator(engine, getattr(result, "inventory", None) or {})
    if _aw and _aw["value"]:
        midpoints[AWARE_MIDPOINT] = _midpoint(_aw["value"] / total_kg, f"{_aw['unit']} per kg")
    unmapped = sorted(c for c in result.impacts
                      if c not in MIDPOINT_MAP and c not in MIDPOINT_SUBINDICATORS)

    # On-farm cold-storage refrigerant leakage (CONTRACT §1): charge x IPCC 2006 Table 7.9
    # operating emission factor x GWP100 on the method's basis (engine/refrigerants.py, wrapped
    # by inputs.refrigerant_leakage). Booked as its own climate source, so the per-kg result,
    # the single score, the MC anchor and the contribution analysis all include it.
    try:
        from .inputs import refrigerant_leakage
    except ImportError:
        from inputs import refrigerant_leakage
    # Booked exactly once, here. If an upstream step already booked a refrigerant-leakage
    # source (contribution source or result flag), do not add it again.
    already = bool(getattr(result, "refrigerant_leakage_booked", False)) or any(
        "refrigerant leakage" in (s or "").lower()
        for s in (getattr(result, "contribution_by_source", None) or {}))
    try:
        leak = None if already else refrigerant_leakage(assessment, engine.method)
    except Exception:
        leak = None
    leak_kg_co2e = (leak or {}).get("kg_co2e") or 0.0
    if leak and (leak.get("kg_co2e") or leak.get("note")) and hasattr(result, "__dict__"):
        from types import SimpleNamespace as _NS
        extra_cbs = {}
        if leak.get("kg_co2e"):
            gw = midpoints.get("Global warming")
            if gw:
                midpoints["Global warming"] = _midpoint((gw.get("value") or 0.0) + leak["kg_co2e"] / total_kg,
                                                        gw.get("unit") or "kg CO2-eq per kg")
            extra_cbs[REFRIGERANT_SOURCE] = {"Climate change": {"value": leak["kg_co2e"], "unit": "kg CO2-eq"}}
        result = _NS(**{**vars(result),
                        "contribution_by_source": {**(getattr(result, "contribution_by_source", None) or {}),
                                                   **extra_cbs},
                        "notes": list(getattr(result, "notes", None) or []) + ([leak["note"]] if leak.get("note") else [])
                        + (["refrigerant leakage is added to the climate midpoint and allocated to crops by "
                            "area share; endpoint (damage) results do not include it"]
                           if leak.get("kg_co2e") else [])})

    # endpoints (per kg) via the matching endpoint method
    ep = _endpoints(engine, {u: {**r, "amount": r["amount"] / total_kg}
                             for u, r in result.inventory.items()}, engine.method)

    # Biodiversity card: ReCiPe has no single "biodiversity" midpoint, but the endpoint
    # Ecosystem Quality (species.yr) IS the biodiversity-damage metric. Surface it so the
    # frontend's Biodiversity card shows a real number instead of N/A.
    if ep.get("Ecosystem Quality", {}).get("value"):
        eq = ep["Ecosystem Quality"]["value"]
        midpoints["Biodiversity loss"] = _midpoint(eq, "species.yr per kg")

    # per-crop breakdown: TRUE per-crop systems when provided (each crop's own impacts),
    # else area allocation. Values are crop-TOTALS (the frontend divides by crop kg).
    foods = assessment.get("foods") or []
    total_area = sum((f.get("area_allocated") or 0) for f in foods) or None
    breakdown: dict = {}
    for f in foods:
        qkg = f.get("quantity_kg") or 1.0
        label = f"{f.get('name', 'crop')} ({qkg:.0f}kg)"
        if per_crop and label in per_crop:
            impacts = per_crop[label].impacts                  # crop's own product system
            breakdown[label] = {MIDPOINT_MAP[c][0]: _midpoint(v["value"], _norm_unit(v.get("unit")) or MIDPOINT_MAP[c][1])
                                for c, v in impacts.items() if c in MIDPOINT_MAP}
        else:
            share = ((f.get("area_allocated") or 0) / total_area) if total_area else (1.0 / max(len(foods), 1))
            breakdown[label] = {MIDPOINT_MAP[c][0]: _midpoint(v["value"] * share, _norm_unit(v.get("unit")) or MIDPOINT_MAP[c][1])
                                for c, v in result.impacts.items() if c in MIDPOINT_MAP}

    # Cold-storage leakage is a farm-level source: allocate it to the crop totals by area
    # share (the same share service._sub_assessment uses for the charge), so crops sum to farm.
    if leak_kg_co2e and breakdown:
        for f in foods:
            qkg = f.get("quantity_kg") or 1.0
            label = f"{f.get('name', 'crop')} ({qkg:.0f}kg)"
            gw = (breakdown.get(label) or {}).get("Global warming")
            if not gw:
                continue
            share = ((f.get("area_allocated") or 0) / total_area) if total_area else (1.0 / max(len(foods), 1))
            breakdown[label]["Global warming"] = _midpoint((gw.get("value") or 0.0) + leak_kg_co2e * share,
                                                           gw.get("unit") or "kg CO2-eq")

    # Co-product allocation (grain vs removed, sold/fed straw), applied as post-processing
    # to each crop's burden; the farm per-kg results are re-weighted by each crop's share.
    allocation = {}
    for f in foods:
        qkg = f.get("quantity_kg") or 1.0
        label = f"{f.get('name', 'crop')} ({qkg:.0f}kg)"
        a = coproduct_allocation(f)
        if a.get("note"):
            allocation[label] = a
    if any(a["applied"] for a in allocation.values()):
        crop_gw = {}
        for label, cats in breakdown.items():
            fac = (allocation.get(label) or {}).get("factor", 1.0)
            crop_gw[label] = ((cats.get("Global warming") or {}).get("value") or 0.0, fac)
            for m in cats.values():
                m["value"] = (m.get("value") or 0.0) * fac
                if m.get("uncertainty_range"):
                    m["uncertainty_range"] = [x * fac for x in m["uncertainty_range"]]
        if len(foods) == 1:
            farm_fac = next(iter(allocation.values()))["factor"] if allocation else 1.0
        else:
            tot = sum(v for v, _ in crop_gw.values())
            farm_fac = (sum(v * fac for v, fac in crop_gw.values()) / tot) if tot else 1.0
        for m in midpoints.values():
            m["value"] = (m.get("value") or 0.0) * farm_fac
            m["uncertainty_range"] = [x * farm_fac for x in m["uncertainty_range"]]
        for m in ep.values():
            m["value"] = (m.get("value") or 0.0) * farm_fac
            m["uncertainty_range"] = [x * farm_fac for x in m["uncertainty_range"]]
        # The MC samples from result.contribution_by_source; scale a shallow copy so its
        # anchor matches the allocated midpoints (result itself is reused by callers).
        from types import SimpleNamespace as _NS
        result = _NS(**{**vars(result), "contribution_by_source": {
            s: {c: {**v, "value": (v.get("value") or 0.0) * farm_fac} for c, v in imp.items()}
            for s, imp in (getattr(result, "contribution_by_source", None) or {}).items()}}) \
            if hasattr(result, "__dict__") else result

    single, single_meta = single_score(midpoints, ep, engine.method)
    single_meta["normalised_midpoints"] = normalised_midpoints(midpoints, engine.method)
    # Several different products: the farm per-kg score divides by summed kg of different crops,
    # so it is a farm aggregate, not a product footprint, and is not banded (CONTRACT §2).
    if len({(f.get("name") or "").strip().lower() for f in foods}) > 1:
        single_meta["band"] = "Not banded"
        single_meta["band_basis"] = ("farm aggregate over several different products, not a product "
                                     "footprint: see the per-crop results (per kg) and the per-ha results")
        single_meta["label"] = (single_meta.get("label") or "single score") + " (farm aggregate)"

    uncertainty_block = None
    single_uncertainty = [single * 0.7, single * 1.4]
    if run_uncertainty:
        try:
            from .uncertainty import run_pedigree_mc, apply_mc_to_midpoints, DEFAULT_N
        except ImportError:
            from uncertainty import run_pedigree_mc, apply_mc_to_midpoints, DEFAULT_N
        uncertainty_block = run_pedigree_mc(
            result, midpoints, engine, total_kg,
            n=uncertainty_n or DEFAULT_N,
            seed=uncertainty_seed if uncertainty_seed is not None else 42,
            assessment=assessment,
        )
        apply_mc_to_midpoints(midpoints, uncertainty_block)
        # Prefer the MC's directly-sampled single-score distribution (single_score is
        # recomputed on every sampled midpoint set, which captures cross-category
        # correlation) over a crude GWP-ratio mapping. Bands stay on the point estimate.
        ss_mc = uncertainty_block.get("single_score") or {}
        if ss_mc.get("p5") is not None and ss_mc.get("p95") is not None:
            single_uncertainty = [ss_mc["p5"], ss_mc["p95"]]
        else:
            gwp = (uncertainty_block.get("percentiles") or {}).get("Global warming") or {}
            base = gwp.get("base") or 0.0
            if base and gwp.get("p5") is not None and gwp.get("p95") is not None:
                single_uncertainty = [single * (gwp["p5"] / base), single * (gwp["p95"] / base)]
                uncertainty_block["single_score"] = {
                    "p5": single_uncertainty[0], "p50": single, "p95": single_uncertainty[1]}

    # Dual functional units: per kg (default scores) and per ha of cropped area.
    # per_ha = per_kg × (kg / ha). Single-score bands stay per-kg only.
    kg_per_ha = (total_kg / total_area) if total_area and total_area > 0 else None
    midpoints_per_ha: dict = {}
    if kg_per_ha:
        for cat, m in midpoints.items():
            u = (m.get("unit") or "").replace(" per kg", " per ha")
            val_ha = (m.get("value") or 0.0) * kg_per_ha
            ur = m.get("uncertainty_range")
            ur_ha = [ur[0] * kg_per_ha, ur[1] * kg_per_ha] if ur and len(ur) == 2 else None
            midpoints_per_ha[cat] = _midpoint(val_ha, u, uncertainty_range=ur_ha)
    functional_units = {
        "per_kg": {
            "total_kg": total_kg,
            "midpoint_impacts": midpoints,
            "note": "Default functional unit for the single score and band.",
        },
        "per_ha": {
            "total_ha": total_area,
            "kg_per_ha": kg_per_ha,
            "midpoint_impacts": midpoints_per_ha or None,
            "note": (
                "Land and other impacts expressed per hectare of cropped area. "
                "The single-score band is calibrated per kg only — do not compare "
                "per-ha totals to Low/Moderate/High bands."
                if kg_per_ha
                else "Cropped area was not provided; per-ha totals are unavailable."
            ),
        },
        "land_intensity_note": (
            "Land use (m² per kg) is land intensity — how much land is occupied to "
            "produce one kilogram of crop — not a judgment that using farmland is wrong. "
            "Higher yield (more kg per hectare) lowers land use per kg."
        ),
    }

    try:
        from .iso_report import build_iso_report
    except ImportError:
        from iso_report import build_iso_report
    try:
        from .uncertainty import one_at_a_time_sensitivity
    except ImportError:
        from uncertainty import one_at_a_time_sensitivity
    try:
        oat = one_at_a_time_sensitivity(result, midpoints, engine, total_kg)
    except Exception:
        oat = None

    single_meta["allocation"] = allocation
    single_meta["unmapped_categories"] = unmapped
    iso = build_iso_report(assessment, result, engine, midpoints, single_meta, total_kg,
                           per_crop, assessment_id=assessment_id, uncertainty=uncertainty_block,
                           sensitivity=oat)

    # Raw LCI + per-source contribution, per functional unit, for programmatic auditing
    # (the ISO report embeds display-ready summaries of the same data).
    cbs = getattr(result, "contribution_by_source", None) or {}
    contribution_by_source = {
        src: {cat: {"value": (v.get("value") or 0.0) / total_kg, "unit": v.get("unit")}
              for cat, v in imp.items()}
        for src, imp in cbs.items()}

    try:
        from .contribution_sankey import build_contribution_sankey
    except ImportError:
        from contribution_sankey import build_contribution_sankey
    contribution_sankey = build_contribution_sankey(contribution_by_source)

    country_raw = assessment.get("country", "") or ""
    country_display = (
        "Canada" if str(country_raw).strip().lower() == "global" else country_raw
    )

    try:
        from .regional_benchmark import compute_regional_benchmark
    except ImportError:
        from regional_benchmark import compute_regional_benchmark
    regional_benchmark = compute_regional_benchmark(assessment, midpoints)

    out = {
        "id": assessment_id,
        "company_name": assessment.get("company_name", ""),
        "country": country_display,
        # Echo identity fields so results/reports never fall back to demo placeholders.
        "farm_profile": assessment.get("farm_profile") or None,
        "assessment_date": datetime.now(timezone.utc).isoformat(),
        "midpoint_impacts": midpoints,
        "endpoint_impacts": ep,
        "single_score": {
            "value": single,
            "unit": single_meta["unit"],
            "label": single_meta.get("label"),
            "band": single_meta["band"],
            "band_basis": single_meta["band_basis"],
            "band_cutoffs": single_meta.get("band_cutoffs"),
            "uncertainty_range": single_uncertainty,
            "weighting_factors": single_meta["weighting_factors"],
            "weighting_basis": single_meta.get("weighting_basis"),
            "contributions": single_meta["contributions"],
            "normalised_midpoints": single_meta.get("normalised_midpoints"),
            "methodology": single_meta["methodology"],
            "iso_14044_disclosure": single_meta.get("iso_14044_disclosure"),
        },
        "data_quality": {
            # derived from the pedigree scorecard, not asserted. Map the scorecard rating
            # (Good/Medium/Limited) to the response's High/Medium/Low confidence vocabulary.
            "overall_confidence": {"Good": "High", "Medium": "Medium", "Limited": "Low"}.get(
                iso["interpretation"]["data_quality_scorecard"]["overall"], "Medium"),
            "completeness_score": (
                len([m for m in (result.input_matches or []) if m.get("matched")])
                / len(result.input_matches)) if result.input_matches else 1.0,
            "scorecard": iso["interpretation"]["data_quality_scorecard"]["indicators"],
            "regional_adaptation": True,
            "warnings": [],
            "recommendations": [],
            "notes": (extra_notes or []) + result.notes,
        },
        "breakdown_by_food": breakdown,
        "sensitivity_analysis": {"contribution": result.contribution,
                                 **({"one_at_a_time": oat["cases"],
                                     "method_sensitivity": oat["method_sensitivity"],
                                     "note": oat["note"]} if oat else {})},
        "input_matches": result.input_matches,
        "inventory": iso["inventory_analysis"]["inventory_results"],
        # Merged elementary-flow inventory (store UIDs, whole farm, BEFORE any co-product
        # allocation) for method recharacterization and the research export. Always a dict.
        "engine_inventory": _engine_inventory(engine, getattr(result, "inventory", None) or {}),
        "coproduct_allocation": allocation or None,
        # Per-source raw flows (method-independent), so a later method switch can
        # re-characterize each contribution source instead of zeroing the MC / Top sources.
        "engine_inventory_by_source": {
            src: {uid: {"name": r.get("name"), "unit": r.get("unit"), "amount": r.get("amount")}
                  for uid, r in (flows or {}).items()}
            for src, flows in (getattr(result, "contribution_flows_by_source", None) or {}).items()
        },
        "lcia_method": engine.method,
        "provenance": _provenance(engine, engine.method),
        "contribution_by_source": contribution_by_source,
        "contribution_sankey": contribution_sankey,
        "functional_units": functional_units,
        "iso_report": iso,
        "review_status": "draft",
    }
    # Pass-throughs from the service / field model (read defensively; CONTRACT §2):
    # soil-carbon change from management is reported SEPARATELY, never in the headline.
    for key in ("soc_management", "needs_review", "climate_zone_used", "per_crop_results"):
        val = getattr(result, key, None)
        if val is None and isinstance(assessment.get("_engine_meta"), dict):
            val = assessment["_engine_meta"].get(key)
        if val is not None:
            out[key] = val
    if regional_benchmark is not None:
        out["regional_benchmark"] = regional_benchmark
    if uncertainty_block is not None:
        out["uncertainty"] = uncertainty_block
    if assessment.get("study_meta"):
        out["study_meta"] = assessment["study_meta"]
    return out
