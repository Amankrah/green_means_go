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


def _emit(cb, stage: str, detail: str = "", index=None, total=None) -> None:
    if cb is None:
        return
    try:
        cb(stage, detail=detail, index=index, total=total)
    except Exception:
        pass


def recharacterize_from_payload(payload: dict, assessment: dict, method: str,
                                region: str | None = None) -> dict | None:
    """Re-characterize a saved assessment using stored ``engine_inventory`` when present.

    Skips the LCI/solve path and only runs characterization with ``method``. Returns a
    full AssessmentResponse-shaped dict, or None when no stored inventory exists."""
    inv = payload.get("engine_inventory")
    if not inv or not isinstance(inv, dict):
        return None
    try:
        from .orchestrator import AssessmentResult
    except ImportError:
        from orchestrator import AssessmentResult

    region_code = _region_of(assessment, region)
    eng, lock = _engine(region_code, method)
    total = total_production_kg(assessment)
    assessment_id = payload.get("id") or str(uuid.uuid4())

    with lock:
        impacts = eng.q.characterize_flows(inv, method)

    res = AssessmentResult(region=eng.region.name, method=method)
    res.impacts = impacts
    res.inventory = inv
    contrib = (payload.get("sensitivity_analysis") or {}).get("contribution")
    if isinstance(contrib, dict):
        res.contribution = contrib

    out = to_assessment_response(res, assessment, eng, total, assessment_id)
    out["id"] = assessment_id
    return out


def run_farm_assessment(assessment: dict, region: str | None = None,
                        method: str | None = None, assessment_id: str | None = None,
                        on_progress=None, run_uncertainty: bool = True,
                        uncertainty_n: int | None = None,
                        uncertainty_seed: int | None = None) -> dict:
    """Full path: auto-extract inputs -> Rust field LCI + supply-chain solve ->
    validated characterization -> AssessmentResponse dict. With multiple crops, each is
    run as its OWN product system (true per-crop) and summed for the farm total.

    on_progress(stage, detail, index, total): optional callback for live progress.
    run_uncertainty: when True (default), attach pedigree screening Monte Carlo
    percentiles (N from engine.uncertainty.DEFAULT_N unless overridden)."""
    _emit(on_progress, "prepare", "Reading your farm data")
    region_code = _region_of(assessment, region)
    eng, lock = _engine(region_code, method)
    total = total_production_kg(assessment)
    foods = assessment.get("foods") or []
    total_area = sum((f.get("area_allocated") or 0) for f in foods)

    if len(foods) > 1 and total_area > 0:
        # Multiple product systems: report progress per crop rather than per input (per-input
        # index would reset each crop and read as going backwards). The inner assess_farm runs
        # without the fine-grained callback for the same reason.
        _emit(on_progress, "inventory", "Building the life-cycle inventory")
        per_crop = {}
        n = len(foods)
        for ci, food in enumerate(foods):
            _emit(on_progress, "solve", detail=f"{food.get('name', 'crop')} ({ci + 1}/{n})",
                  index=ci + 1, total=n)
            share = (food.get("area_allocated") or 0) / total_area
            sub = _sub_assessment(assessment, food, share)
            inputs, _ = extract_purchased_inputs(sub)
            with lock:
                per_crop[_crop_label(food)] = eng.assess_farm(sub, inputs)
        _emit(on_progress, "characterize", "Characterizing impacts")
        farm = _sum_results(per_crop)
        if run_uncertainty:
            _emit(on_progress, "uncertainty", "Running pedigree screening Monte Carlo")
        _emit(on_progress, "report", "Compiling your report")
        return to_assessment_response(
            farm, assessment, eng, total,
            assessment_id or str(uuid.uuid4()), per_crop=per_crop,
            run_uncertainty=run_uncertainty,
            uncertainty_n=uncertainty_n,
            uncertainty_seed=uncertainty_seed,
        )

    # single crop / no area -> one whole-farm system (fine-grained per-input progress)
    inputs, in_notes = extract_purchased_inputs(assessment)
    with lock:
        res = eng.assess_farm(assessment, inputs, on_progress=on_progress)
    if run_uncertainty:
        _emit(on_progress, "uncertainty", "Running pedigree screening Monte Carlo")
    _emit(on_progress, "report", "Compiling your report")
    return to_assessment_response(
        res, assessment, eng, total,
        assessment_id or str(uuid.uuid4()), in_notes,
        run_uncertainty=run_uncertainty,
        uncertainty_n=uncertainty_n,
        uncertainty_seed=uncertainty_seed,
    )
