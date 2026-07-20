#!/usr/bin/env python3
"""
process_service.py — one entry point that runs the full validated PROCESSING (facility)
LCA and returns the frontend response shape. Parallels service.run_farm_assessment, and
reuses the same per-region cached engine (the matcher index is ~300 MB).

A facility has no field emissions, so we call the generic FarmLCA.assess() with
on_farm_lci=[] and the purchased utilities/materials extracted from the request.
"""
from __future__ import annotations

import uuid

try:
    from .service import _engine
    from .regions import get_region
    from .process_inputs import extract_processing_inputs
    from .process_adapter import to_process_response
except ImportError:
    from service import _engine
    from regions import get_region
    from process_inputs import extract_processing_inputs
    from process_adapter import to_process_response


def _resolve_region(request: dict, override: str | None) -> str:
    """Resolve to a known region code, tolerating free-text region names (e.g. a province or
    'Greater Accra'): try the override, then the request region, then the country, else default.

    Canada is submitted as country \"Global\" + region \"CA\". If a free-text province overwrote
    the region code and nothing resolves, prefer CA over the Ghana default — otherwise Canada
    assessments silently run on Ghana backgrounds.
    """
    for cand in (override, request.get("region"), request.get("country")):
        if not cand:
            continue
        try:
            return get_region(str(cand).strip()).code
        except KeyError:
            continue
    country = str(request.get("country") or "").strip().lower()
    if country in ("global", "canada", "ca"):
        return "CA"
    return "GH"   # regions registry is the single source of truth for the default


def _emit(cb, stage: str, detail: str = "", index=None, total=None) -> None:
    if cb is None:
        return
    try:
        cb(stage, detail=detail, index=index, total=total)
    except Exception:
        pass


def run_process_assessment(request: dict, region: str | None = None,
                           method: str | None = None, assessment_id: str | None = None,
                           on_progress=None, run_uncertainty: bool = False,
                           uncertainty_n: int | None = None,
                           uncertainty_seed: int | None = None) -> dict:
    """Full path: extract purchased utilities/materials -> supply-chain solve (no field
    emissions) -> validated characterization -> processing response dict.

    on_progress(stage, detail, index, total): optional callback for live progress.
    run_uncertainty: when True, attach pedigree screening Monte Carlo percentiles."""
    _emit(on_progress, "prepare", "Reading your facility data")
    region_code = _resolve_region(request, region)
    eng, lock = _engine(region_code, method)
    inputs, notes, total_kg = extract_processing_inputs(request)
    _emit(on_progress, "inventory", "Building the life-cycle inventory")
    with lock:
        res = eng.assess(on_farm_lci=[], purchased_inputs=inputs, on_progress=on_progress)
    if run_uncertainty:
        _emit(on_progress, "uncertainty", "Running pedigree screening Monte Carlo")
    _emit(on_progress, "report", "Compiling your report")
    return to_process_response(res, request, eng, total_kg,
                               assessment_id or str(uuid.uuid4()), notes,
                               run_uncertainty=run_uncertainty,
                               uncertainty_n=uncertainty_n,
                               uncertainty_seed=uncertainty_seed)
