#!/usr/bin/env python3
"""
serialize.py - turn the deterministic Recommendation into the JSON the API returns and
the chat grounds on. One canonical shape, used by both, so the endpoint and the RAG seam
never drift.

Every measure carries its provenance and a `reviewed` flag. That is deliberate: the plan
(RECOMMENDATION_ENGINE_PLAN.md §10) requires the surface to distinguish this farm's
measured data from general guidance, with a citation, and to be honest that the v1
library has not passed agronomic review.
"""
from __future__ import annotations

from typing import Any

try:
    from .economics import Recommendation, ScreenedMeasure, RevenueEstimate
    from .matcher import MatchedMeasure
except ImportError:
    from economics import Recommendation, ScreenedMeasure, RevenueEstimate
    from matcher import MatchedMeasure


def _measure_to_dict(s: ScreenedMeasure) -> dict[str, Any]:
    m = s.measure
    mm: MatchedMeasure = s.matched
    e = m.effect
    return {
        "id": m.id,
        "title": m.title,
        "action": m.action_detail,
        "targets_source": mm.target_source,
        "targets_share": mm.target_share,          # fraction of climate impact [0..1]
        "impact_category": m.impact_category,
        "horizon": m.horizon.value,
        "effect": {
            "value": e.value,
            "unit": e.unit.value,
            "basis": e.basis.value,                # measured | modelled | expert_judgement
            "uncertainty": ([e.uncertainty_low, e.uncertainty_high]
                            if e.uncertainty_low is not None else None),
            "yield_effect": e.yield_effect,
            "note": e.note,
        },
        "economics": {
            "capex_ghs": s.capex_ghs,
            "annual_saving_ghs": s.annual_saving_ghs,   # signed: +ve saving, -ve cost
            "payback_months": s.payback_months,
            "cost_tier": s.cost_tier,
            "affordability": s.affordability,
            "currency": m.economics.currency or "GHS",
        },
        "provenance": {
            "source": m.provenance.source,
            "citation": m.provenance.citation,
            "span": m.provenance.span,
            "publication_date": m.provenance.publication_date,
            "licence": m.provenance.licence,
        },
        "reviewed": m.is_reviewed,
        "data_gaps": sorted(set(mm.data_gaps) | set(s.econ_gaps)),
    }


def _revenue_to_dict(r: RevenueEstimate) -> dict[str, Any]:
    return {
        "total_ghs": r.total_ghs,
        "currency": r.currency,
        "basis": r.basis,
        "unit_assumption": r.unit_assumption,
        "priced_fraction": r.priced_fraction,
        "stale_prices": r.stale_prices,
        "lines": [
            {"crop": l.crop, "quantity_kg": l.quantity_kg,
             "price_ghs_per_kg": l.price_ghs_per_kg, "revenue_ghs": l.revenue_ghs,
             "price_source": l.price_source, "priced": l.priced}
            for l in r.lines
        ],
        "gaps": r.gaps,
    }


def recommendation_to_dict(rec: Recommendation, *, assessment_id: str | None = None,
                           generated_at: str | None = None,
                           is_processing: bool = False) -> dict[str, Any]:
    """The full API payload. `pending_review` is true whenever any surfaced measure is
    unreviewed, so the UI can badge draft guidance rather than present it as signed off."""
    measures = [_measure_to_dict(s) for s in rec.screened]
    plan = {
        "phases": [
            {"key": ph["key"], "label": ph["label"],
             "measures": [_measure_to_dict(s) for s in ph["measures"]]}
            for ph in rec.plan.get("phases", [])
        ]
    }
    pending = any(not m["reviewed"] for m in measures)
    reviewer = "a processing specialist" if is_processing else "an agronomist"
    return {
        "assessment_id": assessment_id,
        "generated_at": generated_at,
        "pending_review": pending,
        "is_processing": is_processing,
        "disclaimer": (
            f"Draft guidance. These measures are screening-level and have not yet been "
            f"reviewed by {reviewer}; figures carry uncertainty and prices may be dated."
            if pending else ""
        ),
        "revenue": _revenue_to_dict(rec.revenue),
        "plan": plan,
        "measures": measures,          # flat, ranked, for a simple render
    }


def guidance_snippets(rec: Recommendation, *, limit: int = 4) -> list[str]:
    """Short, cited lines for the chat RAG seam. Reads only structured measure fields, so
    there is nothing for the model to hallucinate - it explains what these say."""
    out: list[str] = []
    for s in rec.screened[:limit]:
        m = s.measure
        econ = ""
        if s.payback_months:
            econ = f" Roughly {s.payback_months:.0f} months to pay back."
        elif s.annual_saving_ghs and s.annual_saving_ghs > 0:
            econ = f" Saves about {s.annual_saving_ghs:.0f} GHS a year."
        elif s.annual_saving_ghs and s.annual_saving_ghs < 0:
            econ = f" Costs about {abs(s.annual_saving_ghs):.0f} GHS a year."
        cite = m.provenance.citation or m.provenance.source
        out.append(
            f"For {mm_target(s)} ({s.matched.target_share:.0%} of climate impact): "
            f"{m.action_detail}{econ} (Source: {cite}.)"
        )
    return out


def mm_target(s: ScreenedMeasure) -> str:
    return s.matched.target_source
