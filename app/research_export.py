"""
research_export.py: SI-ready JSON/CSV slices of a saved assessment payload, including the
full elementary-flow inventory per functional unit and a Brightway-compatible (bw2io dict)
foreground model so an LCA practitioner can reproduce the study.
"""
from __future__ import annotations

import csv
import io
from typing import Any, Optional

FIELD_SOURCE = "Field emissions (on-farm)"
BACKGROUND_DB = "ecoinvent-3.11-cutoff"
BIOSPHERE_DB = "biosphere3"


def _total_kg(payload: dict[str, Any]) -> Optional[float]:
    fu = (payload.get("functional_units") or {}).get("per_kg") or {}
    try:
        v = float(fu.get("total_kg")) if fu.get("total_kg") else None
    except (TypeError, ValueError):
        v = None
    return v if v and v > 0 else None


def _categories(compartment: Optional[str]) -> list[str]:
    """'Emission to air/low population density' -> ['air', 'low population density']."""
    if not compartment:
        return []
    parts = [p.strip() for p in compartment.split("/") if p.strip()]
    if parts and parts[0].lower().startswith("emission to "):
        parts[0] = parts[0][len("emission to "):]
    elif parts and parts[0].lower() == "resource":
        parts[0] = "natural resource"
    return parts


def inventory_per_fu(payload: dict[str, Any]) -> dict[str, Any]:
    """Full merged elementary-flow inventory (cradle-to-gate LCI) per functional unit."""
    inv = payload.get("engine_inventory") or {}
    kg = _total_kg(payload)
    rows = []
    for uid, r in inv.items():
        if not isinstance(r, dict):
            continue
        amt = r.get("amount")
        rows.append({
            "uuid": uid, "name": r.get("name"), "compartment": r.get("compartment"),
            "cas": r.get("cas"), "unit": r.get("unit"),
            "amount_per_fu": (amt / kg) if (kg and isinstance(amt, (int, float))) else None,
            "amount_total": amt,
        })
    rows.sort(key=lambda x: (x["compartment"] or "", x["name"] or ""))
    return {
        "functional_unit": "1 kg product at the farm gate" if kg else "whole study (total kg unknown)",
        "total_kg": kg,
        "allocation_note": ("Inventory is BEFORE any co-product allocation; multiply by the allocation "
                            "factor in 'coproduct_allocation' to match the allocated impacts."
                            if any((a or {}).get("applied") for a in (payload.get("coproduct_allocation") or {}).values())
                            else None),
        "n_flows": len(rows),
        "flows": rows,
    }


