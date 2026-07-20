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
        # Full LCIA method name (not just the single-score methodology blurb) plus the
        # reproducibility stamp (engine build, dataset editions, field model) so a result
        # can be reproduced or diffed later. See engine/provenance.py.
        "lcia_method": payload.get("lcia_method"),
        "provenance": payload.get("provenance"),
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


CSV_SECTIONS = ("impacts", "matches", "contributions")


def _mid_unit(export: dict[str, Any], category: str) -> str:
    """Unit for a category from midpoint_impacts (authoritative). Never guessed."""
    m = (export.get("midpoint_impacts") or {}).get(category)
    return (m.get("unit") or "") if isinstance(m, dict) else ""


def _impacts_rows(export: dict[str, Any]):
    """Tidy long-format impact rows: (section, category, metric, value, unit)."""
    for cat, v in (export.get("midpoint_impacts") or {}).items():
        val = v.get("value") if isinstance(v, dict) else v
        unit = v.get("unit") if isinstance(v, dict) else ""
        yield ["midpoint", cat, "value", val, unit or ""]
    for cat, v in (export.get("endpoint_impacts") or {}).items():
        val = v.get("value") if isinstance(v, dict) else v
        unit = v.get("unit") if isinstance(v, dict) else ""
        yield ["endpoint", cat, "value", val, unit or ""]

    ss = export.get("single_score")
    if isinstance(ss, dict):
        su = ss.get("unit") or ""
        yield ["single_score", "single_score", "value", ss.get("value"), su]
        ur = ss.get("uncertainty_range")
        if isinstance(ur, (list, tuple)) and len(ur) == 2:
            yield ["single_score", "single_score", "p5", ur[0], su]
            yield ["single_score", "single_score", "p95", ur[1], su]

    unc = export.get("uncertainty")
    if isinstance(unc, dict):
        for cat, p in (unc.get("percentiles") or {}).items():
            if not isinstance(p, dict):
                continue
            u = _mid_unit(export, cat)
            for metric in ("p5", "base", "p50", "p95"):
                if p.get(metric) is not None:
                    yield ["uncertainty", cat, metric, p.get(metric), u]


def _write_impacts(w, export):
    w.writerow(["section", "category", "metric", "value", "unit"])
    for row in _impacts_rows(export):
        w.writerow(row)


def _write_matches(w, export):
    w.writerow(["input", "amount", "amount_unit", "matched", "ref_unit", "score", "estimated", "kind"])
    for m in export.get("input_matches") or []:
        if not isinstance(m, dict):
            continue
        matched = m.get("matched")
        matched_name = matched.get("name") if isinstance(matched, dict) else matched
        w.writerow([
            m.get("input") or m.get("name"),
            m.get("amount"),
            m.get("amount_unit") or m.get("unit"),
            matched_name,
            m.get("ref_unit"),
            m.get("score"),
            m.get("estimated"),
            m.get("kind"),
        ])


def _write_contributions(w, export):
    w.writerow(["source", "category", "value", "unit"])
    for src, cats in (export.get("contribution_by_source") or {}).items():
        if not isinstance(cats, dict):
            continue
        for cat, v in cats.items():
            val = v.get("value") if isinstance(v, dict) else v
            unit = v.get("unit") if isinstance(v, dict) else ""
            w.writerow([src, cat, val, unit or ""])


def build_export_csv(export: dict[str, Any], section: str = "impacts") -> str:
    """One tidy, rectangular table per section (loadable in a single pandas/R read_csv):

    - ``impacts``       long-format: section, category, metric, value, unit
                        (midpoints, endpoints, single score, MC percentiles)
    - ``matches``       one row per matched background process
    - ``contributions`` long-format contribution_by_source: source, category, value, unit

    A unit column is always present and never defaulted per category (units come from the
    stored values, blank when genuinely unknown)."""
    sec = (section or "impacts").lower()
    if sec not in CSV_SECTIONS:
        sec = "impacts"
    buf = io.StringIO()
    w = csv.writer(buf)
    {"impacts": _write_impacts, "matches": _write_matches,
     "contributions": _write_contributions}[sec](w, export)
    return buf.getvalue()


def build_cohort_csv(exports: list[dict[str, Any]]) -> str:
    """One tidy long-format table for a whole study cohort, loadable in a single read_csv:
    assessment_id, title, section, category, metric, value, unit. Each export is one
    assessment's build_export_json output; impact rows are prefixed with its id/title."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["assessment_id", "title", "section", "category", "metric", "value", "unit"])
    for export in exports:
        aid = export.get("id")
        title = export.get("title")
        for section, category, metric, value, unit in _impacts_rows(export):
            w.writerow([aid, title, section, category, metric, value, unit])
    return buf.getvalue()
