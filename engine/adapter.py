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
    "Acidification":                                ("Terrestrial acidification", "mol H+-eq"),
    "Eutrophication: freshwater":                   ("Freshwater eutrophication", "kg P-eq"),
    "Eutrophication, freshwater":                   ("Freshwater eutrophication", "kg P-eq"),
    "Eutrophication: marine":                       ("Marine eutrophication", "kg N-eq"),
    "Eutrophication, marine":                       ("Marine eutrophication", "kg N-eq"),
    "Fossil resource scarcity":                     ("Fossil depletion", "kg oil-eq"),
    "Energy resources: non-renewable, fossil":      ("Fossil depletion", "MJ"),
    "Mineral resource scarcity":                    ("Mineral depletion", "kg Cu-eq"),
    "Material resources: metals/minerals":          ("Mineral depletion", "kg Sb-eq"),
    "Particulate matter formation":                 ("Particulate matter formation", "kg PM2.5-eq"),
    "Particulate matter":                           ("Particulate matter formation", "disease inc."),
    "Photochemical oxidant formation: human health": ("Photochemical oxidation", "kg NOx-eq"),
    "Photochemical ozone formation: human health":  ("Photochemical oxidation", "kg NMVOC-eq"),
}

SOURCES = ["ecoinvent 3.11 (supply chain)", "IPCC 2019 AFOLU (field emissions)",
           "ReCiPe 2016 / EF 3.1 (characterization)"]


def _norm_unit(unit) -> str:
    """Lightly tidy a store unit for display (keep it authoritative — it must match the
    number). e.g. 'kg CO2-Eq' -> 'kg CO2-eq', 'm2*a crop-Eq' -> 'm2a crop-eq'."""
    if not unit:
        return ""
    return str(unit).replace("-Eq", "-eq").replace("*a", "a").replace("m2*", "m2")


def _midpoint(value_per_kg: float, unit: str) -> dict:
    return {
        "value": value_per_kg,
        "unit": unit,
        "uncertainty_range": [value_per_kg * 0.7, value_per_kg * 1.4],  # pedigree ~±30/40%
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


# ReCiPe 2016 midpoint normalization, World, Hierarchist perspective (impact per person
# per year), from data/ReCipe2016/Normalization scores ReCiPe2016v1.1_20190514.xlsx.
# A normalized single score = Σ(impact / NF) = person-equivalents, then ×1e6 → µPt.
RECIPE_NF = {
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


# Band thresholds are calibrated EMPIRICALLY against a benchmark basket of farm-gate
# crop products run through this same pipeline (see engine/calibrate_bands.py, which
# writes single_score_bands.json). Low/Moderate/High = below 33rd / 33rd-67th / above
# 67th percentile of that basket. The 500/1500 fallback is only used if the file is
# absent, and is flagged as indicative in that case.
import json as _json
import os as _os

_BANDS_FILE = _os.path.join(_os.path.dirname(__file__), "single_score_bands.json")
_BANDS_CACHE: dict | None = None


def _bands() -> dict:
    """Load the calibrated band cutoffs (cached). Falls back to indicative defaults."""
    global _BANDS_CACHE
    if _BANDS_CACHE is None:
        try:
            d = _json.loads(open(_BANDS_FILE, encoding="utf-8").read())
            _BANDS_CACHE = {
                "low": float(d["low_cut_upt_per_kg"]),
                "high": float(d["high_cut_upt_per_kg"]),
                "calibrated": True,
                "basis": (f"tertiles of {d.get('n_products', '?')} benchmark farm-gate crop "
                          f"products via the identical pipeline"),
                "percentiles": d.get("percentiles"),
            }
        except (OSError, ValueError, KeyError):
            _BANDS_CACHE = {"low": 500.0, "high": 1500.0, "calibrated": False,
                            "basis": "indicative defaults (no calibration file present)",
                            "percentiles": None}
    return _BANDS_CACHE


def single_score(midpoints: dict, ep: dict) -> tuple:
    """Proper normalized single score: normalise each midpoint by its ReCiPe 2016
    per-capita reference (person-equivalents), equal-weight and sum, express in
    micro-person-equivalents (µPt) per kg. Transparent and standard — replaces both the
    old misleading sigmoid and the earlier GWP proxy. Also returns a qualitative band
    whose Low/Moderate/High cutoffs are empirically calibrated (see _bands)."""
    total = 0.0
    per_cat: dict = {}
    for cat, nf in RECIPE_NF.items():
        v = midpoints.get(cat, {}).get("value")
        if v is not None and nf:
            per_cat[cat] = v / nf     # person-equivalents from this category
            total += per_cat[cat]
    used = list(per_cat)
    micro = total * 1e6   # µPt per kg
    # Each category's SHARE of the single score (what actually drives it) — far more
    # informative than the flat equal weights, which all render as an unhelpful "100%".
    contributions = {c: (pe / total if total else 0.0) for c, pe in per_cat.items()}
    # Band relative to the calibrated benchmark basket (1e6 µPt = one person's annual
    # footprint). Cutoffs come from single_score_bands.json when present.
    b = _bands()
    band = ("Low" if micro < b["low"] else "Moderate" if micro < b["high"] else "High")
    return micro, {
        "unit": "µPt per kg",
        "band": band,
        "band_basis": b["basis"],
        "band_cutoffs": {"low": b["low"], "high": b["high"], "calibrated": b["calibrated"]},
        "person_equivalents_per_kg": total,
        "weighting_factors": {c: 1.0 for c in used},   # equal weighting
        "contributions": contributions,                # share of the single score per category
        "methodology": (
            f"Normalized single score = Σ(midpoint ÷ ReCiPe 2016 midpoint normalization "
            f"[World, Hierarchist]) over {len(used)} categories, equal weighting, in "
            f"micro-person-equivalents (µPt) per kg product. 1e6 µPt ≈ one person's total "
            f"annual environmental footprint."),
    }


def to_assessment_response(result, assessment: dict, engine, total_kg: float,
                           assessment_id: str, extra_notes=None, per_crop=None) -> dict:
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

    single, single_meta = single_score(midpoints, ep)

    try:
        from .iso_report import build_iso_report
    except ImportError:
        from iso_report import build_iso_report
    iso = build_iso_report(assessment, result, engine, midpoints, single_meta, total_kg,
                           per_crop, assessment_id=assessment_id)

    return {
        "id": assessment_id,
        "company_name": assessment.get("company_name", ""),
        "country": assessment.get("country", ""),
        "assessment_date": datetime.now(timezone.utc).isoformat(),
        "midpoint_impacts": midpoints,
        "endpoint_impacts": ep,
        "single_score": {
            "value": single,
            "unit": single_meta["unit"],
            "band": single_meta["band"],
            "band_basis": single_meta["band_basis"],
            "uncertainty_range": [single * 0.7, single * 1.4],
            "weighting_factors": single_meta["weighting_factors"],
            "contributions": single_meta["contributions"],
            "methodology": single_meta["methodology"],
        },
        "data_quality": {
            "overall_confidence": "Medium",
            "completeness_score": 0.8,
            "regional_adaptation": True,
            "warnings": [],
            "recommendations": [],
            "notes": (extra_notes or []) + result.notes,
        },
        "breakdown_by_food": breakdown,
        "sensitivity_analysis": {"contribution": result.contribution},
        "input_matches": result.input_matches,
        "iso_report": iso,
    }
