#!/usr/bin/env python3
"""
process_adapter.py — turn a processing AssessmentResult into the frontend response shape,
reusing the farm adapter's characterization helpers. Parallels adapter.to_assessment_response
but for a facility: functional unit is per kg of processed output, there are no field
emissions, and the breakdown is per PRODUCT.

M1 scope: whole-facility footprint, product breakdown by output-mass share, no ISO report
yet (added in M4). Co-product allocation (M2), refrigerants (M3), a processing ISO report
and recalibrated bands (M4) build on this.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

try:
    from .adapter import MIDPOINT_MAP, _norm_unit, _midpoint, _endpoints, single_score, _bands
    from .iso_report import _data_quality_scorecard
    from .refrigerants import refrigerant_co2e
    from .process_iso_report import build_process_iso_report
except ImportError:
    from adapter import MIDPOINT_MAP, _norm_unit, _midpoint, _endpoints, single_score, _bands
    from iso_report import _data_quality_scorecard
    from refrigerants import refrigerant_co2e
    from process_iso_report import build_process_iso_report

_PROC_BANDS_FILE = os.path.join(os.path.dirname(__file__), "process_single_score_bands.json")
_PROC_BANDS_CACHE: dict | None = None


def _process_bands() -> dict:
    """Calibrated Low/Moderate/High cutoffs for PROCESSED-FOOD single scores. Falls back to
    the farm-gate bands (flagged as indicative) if the processed-food calibration is absent."""
    global _PROC_BANDS_CACHE
    if _PROC_BANDS_CACHE is None:
        try:
            d = json.loads(open(_PROC_BANDS_FILE, encoding="utf-8").read())
            _PROC_BANDS_CACHE = {
                "low": float(d["low_cut_upt_per_kg"]), "high": float(d["high_cut_upt_per_kg"]),
                "calibrated": True,
                "basis": (f"tertiles of {d.get('n_products', '?')} benchmark processed-food products "
                          "via the identical pipeline"),
                "percentiles": d.get("percentiles"),
            }
        except (OSError, ValueError, KeyError):
            fb = _bands()
            _PROC_BANDS_CACHE = {**fb, "calibrated": False,
                                 "basis": fb["basis"] + " (farm-gate benchmark shown as indicative; "
                                          "processed-food calibration not yet available)"}
    return _PROC_BANDS_CACHE


def _allocation(products: list, total_kg: float, basis: str) -> tuple[dict, str, str]:
    """Split the facility total across co-products. Returns (per-product info, basis_used, note).

    Each product's `intensity` scales the facility's per-kg result to that product's own
    per-kg result: intensity = factor x total_kg / product_kg, where `factor` is the product's
    share of the facility total. Under MASS, factor = mass share so intensity == 1 for every
    product (co-products share the same per-kg burden). Under ECONOMIC, factor = revenue share,
    so a higher-value product carries more per kg. Economic falls back to mass if any price is missing.
    """
    kgs = {p.get("name", p.get("id", "product")): (p.get("annual_production") or 0.0) * 1000.0 for p in products}
    prices = {p.get("name", p.get("id", "product")): p.get("economic_value") for p in products}
    note = ""
    basis_used = basis
    if basis == "economic":
        if all((prices.get(n) or 0) > 0 for n in kgs) and kgs:
            revenue = {n: prices[n] * kgs[n] for n in kgs}
            total_rev = sum(revenue.values()) or 1.0
            factors = {n: revenue[n] / total_rev for n in kgs}
        else:
            basis_used = "mass"
            note = "economic allocation requested but a per-kg value was missing; fell back to mass allocation"
            factors = {n: (kgs[n] / total_kg if total_kg else 0.0) for n in kgs}
    else:
        factors = {n: (kgs[n] / total_kg if total_kg else 0.0) for n in kgs}

    info = {}
    for n, kg in kgs.items():
        intensity = (factors[n] * total_kg / kg) if kg else 0.0
        info[n] = {"factor": factors[n], "intensity": intensity, "output_kg": kg}
    return info, basis_used, note


def _inventory_results(inventory: dict, total_kg: float, top_n: int = 20) -> dict:
    """Display-ready summary of the biggest elementary flows, per kg of output."""
    rows = [{"flow": r.get("name") or uid, "amount": (r.get("amount") or 0.0) / total_kg,
             "unit": r.get("unit")} for uid, r in inventory.items()]
    rows.sort(key=lambda r: -abs(r["amount"] or 0.0))
    return {"basis": "per kilogram of processed product", "n_flows_total": len(rows),
            "n_shown": min(top_n, len(rows)), "flows": rows[:top_n]}


def to_process_response(result, request: dict, engine, total_kg: float,
                        assessment_id: str, extra_notes=None,
                        run_uncertainty: bool = True,
                        uncertainty_n: int | None = None,
                        uncertainty_seed: int | None = None) -> dict:
    """`result` = whole-facility AssessmentResult (impacts + inventory + input_matches)."""
    total_kg = total_kg or 1.0

    # midpoints: whole-facility -> per kg of output, mapped to frontend names.
    # (unit MUST end in "per kg"; see the note in adapter.to_assessment_response.)
    midpoints: dict = {}
    for cat, v in result.impacts.items():
        m = MIDPOINT_MAP.get(cat)
        if not m:
            continue
        unit = _norm_unit(v.get("unit")) or m[1]
        midpoints[m[0]] = _midpoint(v["value"] / total_kg, f"{unit} per kg")

    ep = _endpoints(engine, {u: {**r, "amount": r["amount"] / total_kg}
                             for u, r in result.inventory.items()}, engine.method)
    if ep.get("Ecosystem Quality", {}).get("value"):
        midpoints["Biodiversity loss"] = _midpoint(ep["Ecosystem Quality"]["value"], "species.yr per kg")

    # On-site refrigerant (F-gas) leakage -> climate via AR6 GWP100, added before the single
    # score so it is reflected in it. Method-agnostic (see engine/refrigerants.py).
    rm = (request.get("processing_operations") or {}).get("refrigerant_management") or {}
    ref_co2e, ref_note = refrigerant_co2e(rm.get("refrigerant_type"), rm.get("annual_leakage_kg") or 0.0)
    ref_per_kg = (ref_co2e / total_kg) if ref_co2e else 0.0
    if ref_per_kg and "Global warming" in midpoints:
        gw = dict(midpoints["Global warming"])
        gw["value"] = (gw.get("value") or 0.0) + ref_per_kg
        midpoints["Global warming"] = gw

    single, single_meta = single_score(midpoints, ep, engine.method, bands=_process_bands())

    # Pedigree screening Monte Carlo (parity with the farm path): scale category totals by
    # data-class GSD without re-solving the LCI. The on-site refrigerant term is folded into
    # the decomposition (as a measured on-site source) so the sampled base matches the GW
    # midpoint that already includes it — otherwise the point estimate would sit above its own
    # band. A shim is used rather than mutating `result`, whose contribution_by_source is
    # reused below and would then double-count the refrigerant.
    single_uncertainty = [single * 0.7, single * 1.4]
    uncertainty_block = None
    if run_uncertainty:
        try:
            from .uncertainty import run_pedigree_mc, apply_mc_to_midpoints, DEFAULT_N
        except ImportError:
            from uncertainty import run_pedigree_mc, apply_mc_to_midpoints, DEFAULT_N
        from types import SimpleNamespace
        cbs_raw = dict(getattr(result, "contribution_by_source", None) or {})
        if ref_co2e:
            cbs_raw["refrigerant leakage (on-site)"] = {
                "Climate change": {"value": ref_co2e, "unit": "kg CO2-eq"}}
        mc_result = SimpleNamespace(
            contribution_by_source=cbs_raw,
            input_matches=getattr(result, "input_matches", None),
        )
        uncertainty_block = run_pedigree_mc(
            mc_result, midpoints, engine, total_kg,
            n=uncertainty_n or DEFAULT_N,
            seed=uncertainty_seed if uncertainty_seed is not None else 42,
        )
        apply_mc_to_midpoints(midpoints, uncertainty_block)
        # Map GW relative p5/p95 onto the single score (bands stay on the point estimate).
        gwp = (uncertainty_block.get("percentiles") or {}).get("Global warming") or {}
        base = gwp.get("base") or 0.0
        if base and gwp.get("p5") is not None and gwp.get("p95") is not None:
            single_uncertainty = [single * (gwp["p5"] / base), single * (gwp["p95"] / base)]
            uncertainty_block["single_score"] = {
                "p5": single_uncertainty[0], "p50": single, "p95": single_uncertainty[1]}

    # Co-product allocation: split the facility total across products. `intensity` scales the
    # facility per-kg result to each product's own per-kg result (see _allocation). The facility
    # midpoints/single score above are the blended per-kg-of-total-output average.
    products = request.get("processed_products") or []
    basis = (request.get("allocation_basis") or "mass")
    alloc, basis_used, alloc_note = _allocation(products, total_kg, basis)
    breakdown: dict = {}
    for name, a in alloc.items():
        k = a["intensity"]
        breakdown[name] = {
            "single_score": round(single * k, 4),
            "allocation_factor": round(a["factor"], 4),
            "output_kg": a["output_kg"],
            "impacts": {fname: _midpoint(v["value"] * k, v["unit"]) for fname, v in midpoints.items()},
        }

    unlinked = [n for n in (result.notes or []) if "no match" in (n or "").lower() or "excluded" in (n or "").lower()]
    dq_overall, dq_indicators = _data_quality_scorecard(result.input_matches, unlinked, result.region)

    cbs = getattr(result, "contribution_by_source", None) or {}
    contribution_by_source = {
        src: {cat: {"value": (v.get("value") or 0.0) / total_kg, "unit": v.get("unit")}
              for cat, v in imp.items()}
        # a processor has no field emissions, so drop the always-empty on-farm source
        for src, imp in cbs.items()
        if src != "Field emissions (on-farm)" and any((v.get("value") or 0.0) for v in imp.values())}
    if ref_per_kg:
        clim_key = next((k for src in contribution_by_source.values() for k in src
                         if "climate" in k.lower() or "warming" in k.lower()), "Climate change")
        contribution_by_source["refrigerant leakage (on-site)"] = {
            clim_key: {"value": ref_per_kg, "unit": "kg CO2-eq"}}

    run_notes = list(extra_notes or [])
    if ref_note:
        run_notes.append(ref_note)

    allocation = {"basis": basis_used, "note": alloc_note, "n_products": len(products)}
    iso = build_process_iso_report(request, result, engine, midpoints, single_meta, total_kg,
                                   allocation, extra_notes=run_notes, assessment_id=assessment_id)

    region_code = getattr(getattr(engine, "region", None), "code", None) or request.get("region")
    # API country enum uses "Global" for Canada; surface a clear display label.
    country_raw = request.get("country", "") or ""
    country_display = (
        "Canada" if str(country_raw).strip().lower() == "global" else country_raw
    )

    resp = {
        "id": assessment_id,
        "facility_profile": request.get("facility_profile"),
        "country": country_display,
        "region": region_code,
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
            "overall_confidence": {"Good": "High", "Medium": "Medium", "Limited": "Low"}.get(dq_overall, "Medium"),
            "completeness_score": (len([m for m in (result.input_matches or []) if m.get("matched")])
                                   / len(result.input_matches)) if result.input_matches else 1.0,
            "scorecard": dq_indicators,
            "regional_adaptation": True,
            "warnings": [],
            "recommendations": [],
            "notes": run_notes + result.notes,
        },
        "breakdown_by_product": breakdown,
        "allocation": allocation,
        "input_matches": result.input_matches,
        "inventory": iso["inventory_analysis"]["inventory_results"],
        "contribution_by_source": contribution_by_source,
        "iso_report": iso,
    }
    if uncertainty_block is not None:
        resp["uncertainty"] = uncertainty_block
    return resp
