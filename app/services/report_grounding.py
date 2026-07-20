"""
report_grounding.py — build a slim, token-efficient grounding payload from the
deterministic iso_report + assessment metrics for AI plain-language guides.

The AI layer must only interpret what is already in this JSON — never invent
methodology, numbers, or exclusions.
"""
from __future__ import annotations

import json
from typing import Any

GROUNDING_RULES = (
    "You are an interpreter, not an LCA author. "
    "Do not add facts, numbers, boundaries, or exclusions not present in the grounding JSON. "
    "If something is not listed, say it was not quantified in this study."
)

AI_DISCLAIMER = (
    "Plain-language summary of the deterministic ISO draft. "
    "Not a substitute for independent critical review."
)


class MissingIsoReportError(ValueError):
    """Raised when assessment data lacks the deterministic iso_report."""


def require_iso_report(assessment_data: dict) -> dict:
    iso = assessment_data.get("iso_report")
    if not iso:
        raise MissingIsoReportError(
            "Assessment has no iso_report. Re-run the assessment through the validated "
            "engine (POST /assess) before generating an AI guide."
        )
    return iso


def _midpoint_summary(midpoints: dict, limit: int = 12) -> list[dict]:
    rows = []
    for name, m in (midpoints or {}).items():
        if isinstance(m, dict):
            rows.append({
                "category": name,
                "value": m.get("value"),
                "unit": m.get("unit"),
            })
        elif isinstance(m, (int, float)):
            rows.append({"category": name, "value": m, "unit": None})
    rows.sort(key=lambda r: abs(r.get("value") or 0), reverse=True)
    return rows[:limit]


def _input_matches_summary(matches: list) -> list[dict]:
    out = []
    for m in matches or []:
        if not m.get("matched"):
            continue
        out.append({
            "input": m.get("input"),
            "matched": m.get("matched"),
            "kind": m.get("kind"),
            "location": m.get("location"),
            "source": m.get("source"),
        })
    return out


def build_grounding_payload(assessment_data: dict) -> dict:
    """Return a slim dict for LLM grounding. Requires iso_report."""
    iso = require_iso_report(assessment_data)
    interp = iso.get("interpretation") or {}
    scope = iso.get("scope") or {}
    inv = iso.get("inventory_analysis") or {}
    impact = iso.get("impact_assessment") or {}
    doc = iso.get("document_control") or {}
    single = assessment_data.get("single_score") or {}

    if isinstance(single, dict):
        single_summary = {
            "value": single.get("value"),
            "unit": single.get("unit"),
            "band": single.get("band"),
            "band_basis": single.get("band_basis"),
        }
    else:
        single_summary = {"value": single, "unit": "µPt per kg", "band": None}

    contribution = interp.get("contribution_analysis") or {}
    by_source = contribution.get("by_source") or []

    # Prefer per-input contribution from assessment root if present
    cbs = assessment_data.get("contribution_by_source") or {}
    if cbs and not by_source:
        clim_entries = []
        for src, cats in cbs.items():
            if isinstance(cats, dict):
                cc = cats.get("Climate change") or cats.get("Global warming") or {}
                val = cc.get("value") if isinstance(cc, dict) else None
                if val:
                    clim_entries.append({"source": src, "climate_change": val})
        clim_entries.sort(key=lambda x: abs(x.get("climate_change") or 0), reverse=True)
        by_source = clim_entries[:8]

    fu = assessment_data.get("functional_units") or {}
    land_note = fu.get("land_intensity_note") or (
        "Land use (m² per kg) is land intensity — area occupied per kilogram of crop — "
        "not a judgment that using farmland is environmentally wrong. "
        "Higher yield lowers land intensity per kg."
    )

    return {
        "grounding_rules": GROUNDING_RULES,
        "title": doc.get("title"),
        "commissioner": doc.get("commissioner"),
        "company_name": assessment_data.get("company_name"),
        "country": assessment_data.get("country"),
        "region": scope.get("product_system"),
        "functional_unit": scope.get("functional_unit"),
        "functional_units_available": {
            "per_kg": bool((fu.get("per_kg") or {}).get("midpoint_impacts")),
            "per_ha": bool((fu.get("per_ha") or {}).get("midpoint_impacts")),
        },
        "land_intensity_note": land_note,
        "boundary_included": scope.get("boundary_included"),
        "boundary_excluded": scope.get("boundary_excluded"),
        "lcia_method": scope.get("lcia_method"),
        "assumptions_and_limitations": scope.get("assumptions_and_limitations"),
        "inputs_matched": inv.get("inputs_matched"),
        "completeness_check": interp.get("completeness_check"),
        "significant_issues": interp.get("significant_issues"),
        "results_interpretation": interp.get("results_interpretation"),
        "contribution_analysis": {
            "indicator": contribution.get("indicator"),
            "by_source": by_source[:8],
        },
        "impact_results": impact.get("results_table"),
        "single_score": single_summary,
        "midpoint_impacts": _midpoint_summary(assessment_data.get("midpoint_impacts")),
        "input_matches": _input_matches_summary(assessment_data.get("input_matches")),
        "data_quality_notes": (assessment_data.get("data_quality") or {}).get("notes"),
        "engine_notes": inv.get("notes") or [],
        "recommendations": assessment_data.get("recommendations") or [],
    }


def format_grounding_for_prompt(assessment_data: dict) -> str:
    """Serialize grounding payload as JSON for LLM prompts."""
    payload = build_grounding_payload(assessment_data)
    return json.dumps(payload, indent=2, default=str)