def brightway_export(payload: dict[str, Any], assessment_id: str) -> dict[str, Any]:
    """bw2io-style dict of the FOREGROUND unit process per kg product: production exchange,
    biosphere exchanges (on-farm sources, store UUIDs = ecoinvent/EF elementary-flow UUIDs),
    and technosphere exchanges to the matched background datasets (store process UUIDs)."""
    kg = _total_kg(payload) or 1.0
    db = f"gmg_{assessment_id}"
    exchanges: list[dict[str, Any]] = [
        {"type": "production", "amount": 1.0, "unit": "kilogram", "input": [db, assessment_id]}]
    inv_meta = payload.get("engine_inventory") or {}
    by_src = payload.get("engine_inventory_by_source") or {}
    matched_inputs = {(m.get("input") or m.get("name")) for m in (payload.get("input_matches") or [])
                      if isinstance(m, dict) and m.get("matched")}
    for src, flows in by_src.items():
        if src in matched_inputs:
            continue                    # background: represented by the technosphere link below
        for uid, r in (flows or {}).items():
            meta = inv_meta.get(uid) or {}
            amt = r.get("amount")
            if not isinstance(amt, (int, float)) or not amt:
                continue
            exchanges.append({
                "type": "biosphere", "name": meta.get("name") or r.get("name"),
                "categories": _categories(meta.get("compartment")),
                "unit": r.get("unit"), "amount": amt / kg,
                "CAS number": meta.get("cas"), "input": [BIOSPHERE_DB, uid],
                "comment": f"on-site source: {src}",
            })
    for m in payload.get("input_matches") or []:
        if not isinstance(m, dict) or not m.get("matched") or m.get("excluded"):
            continue
        amt = m.get("solve_amount", m.get("amount"))
        exchanges.append({
            "type": "technosphere",
            "name": m.get("matched") if isinstance(m.get("matched"), str) else (m.get("matched") or {}).get("name"),
            "location": m.get("location"),
            "unit": m.get("ref_unit") or m.get("amount_unit") or m.get("unit"),
            "amount": (amt / kg) if isinstance(amt, (int, float)) else None,
            "input": [BACKGROUND_DB, m.get("uid")] if m.get("uid") else None,
            "comment": (f"declared input '{m.get('input')}'"
                        + (f"; amount in declared unit {m.get('amount_unit')}, check against ref unit"
                           if m.get("amount_unit") and m.get("ref_unit") and m.get("amount_unit") != m.get("ref_unit")
                           and "solve_amount" not in m else "")
                        + ("; NEEDS REVIEW" if m.get("needs_review") else "")),
        })
    return {
        "format": ("brightway2 bw2io importer list (each activity has 'database' and 'code'; "
                   "{(a['database'], a['code']): a for a in data} is the bw2data.Database.write dict)"),
        "database": db,
        "background_database": BACKGROUND_DB,
        "biosphere_database": BIOSPHERE_DB,
        "lcia_method": payload.get("lcia_method"),
        "data": [{
            "database": db, "code": assessment_id,
            "name": payload.get("title") or f"farm product system {assessment_id}",
            "unit": "kilogram", "location": payload.get("region") or payload.get("country"),
            "reference product": "farm-gate crop (per kg, as harvested)",
            "exchanges": exchanges,
        }],
        "note": ("Biosphere 'input' keys are the canonical-store elementary-flow UUIDs (ecoinvent / "
                 "EF nomenclature); technosphere keys are the store's process UUIDs of the matched "
                 "ecoinvent 3.11 cut-off datasets. Map to your local database names before writing. "
                 "On-site refrigerant leakage, grid calibration and co-product allocation are "
                 "applied in the engine and listed in 'notes' / 'coproduct_allocation'."),
    }


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
        # Full LCI per functional unit (UUID, name, compartment, CAS, unit, amount) and a
        # Brightway-compatible foreground model for reproduction outside this engine.
        "inventory_per_fu": inventory_per_fu(payload),
        "brightway": brightway_export(payload, assessment_id),
        "coproduct_allocation": payload.get("coproduct_allocation"),
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


CSV_SECTIONS = ("impacts", "matches", "contributions", "inventory", "brightway")


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


def _write_inventory(w, export):
    w.writerow(["uuid", "name", "compartment", "cas", "unit", "amount_per_fu", "amount_total"])
    for r in (export.get("inventory_per_fu") or {}).get("flows") or []:
        w.writerow([r.get("uuid"), r.get("name"), r.get("compartment"), r.get("cas"),
                    r.get("unit"), r.get("amount_per_fu"), r.get("amount_total")])


def _write_brightway(w, export):
    """Flat exchange table of the foreground activity (bw2io CSV-importer style columns)."""
    w.writerow(["type", "name", "categories", "location", "unit", "amount", "database", "code",
                "cas", "comment"])
    bw = export.get("brightway") or {}
    for act in bw.get("data") or []:
        for ex in act.get("exchanges") or []:
            inp = ex.get("input") or [None, None]
            w.writerow([ex.get("type"), ex.get("name") or act.get("name"),
                        "::".join(ex.get("categories") or []), ex.get("location"), ex.get("unit"),
                        ex.get("amount"), inp[0], inp[1], ex.get("CAS number"), ex.get("comment")])


def build_export_csv(export: dict[str, Any], section: str = "impacts") -> str:
    """One tidy, rectangular table per section (loadable in a single pandas/R read_csv):

    - ``impacts``       long-format: section, category, metric, value, unit
                        (midpoints, endpoints, single score, MC percentiles)
    - ``matches``       one row per matched background process
    - ``contributions`` long-format contribution_by_source: source, category, value, unit
    - ``inventory``     full elementary-flow LCI per functional unit (uuid, compartment, CAS)
    - ``brightway``     foreground exchanges (production / biosphere / technosphere)

    A unit column is always present and never defaulted per category (units come from the
    stored values, blank when genuinely unknown)."""
    sec = (section or "impacts").lower()
    if sec not in CSV_SECTIONS:
        sec = "impacts"
    buf = io.StringIO()
    w = csv.writer(buf)
    {"impacts": _write_impacts, "matches": _write_matches,
     "contributions": _write_contributions, "inventory": _write_inventory,
     "brightway": _write_brightway}[sec](w, export)
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
