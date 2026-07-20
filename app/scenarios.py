"""
scenarios.py — clone a saved farm assessment request, apply named patches, and
compute deltas vs the baseline payload (Tier 1 researcher scenario compare).
"""
from __future__ import annotations

import copy
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


ALLOWED_PATCH_KEYS = frozenset({"yield_scale", "n_rate_scale", "diesel_scale"})


class ScenarioPatch(BaseModel):
    """Scales applied to the archived AssessmentRequest API dump."""

    name: Optional[str] = None
    yield_scale: Optional[float] = Field(default=None, gt=0)
    n_rate_scale: Optional[float] = Field(default=None, gt=0)
    diesel_scale: Optional[float] = Field(default=None, gt=0)

    @field_validator("yield_scale", "n_rate_scale", "diesel_scale")
    @classmethod
    def _finite_positive(cls, v):
        if v is None:
            return v
        if v != v or v in (float("inf"), float("-inf")):  # NaN / inf
            raise ValueError("scale must be a finite positive number")
        return v

    def active_scales(self) -> dict[str, float]:
        out = {}
        for k in ALLOWED_PATCH_KEYS:
            v = getattr(self, k)
            if v is not None:
                out[k] = float(v)
        return out


def apply_scenario_patch(api_request: dict[str, Any], patch: ScenarioPatch) -> dict[str, Any]:
    """Deep-copy the archived API request and apply yield / N / diesel scales."""
    scales = patch.active_scales()
    if not scales:
        raise ValueError("At least one of yield_scale, n_rate_scale, diesel_scale is required")

    req = copy.deepcopy(api_request)

    if "yield_scale" in scales:
        s = scales["yield_scale"]
        for food in req.get("foods") or []:
            if food.get("quantity_kg") is not None:
                food["quantity_kg"] = float(food["quantity_kg"]) * s

    if "n_rate_scale" in scales:
        s = scales["n_rate_scale"]
        fert = ((req.get("management_practices") or {}).get("fertilization") or {})
        for app in fert.get("fertilizer_applications") or []:
            if app.get("application_rate") is not None:
                app["application_rate"] = float(app["application_rate"]) * s

    if "diesel_scale" in scales:
        s = scales["diesel_scale"]
        ee = req.get("equipment_energy") or {}
        for fuel in ee.get("fuel_consumption") or []:
            if fuel.get("monthly_consumption") is not None:
                fuel["monthly_consumption"] = float(fuel["monthly_consumption"]) * s
        for eq in ee.get("equipment") or []:
            if (eq.get("power_source") or "").lower().find("diesel") >= 0:
                if eq.get("hours_per_year") is not None:
                    eq["hours_per_year"] = float(eq["hours_per_year"]) * s

    return req


def _midpoint_value(midpoints: dict, *keys: str) -> Optional[float]:
    for k in keys:
        m = (midpoints or {}).get(k)
        if isinstance(m, dict) and m.get("value") is not None:
            return float(m["value"])
        if isinstance(m, (int, float)):
            return float(m)
    return None


def _single_score_value(payload: dict) -> Optional[float]:
    s = payload.get("single_score")
    if isinstance(s, dict):
        v = s.get("value")
        return float(v) if v is not None else None
    if isinstance(s, (int, float)):
        return float(s)
    return None


def compute_scenario_deltas(baseline: dict, scenario: dict) -> dict[str, Any]:
    """Delta midpoints (scenario − baseline) and single-score delta."""
    b_mid = baseline.get("midpoint_impacts") or {}
    s_mid = scenario.get("midpoint_impacts") or {}
    keys = sorted(set(b_mid) | set(s_mid))
    delta_midpoints: dict[str, Any] = {}
    for k in keys:
        bv = _midpoint_value(b_mid, k)
        sv = _midpoint_value(s_mid, k)
        if bv is None or sv is None:
            continue
        unit = None
        sm = s_mid.get(k)
        if isinstance(sm, dict):
            unit = sm.get("unit")
        delta_midpoints[k] = {"value": sv - bv, "unit": unit, "baseline": bv, "scenario": sv}

    b_ss = _single_score_value(baseline)
    s_ss = _single_score_value(scenario)
    delta_ss = None if b_ss is None or s_ss is None else s_ss - b_ss

    return {
        "delta_midpoints": delta_midpoints,
        "delta_single_score": delta_ss,
        "baseline_single_score": b_ss,
        "scenario_single_score": s_ss,
    }


def default_scenario_title(patch: ScenarioPatch) -> str:
    if patch.name:
        return f"Scenario: {patch.name}"
    parts = [f"{k}={v:g}" for k, v in sorted(patch.active_scales().items())]
    return "Scenario: " + ", ".join(parts)
