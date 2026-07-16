#!/usr/bin/env python3
"""
service.py — one entry point that runs the full validated farm LCA and returns the
frontend AssessmentResponse shape. Used by the production /assess route (replacing the
Rust hardcoded-LCIA path) and by /farm/assess.

Engines are cached per region (the matcher index is ~300 MB); calls are serialised per
engine with a lock (SQLite is not thread-safe; farm assessments are low-frequency).
"""
from __future__ import annotations

import threading
import uuid

try:
    from .orchestrator import FarmLCA
    from .regions import get_region
    from .inputs import extract_purchased_inputs, total_production_kg
    from .adapter import to_assessment_response
except ImportError:
    from orchestrator import FarmLCA
    from regions import get_region
    from inputs import extract_purchased_inputs, total_production_kg
    from adapter import to_assessment_response

_engines: dict[str, FarmLCA] = {}
_locks: dict[str, threading.Lock] = {}
_build_lock = threading.Lock()


def _engine(region_code: str, method: str | None):
    key = f"{get_region(region_code).code}|{method or ''}"
    if key not in _engines:
        with _build_lock:
            if key not in _engines:
                _engines[key] = FarmLCA(region_code, method=method)
                _locks[key] = threading.Lock()
    return _engines[key], _locks[key]


def _region_of(assessment: dict, override: str | None) -> str:
    if override:
        return override
    country = (assessment.get("country") or "").strip()
    try:
        return get_region(country).code
    except KeyError:
        return "GH"   # default; regions registry is the single source of truth


def warm(regions=("GH",)) -> None:
    """Pre-build engines (loads the ~300 MB matcher index) so the first real request is
    fast. Safe to call from a background thread at app startup."""
    for rc in regions:
        try:
            _engine(rc, None)
        except Exception:
            pass


def _crop_label(food: dict) -> str:
    return f"{food.get('name', 'crop')} ({(food.get('quantity_kg') or 0):.0f}kg)"


def _sub_assessment(assessment: dict, food: dict, share: float) -> dict:
    """Single-crop product system: that crop's food + its area-partitioned farm-level
    energy (fuel/electricity/equipment scaled by area share). Fertiliser is per-ha, so
    the single-crop area drives the correct field emissions and fertiliser inputs."""
    sub = dict(assessment)
    sub["foods"] = [food]
    ee = assessment.get("equipment_energy")
    if ee:
        def scale(items, key):
            return [{**x, key: (x.get(key) or 0) * share} for x in (items or [])]
        sub["equipment_energy"] = {
            "fuel_consumption": scale(ee.get("fuel_consumption"), "monthly_consumption"),
            "energy_sources": scale(ee.get("energy_sources"), "monthly_consumption"),
            "equipment": scale(ee.get("equipment"), "hours_per_year"),
        }
    return sub


def _sum_results(per_crop: dict):
    """Aggregate per-crop AssessmentResults into one whole-farm result."""
    try:
        from .orchestrator import AssessmentResult
    except ImportError:
        from orchestrator import AssessmentResult
    farm = AssessmentResult(region="", method="")
    for res in per_crop.values():
        farm.region, farm.method = res.region, res.method
        for cat, v in res.impacts.items():
            slot = farm.impacts.setdefault(cat, {"value": 0.0, "unit": v.get("unit")})
            slot["value"] += v["value"]
        for area, imp in res.contribution.items():
            dst = farm.contribution.setdefault(area, {})
            for cat, v in imp.items():
                s = dst.setdefault(cat, {"value": 0.0, "unit": v.get("unit")})
                s["value"] += v["value"]
        for src, imp in res.contribution_by_source.items():
            dst = farm.contribution_by_source.setdefault(src, {})
            for cat, v in imp.items():
                s = dst.setdefault(cat, {"value": 0.0, "unit": v.get("unit")})
                s["value"] += v["value"]
        for uid, r in res.inventory.items():
            slot = farm.inventory.setdefault(uid, {"name": r["name"], "unit": r["unit"], "amount": 0.0})
            slot["amount"] += r["amount"]
        farm.input_matches += res.input_matches
        farm.notes += res.notes
    # collapse identical notes repeated once per crop (e.g. "field N2O scaled …",
    # "dropped N upstream …"); genuinely per-crop notes (different compost N amounts)
    # differ as strings and are preserved.
    seen: set[str] = set()
    farm.notes = [n for n in farm.notes if not (n in seen or seen.add(n))]
    return farm


def run_farm_assessment(assessment: dict, region: str | None = None,
                        method: str | None = None, assessment_id: str | None = None) -> dict:
    """Full path: auto-extract inputs -> Rust field LCI + supply-chain solve ->
    validated characterization -> AssessmentResponse dict. With multiple crops, each is
    run as its OWN product system (true per-crop) and summed for the farm total."""
    region_code = _region_of(assessment, region)
    eng, lock = _engine(region_code, method)
    total = total_production_kg(assessment)
    foods = assessment.get("foods") or []
    total_area = sum((f.get("area_allocated") or 0) for f in foods)

    if len(foods) > 1 and total_area > 0:
        per_crop = {}
        for food in foods:
            share = (food.get("area_allocated") or 0) / total_area
            sub = _sub_assessment(assessment, food, share)
            inputs, _ = extract_purchased_inputs(sub)
            with lock:
                per_crop[_crop_label(food)] = eng.assess_farm(sub, inputs)
        farm = _sum_results(per_crop)
        return to_assessment_response(farm, assessment, eng, total,
                                      assessment_id or str(uuid.uuid4()), per_crop=per_crop)

    # single crop / no area -> one whole-farm system
    inputs, in_notes = extract_purchased_inputs(assessment)
    with lock:
        res = eng.assess_farm(assessment, inputs)
    return to_assessment_response(res, assessment, eng, total,
                                  assessment_id or str(uuid.uuid4()), in_notes)
