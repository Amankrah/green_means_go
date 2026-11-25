#!/usr/bin/env python3
"""
service.py: one entry point that runs the full validated farm LCA and returns the
frontend AssessmentResponse shape. Used by the production /assess route (replacing the
Rust hardcoded-LCIA path) and by /farm/assess.

Engines are cached per (region, method) but all share ONE store connection and ONE
~300 MB matcher index per process; calls are serialised with a single lock (the shared
SQLite connection and matcher caches are not thread-safe; farm assessments are
low-frequency).
"""
from __future__ import annotations

import threading
import uuid

try:
    from .orchestrator import FarmLCA
    from .regions import get_region
    from .inputs import extract_purchased_inputs, total_production_kg
    from .adapter import to_assessment_response
    from . import field_params, fuels, perennials
    from .commodities import reject_unsupported_farm_commodities, UnsupportedCommodityError  # noqa: F401
    from . import farm_flows
except ImportError:
    from orchestrator import FarmLCA
    from regions import get_region
    from inputs import extract_purchased_inputs, total_production_kg
    from adapter import to_assessment_response
    import field_params
    import fuels
    import perennials
    from commodities import reject_unsupported_farm_commodities, UnsupportedCommodityError  # noqa: F401
    import farm_flows

WARNING_PREFIX = "validation warning: "


def prepare_farm_run(assessment: dict, inputs: list[dict], region) -> tuple[dict, list[dict], list[str]]:
    """Foreground preparation shared by every farm entry point (WS1):
      * region/climate IPCC 2019 soil-N parameters and perennial residue renewal injected
        for the Rust kernel (engine/field_params.py);
      * LPG/kerosene/firewood/charcoal split into production (kg) + direct combustion flows
        (engine/fuels.py), the flows riding on the assessment as `direct_combustion_lci`;
      * perennial establishment amortisation of the purchased inputs (engine/perennials.py).
    Returns (kernel_assessment, inputs, notes)."""
    kernel_assessment, notes = field_params.prepare_kernel_assessment(assessment, region)
    inputs, combustion, fuel_notes = fuels.expand_fuel_inputs(inputs)
    if combustion:
        kernel_assessment["direct_combustion_lci"] = combustion
    inputs, per_notes = perennials.scale_purchased_inputs(inputs, assessment)
    return kernel_assessment, inputs, notes + fuel_notes + per_notes


def lift_validation_warnings(response: dict) -> dict:
    """Copy notes carrying the validation-warning prefix into data_quality.warnings so the
    client shows them as warnings instead of burying them in the notes."""
    dq = response.get("data_quality")
    if not isinstance(dq, dict):
        return response
    warnings = list(dq.get("warnings") or [])
    for n in dq.get("notes") or []:
        if isinstance(n, str) and n.startswith(WARNING_PREFIX):
            w = n[len(WARNING_PREFIX):]
            if w not in warnings:
                warnings.append(w)
    dq["warnings"] = warnings
    return response

_engines: dict[str, FarmLCA] = {}
_build_lock = threading.Lock()
# Guards everything the engines share (store connection, matcher index and caches).
engine_lock = threading.Lock()
_shared: dict = {}


def shared_matcher():
    """The process-wide matcher (index loaded once); callers must hold `engine_lock`."""
    with _build_lock:
        m = _shared.get("matcher")
        if m is None:
            try:
                from ingestion.query import CanonicalQuery
                from ingestion.matching import ProcessMatcher
            except ImportError:
                from query import CanonicalQuery
                from matching import ProcessMatcher
            m = ProcessMatcher(CanonicalQuery())
            m.build_index()
            _shared["matcher"] = m
        return m


def _engine(region_code: str, method: str | None):
    key = f"{get_region(region_code).code}|{method or ''}"
    if key not in _engines:
        m = shared_matcher()
        with _build_lock:
            if key not in _engines:
                _engines[key] = FarmLCA(region_code, method=method, matcher=m, query=m.q)
    return _engines[key], engine_lock


def _region_of(assessment: dict, override: str | None) -> str:
    if override:
        # An explicit override must be a known region code or alias; the API maps the
        # ValueError to a 422 instead of letting a KeyError surface as a 500.
        try:
            return get_region(override).code
        except KeyError as e:
            raise ValueError(str(e)) from e
    # An explicit engine region (e.g. "SN" with the kernel country bucket "Global") wins
    # over the country; otherwise "Global" would resolve to CA.
    try:
        return get_region((assessment.get("region") or "").strip()).code
    except KeyError:
        pass
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
            eng, lock = _engine(rc, None)
            with lock:
                eng.q.characterize_flows({}, eng.method)   # builds the method's CF tables
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
    # A measured farm irrigation volume is a farm total: partition it by area like energy.
    wm = ((assessment.get("management_practices") or {}).get("water_management")) or {}
    if wm.get("irrigation_water_m3"):
        mp = dict(assessment["management_practices"])
        mp["water_management"] = {**wm, "irrigation_water_m3": wm["irrigation_water_m3"] * share}
        sub["management_practices"] = mp
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
        for src, flows in res.contribution_flows_by_source.items():
            dst = farm.contribution_flows_by_source.setdefault(src, {})
            for uid, r in flows.items():
                s = dst.setdefault(uid, {"name": r.get("name"), "unit": r.get("unit"), "amount": 0.0})
                s["amount"] += r.get("amount") or 0.0
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


