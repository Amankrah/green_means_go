#!/usr/bin/env python3
"""
olca_common.py — shared, defensive mappers from olca-schema entities to the
canonical-store row dicts.

These operate on `olca_schema` dataclass instances, which are identical whether
they come from a JSON-LD zip (jsonld_reader) or a live openLCA IPC server
(ipc_reader). All attribute access is defensive: olca-schema field names have
shifted across versions, so we getattr with fallbacks rather than assume.

Pinned/expected: olca-schema >= 2.0 (GreenDelta). See requirements.txt.
"""
from __future__ import annotations

from typing import Any, Optional


def enum_str(v: Any) -> Optional[str]:
    """Enum -> its string value; pass through plain strings; None -> None."""
    if v is None:
        return None
    return getattr(v, "value", None) or getattr(v, "name", None) or str(v)


def ref_name(x: Any) -> Optional[str]:
    """A Ref/entity -> its name; a string -> itself; None -> None."""
    if x is None:
        return None
    if isinstance(x, str):
        return x
    return getattr(x, "name", None)


def ref_id(x: Any) -> Optional[str]:
    if x is None:
        return None
    if isinstance(x, str):
        return x
    return getattr(x, "id", None)


def category_str(entity: Any) -> Optional[str]:
    """openLCA category may be a path string or a Ref; normalise to a string."""
    cat = getattr(entity, "category", None)
    if cat is None:
        return None
    if isinstance(cat, str):
        return cat
    return getattr(cat, "name", None) or str(cat)


def is_elementary_ref(flow_ref: Any) -> bool:
    ft = enum_str(getattr(flow_ref, "flow_type", None))
    return ft == "ELEMENTARY_FLOW"


def flow_to_row(flow: Any) -> dict:
    return {
        "uid": getattr(flow, "id", None),
        "name": getattr(flow, "name", None),
        "category": category_str(flow),
        "flow_type": enum_str(getattr(flow, "flow_type", None)),
        "ref_unit": ref_name(getattr(flow, "ref_unit", None)),  # often None in full Flow; OK
        "cas": getattr(flow, "cas", None),
        "formula": getattr(flow, "formula", None),
    }


def process_to_rows(process: Any) -> tuple[dict, list[dict]]:
    """Return (process_row, [exchange_rows...])."""
    puid = getattr(process, "id", None)
    exchanges = getattr(process, "exchanges", None) or []

    proc = {
        "uid": puid,
        "name": getattr(process, "name", None),
        "category": category_str(process),
        "location": ref_name(getattr(process, "location", None)),
        "process_type": enum_str(getattr(process, "process_type", None)),
        "ref_flow": None,
        "ref_amount": None,
        "ref_unit": None,
    }

    ex_rows: list[dict] = []
    for ex in exchanges:
        flow_ref = getattr(ex, "flow", None)
        is_ref = bool(getattr(ex, "is_quantitative_reference", False))
        row = {
            "process_uid": puid,
            "flow_uid": ref_id(flow_ref),
            "flow_name": ref_name(flow_ref),
            "is_input": bool(getattr(ex, "is_input", False)),
            "is_elementary": is_elementary_ref(flow_ref),
            "is_reference": is_ref,
            "amount": getattr(ex, "amount", None),
            "unit": ref_name(getattr(ex, "unit", None)),
            "provider_process_uid": ref_id(getattr(ex, "default_provider", None)),
        }
        ex_rows.append(row)
        if is_ref:
            proc["ref_flow"] = row["flow_uid"]
            proc["ref_amount"] = row["amount"]
            proc["ref_unit"] = row["unit"]

    return proc, ex_rows


def impact_category_to_rows(cat: Any) -> tuple[dict, list[dict]]:
    """Return (category_row, [cf_rows...])."""
    cuid = getattr(cat, "id", None)
    factors = getattr(cat, "impact_factors", None) or []
    cat_row = {
        "uid": cuid,
        "name": getattr(cat, "name", None),
        "ref_unit": getattr(cat, "ref_unit", None) or getattr(cat, "reference_unit", None),
    }
    cf_rows: list[dict] = []
    for f in factors:
        flow_ref = getattr(f, "flow", None)
        cf_rows.append({
            "flow_uid": ref_id(flow_ref),
            "flow_name": ref_name(flow_ref),
            "factor": getattr(f, "value", None),
            "unit": ref_name(getattr(f, "unit", None)),
        })
    # drop CFs without a numeric factor
    cf_rows = [r for r in cf_rows if r["factor"] is not None]
    return cat_row, cf_rows
