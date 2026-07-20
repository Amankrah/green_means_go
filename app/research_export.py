"""
research_export.py — SI-ready JSON/CSV slices of a saved assessment payload.
"""
from __future__ import annotations

import csv
import io
from typing import Any, Optional


def build_export_json(
    *,
    assessment_id: str,
    a_type: str,
    title: Optional[str],
    payload: dict[str, Any],
    request_json: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Structured research export (not the full opaque wizard snapshot)."""
    ss = payload.get("single_score") or {}
    return {
        "id": assessment_id,
        "type": a_type,
        "title": title,
        "company_name": payload.get("company_name"),
        "country": payload.get("country"),
        "region": payload.get("region"),
        "assessment_date": payload.get("assessment_date"),
        "methodology": ss.get("methodology") if isinstance(ss, dict) else None,
        "single_score": ss,
        "midpoint_impacts": payload.get("midpoint_impacts") or {},
        "endpoint_impacts": payload.get("endpoint_impacts") or {},
        "functional_units": payload.get("functional_units"),
        "contribution_by_source": payload.get("contribution_by_source") or {},
        "contribution_sankey": payload.get("contribution_sankey"),
        "sensitivity_analysis": payload.get("sensitivity_analysis"),
        "input_matches": payload.get("input_matches") or [],
        "data_quality": payload.get("data_quality") or {},
        "breakdown_by_food": payload.get("breakdown_by_food") or {},
        "inventory": payload.get("inventory"),
        "request_meta": {
            "has_api": bool(request_json and request_json.get("api")),
            "has_form": bool(request_json and request_json.get("form")),
            "api_keys": sorted((request_json.get("api") or {}).keys())
            if request_json and isinstance(request_json.get("api"), dict)
            else [],
        },
        "baseline_assessment_id": payload.get("baseline_assessment_id"),
        "method_variants": payload.get("method_variants"),
        "uncertainty": payload.get("uncertainty"),
        "study_meta": payload.get("study_meta"),
        "review_status": payload.get("review_status"),
    }


def build_export_csv(export: dict[str, Any]) -> str:
    """Multi-section CSV: midpoints, matches, contribution_by_source (long)."""
    buf = io.StringIO()
    w = csv.writer(buf)

    w.writerow(["# midpoints"])
    w.writerow(["category", "value", "unit"])
    for cat, v in (export.get("midpoint_impacts") or {}).items():
        if isinstance(v, dict):
            w.writerow([cat, v.get("value"), v.get("unit")])
        else:
            w.writerow([cat, v, ""])

    w.writerow([])
    w.writerow(["# input_matches"])
    w.writerow(
        ["input", "amount", "amount_unit", "matched", "ref_unit", "score", "estimated", "kind"]
    )
    for m in export.get("input_matches") or []:
        if not isinstance(m, dict):
            continue
        matched = m.get("matched")
        matched_name = matched.get("name") if isinstance(matched, dict) else matched
        w.writerow(
            [
                m.get("input") or m.get("name"),
                m.get("amount"),
                m.get("amount_unit") or m.get("unit"),
                matched_name,
                m.get("ref_unit"),
                m.get("score"),
                m.get("estimated"),
                m.get("kind"),
            ]
        )

    w.writerow([])
    w.writerow(["# contribution_by_source"])
    w.writerow(["source", "category", "value", "unit"])
    for src, cats in (export.get("contribution_by_source") or {}).items():
        if not isinstance(cats, dict):
            continue
        for cat, v in cats.items():
            if isinstance(v, dict):
                w.writerow([src, cat, v.get("value"), v.get("unit")])
            else:
                w.writerow([src, cat, v, ""])

    return buf.getvalue()