def _with_metadata(assessment: dict, out: dict) -> dict:
    """Echo the wizard's report-only fields verbatim in the ISO report scope (they do not
    change the numbers; see engine/inputs.report_only_metadata)."""
    try:
        from .inputs import report_only_metadata
    except ImportError:
        from inputs import report_only_metadata
    iso = out.get("iso_report")
    if isinstance(iso, dict) and isinstance(iso.get("scope"), dict):
        iso["scope"]["reported_metadata"] = report_only_metadata(assessment)
    return out


def _emit(cb, stage: str, detail: str = "", index=None, total=None) -> None:
    if cb is None:
        return
    try:
        cb(stage, detail=detail, index=index, total=total)
    except Exception:
        pass


def recharacterize_from_payload(payload: dict, assessment: dict, method: str,
                                region: str | None = None) -> dict | None:
    """Re-characterize a saved assessment using the stored method-independent inventory.

    Skips the LCI/solve path and only runs characterization with ``method``. Requires the
    per-source flows (``engine_inventory_by_source``) so the contribution split, Top
    sources, and pedigree MC are rebuilt *for the new method* rather than carried over
    stale or zeroed. Returns a full AssessmentResponse-shaped dict, or None when the stored
    inventory is missing/pre-dates per-source persistence (caller then does a full re-solve)."""
    inv = payload.get("engine_inventory")
    flows_by_source = payload.get("engine_inventory_by_source")
    if not inv or not isinstance(inv, dict):
        return None
    # Without per-source flows we cannot honestly rebuild contribution/MC under the new
    # method; fall back to a full re-solve rather than emit stale or zeroed numbers.
    if not flows_by_source or not isinstance(flows_by_source, dict):
        return None
    try:
        from .orchestrator import AssessmentResult
    except ImportError:
        from orchestrator import AssessmentResult

    region_code = _region_of(assessment, region)
    eng, lock = _engine(region_code, method)
    total = total_production_kg(assessment)
    assessment_id = payload.get("id") or str(uuid.uuid4())

    field_label = "Field emissions (on-farm)"
    with lock:
        impacts = eng.q.characterize_flows(inv, method)
        # Re-characterize each source's raw flows with the NEW method.
        contribution_by_source = {
            src: eng.q.characterize_flows(flows, method)
            for src, flows in flows_by_source.items()
        }
        # Rebuild the on-farm / supply-chain split from the same raw flows.
        on_farm = eng.q.characterize_flows(flows_by_source.get(field_label) or {}, method)
        supply_flows: dict = {}
        for src, flows in flows_by_source.items():
            if src == field_label:
                continue
            for uid, r in (flows or {}).items():
                slot = supply_flows.setdefault(
                    uid, {"name": r.get("name"), "unit": r.get("unit"), "amount": 0.0})
                slot["amount"] += r.get("amount") or 0.0
        supply_chain = eng.q.characterize_flows(supply_flows, method)

    res = AssessmentResult(region=eng.region.name, method=method)
    res.impacts = impacts
    res.inventory = inv
    res.contribution_by_source = contribution_by_source
    res.contribution_flows_by_source = flows_by_source
    res.contribution = {"on_farm": on_farm, "supply_chain": supply_chain}
    res.input_matches = payload.get("input_matches") or []

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
    reject_unsupported_farm_commodities(assessment)
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
            kernel_sub, inputs, prep_notes = prepare_farm_run(sub, inputs, eng.region)
            with lock:
                crop_res = eng.assess_farm(kernel_sub, inputs)
                farm_flows.apply(crop_res, eng, sub)   # pesticide AI, irrigation water, composting
            crop_res.notes = prep_notes + crop_res.notes
            per_crop[_crop_label(food)] = crop_res
        _emit(on_progress, "characterize", "Characterizing impacts")
        farm = _sum_results(per_crop)
        if run_uncertainty:
            _emit(on_progress, "uncertainty", "Running pedigree screening Monte Carlo")
        _emit(on_progress, "report", "Compiling your report")
        return lift_validation_warnings(_with_metadata(assessment, to_assessment_response(
            farm, assessment, eng, total,
            assessment_id or str(uuid.uuid4()), per_crop=per_crop,
            run_uncertainty=run_uncertainty,
            uncertainty_n=uncertainty_n,
            uncertainty_seed=uncertainty_seed,
        )))

    # single crop / no area -> one whole-farm system (fine-grained per-input progress)
    inputs, in_notes = extract_purchased_inputs(assessment)
    kernel_assessment, inputs, prep_notes = prepare_farm_run(assessment, inputs, eng.region)
    in_notes = list(in_notes) + prep_notes
    with lock:
        res = eng.assess_farm(kernel_assessment, inputs, on_progress=on_progress)
        farm_flows.apply(res, eng, assessment)   # pesticide AI, irrigation water, composting
    if run_uncertainty:
        _emit(on_progress, "uncertainty", "Running pedigree screening Monte Carlo")
    _emit(on_progress, "report", "Compiling your report")
    return lift_validation_warnings(_with_metadata(assessment, to_assessment_response(
        res, assessment, eng, total,
        assessment_id or str(uuid.uuid4()), in_notes,
        run_uncertainty=run_uncertainty,
        uncertainty_n=uncertainty_n,
        uncertainty_seed=uncertainty_seed,
    )))
