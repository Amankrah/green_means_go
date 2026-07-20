#!/usr/bin/env python3
"""
regional_benchmark.py — compare farm land/yield against Ghana MoFA rainfed screening guides.

Uses yield_guides_kg_per_ha from ghana_farm_activity_defaults.json (rainfed manual row)
as the reference cohort benchmark for GH assessments.
"""
from __future__ import annotations

from typing import Any, Optional

try:
    from .activity_defaults import _table, is_ghana
except ImportError:
    from activity_defaults import _table, is_ghana  # type: ignore

_HA_M2 = 10_000.0
_RAINFED_ROW_ID = "rainfed_manual"


def _rainfed_guide_row() -> dict[str, Any]:
    for row in _table().get("rows") or []:
        if row.get("id") == _RAINFED_ROW_ID:
            return row
    return {}


def _crop_key(name: str) -> str:
    return str(name or "").strip().lower().replace(" ", "_")


def _guide_yield(guides: dict, crop_name: str) -> float:
    key = _crop_key(crop_name)
    if key in guides:
        return float(guides[key])
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
    """Return land/yield comparison vs Ghana rainfed MoFA guide, or None if not GH."""
    if not is_ghana(assessment):
        return None

    row = _rainfed_guide_row()
    guides = row.get("yield_guides_kg_per_ha") or {}
    foods = assessment.get("foods") or []
    crops: list[dict[str, Any]] = []
    total_area = 0.0
    total_kg = 0.0

    for food in foods:
        area = float(food.get("area_allocated") or 0)
        qty = float(food.get("quantity_kg") or 0)
        name = food.get("name") or "crop"
        guide_yield = _guide_yield(guides, name)
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
    aggregate_guide = _guide_yield(guides, "_default")
    aggregate_guide_land = (_HA_M2 / aggregate_guide) if aggregate_guide else None

    return {
        "region": "GH",
        "reference": "Ghana rainfed smallholder (MoFA/FAO screening guides)",
        "guide_row_id": row.get("id") or _RAINFED_ROW_ID,
        "provenance": row.get("provenance") or {},
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
