#!/usr/bin/env python3
"""
regional_benchmark.py: compare farm land/yield against national screening yield guides.

GH: yield_guides_kg_per_ha from ghana_farm_activity_defaults.json (rainfed manual row,
MoFA/FAO). Other regions: the Region's yield_guide_file (FAOSTAT national means for SN, BF,
ZA) or, failing that, the rainfed row of the region's activity-defaults table (NG). A
region with neither gets no benchmark rather than Ghana's numbers.
"""
from __future__ import annotations

from typing import Any, Optional

import json
from pathlib import Path

try:
    from .activity_defaults import _table, is_ghana, region_of, table_path_for
except ImportError:
    from activity_defaults import _table, is_ghana, region_of, table_path_for  # type: ignore

_REF_DIR = Path(__file__).resolve().parent / "recommend" / "reference"

_HA_M2 = 10_000.0
_RAINFED_ROW_ID = "rainfed_manual"


def _rainfed_guide_row() -> dict[str, Any]:
    for row in _table().get("rows") or []:
        if row.get("id") == _RAINFED_ROW_ID:
            return row
    return {}


def _region_guides(region) -> tuple[dict, str, dict, str] | None:
    """(guides kg/ha by crop key, reference label, provenance, row id) for a non-GH region."""
    f = getattr(region, "yield_guide_file", None)
    if f and (_REF_DIR / f).is_file():
        d = json.loads((_REF_DIR / f).read_text(encoding="utf-8"))
        guides = {_crop_key(k): float(v["value"]) for k, v in (d.get("crops") or {}).items()
                  if isinstance(v, dict) and v.get("value")}
        return guides, d.get("title") or f, d.get("provenance") or {}, d.get("id") or f
    path = table_path_for(region)
    if path is not None and path.is_file():
        d = json.loads(path.read_text(encoding="utf-8"))
        for row in d.get("rows") or []:
            if row.get("id") == _RAINFED_ROW_ID and row.get("yield_guides_kg_per_ha"):
                return (dict(row["yield_guides_kg_per_ha"]),
                        f"{region.name} rainfed smallholder screening guides",
                        row.get("provenance") or {}, _RAINFED_ROW_ID)
    return None


def _crop_key(name: str) -> str:
    return str(name or "").strip().lower().replace(" ", "_")


def _guide_yield(guides: dict, crop_name: str, strict: bool = False) -> float | None:
    key = _crop_key(crop_name)
    if key in guides:
        return float(guides[key])
    if strict and "_default" not in guides:
        return None   # no national guide for this crop: do not invent one
    return float(guides.get("_default") or 1200)


def _midpoint_value(midpoints: dict | None, category: str) -> float | None:
    if not midpoints:
        return None
    raw = midpoints.get(category)
    if isinstance(raw, dict):
        return float(raw.get("value") or 0)
    if isinstance(raw, (int, float)):
        return float(raw)
    return None


def compute_regional_benchmark(
    assessment: dict,
    midpoints: dict | None = None,
) -> dict | None:
    """Return land/yield comparison vs the region's national yield guides, or None when
    the region has no guide table."""
    if is_ghana(assessment):
        row = _rainfed_guide_row()
        guides = row.get("yield_guides_kg_per_ha") or {}
        region_code, reference = "GH", "Ghana rainfed smallholder (MoFA/FAO screening guides)"
        provenance, row_id, strict = row.get("provenance") or {}, row.get("id") or _RAINFED_ROW_ID, False
    else:
        region = region_of(assessment)
        found = _region_guides(region) if region is not None else None
        if not found:
            return None
        guides, reference, provenance, row_id = found
        region_code, strict = region.code, True
    foods = assessment.get("foods") or []
    crops: list[dict[str, Any]] = []
    total_area = 0.0
    total_kg = 0.0

    for food in foods:
        area = float(food.get("area_allocated") or 0)
        qty = float(food.get("quantity_kg") or 0)
        name = food.get("name") or "crop"
        guide_yield = _guide_yield(guides, name, strict)
        actual_yield = (qty / area) if area > 0 else None
        yield_ratio = (actual_yield / guide_yield) if actual_yield and guide_yield else None
        guide_land_m2_per_kg = (_HA_M2 / guide_yield) if guide_yield else None
        crops.append({
            "crop": name,
            "area_ha": area,
            "quantity_kg": qty,
            "actual_yield_kg_per_ha": actual_yield,
            "guide_yield_kg_per_ha": guide_yield,
            "yield_ratio_vs_guide": yield_ratio,
            "guide_land_m2_per_kg": guide_land_m2_per_kg,
        })
        total_area += area
        total_kg += qty

    land_use_per_kg = _midpoint_value(midpoints, "Land use")
    aggregate_yield = (total_kg / total_area) if total_area > 0 else None
    if strict:
        # Area-weighted guide over the crops that have one (no national "_default").
        g_area = sum(c["area_ha"] for c in crops if c["guide_yield_kg_per_ha"])
        g_kg = sum(c["area_ha"] * c["guide_yield_kg_per_ha"] for c in crops if c["guide_yield_kg_per_ha"])
        aggregate_guide = (g_kg / g_area) if g_area > 0 else None
    else:
        aggregate_guide = _guide_yield(guides, "_default")
    aggregate_guide_land = (_HA_M2 / aggregate_guide) if aggregate_guide else None

    return {
        "region": region_code,
        "reference": reference,
        "guide_row_id": row_id,
        "provenance": provenance,
        "crops": crops,
        "aggregate": {
            "total_area_ha": total_area,
            "total_kg": total_kg,
            "actual_yield_kg_per_ha": aggregate_yield,
            "guide_yield_kg_per_ha": aggregate_guide,
            "yield_ratio_vs_guide": (
                (aggregate_yield / aggregate_guide) if aggregate_yield and aggregate_guide else None
            ),
            "land_use_m2_per_kg": land_use_per_kg,
            "guide_land_m2_per_kg": aggregate_guide_land,
            "land_ratio_vs_guide": (
                (land_use_per_kg / aggregate_guide_land)
                if land_use_per_kg and aggregate_guide_land
                else None
            ),
        },
    }
