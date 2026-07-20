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


# Environmental Footprint (EF) 3.1 global normalization factors, per person per year
# (JRC EF reference package). Used when the method is EF, since EF midpoints are in
# different units/magnitudes than ReCiPe — normalising EF values with ReCiPe factors
# produces a nonsense score (e.g. EF land-use points ÷ ReCiPe m2a).
EF_NF = {
    "Global warming": 7550.0,            # kg CO2-eq
    "Terrestrial acidification": 55.6,   # mol H+-eq (EF "Acidification")
    "Freshwater eutrophication": 1.61,   # kg P-eq
    "Marine eutrophication": 19.5,       # kg N-eq
    "Land use": 819000.0,                # dimensionless points (Pt)
    "Mineral depletion": 0.0636,         # kg Sb-eq
    "Particulate matter formation": 5.95e-4,  # disease incidence
    "Photochemical oxidation": 40.9,     # kg NMVOC-eq
    "Water consumption": 11500.0,        # m3 world-eq deprived
    "Fossil depletion": 65000.0,         # MJ
}


def single_score(midpoints: dict, ep: dict, method: str = "ReCiPe 2016 v1.03, midpoint (H)",
                 bands: dict | None = None) -> tuple:
    """Proper normalized single score: normalise each midpoint by its per-capita reference
    (person-equivalents), equal-weight and sum, express in micro-person-equivalents (µPt)
    per kg. The normalization set is chosen to MATCH the LCIA method (ReCiPe vs EF), so the
    factors are in the same units as the values. Transparent and standard. Also returns a
    qualitative band whose Low/Moderate/High cutoffs are empirically calibrated (see _bands).

    `bands` overrides the default farm-gate benchmark with another calibrated set (e.g. the
    processed-food benchmark for facility assessments); it must have the same shape as _bands()."""
    is_ef = bool(method) and "EF" in method and "ReCiPe" not in method
    nf_set = EF_NF if is_ef else RECIPE_NF
    total = 0.0
    per_cat: dict = {}
    for cat, nf in nf_set.items():
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
    b = bands or _bands()
    band = ("Low" if micro < b["low"] else "Moderate" if micro < b["high"] else "High")
    nf_name = "Environmental Footprint 3.1" if is_ef else "ReCiPe 2016 [World, Hierarchist]"
    # The band cutoffs are calibrated on ReCiPe scores; for EF they are only indicative.
    band_basis = b["basis"] if not is_ef else (b["basis"] + " (calibrated on ReCiPe; indicative for the EF method)")
    return micro, {
        "unit": "µPt per kg",
        "band": band,
        "band_basis": band_basis,
        "band_cutoffs": {"low": b["low"], "high": b["high"], "calibrated": b["calibrated"],
                         "benchmark_min": (b.get("percentiles") or {}).get("min"),
                         "benchmark_max": (b.get("percentiles") or {}).get("max")},
        "person_equivalents_per_kg": total,
        "weighting_factors": {c: 1.0 for c in used},   # equal weighting
        "contributions": contributions,                # share of the single score per category
        "methodology": (
            f"Normalized single score = Σ(midpoint ÷ {nf_name} midpoint normalization) over "
            f"{len(used)} categories, equal weighting, in micro-person-equivalents (µPt) per kg "
            f"product. 1e6 µPt ≈ one person's total annual environmental footprint."),
    }


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

    single, single_meta = single_score(midpoints, ep, engine.method)

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
        )
        apply_mc_to_midpoints(midpoints, uncertainty_block)
        # Map GWP relative p5/p95 onto the single score (bands stay on the point estimate).
        gwp = (uncertainty_block.get("percentiles") or {}).get("Global warming") or {}
        base = gwp.get("base") or 0.0
        if base and gwp.get("p5") is not None and gwp.get("p95") is not None:
            single_uncertainty = [single * (gwp["p5"] / base), single * (gwp["p95"] / base)]
            uncertainty_block["single_score"] = {
                "p5": single_uncertainty[0],
                "p50": single,
                "p95": single_uncertainty[1],
            }

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
    iso = build_iso_report(assessment, result, engine, midpoints, single_meta, total_kg,
                           per_crop, assessment_id=assessment_id, uncertainty=uncertainty_block)

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
            "band": single_meta["band"],
            "band_basis": single_meta["band_basis"],
            "uncertainty_range": single_uncertainty,
            "weighting_factors": single_meta["weighting_factors"],
            "contributions": single_meta["contributions"],
            "methodology": single_meta["methodology"],
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
        "sensitivity_analysis": {"contribution": result.contribution},
        "input_matches": result.input_matches,
        "inventory": iso["inventory_analysis"]["inventory_results"],
        # Merged elementary-flow inventory (store UIDs) for fast method recharacterization.
        # Always a dict (may be empty) so callers can rely on the key being present.
        "engine_inventory": {
            uid: {"name": r.get("name"), "unit": r.get("unit"), "amount": r.get("amount")}
            for uid, r in (getattr(result, "inventory", None) or {}).items()
        },
        "lcia_method": engine.method,
        "contribution_by_source": contribution_by_source,
        "contribution_sankey": contribution_sankey,
        "functional_units": functional_units,
        "iso_report": iso,
        "review_status": "draft",
    }
    if regional_benchmark is not None:
        out["regional_benchmark"] = regional_benchmark
    if uncertainty_block is not None:
        out["uncertainty"] = uncertainty_block
    if assessment.get("study_meta"):
        out["study_meta"] = assessment["study_meta"]
    return out
