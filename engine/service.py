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

import copy
import threading
import uuid
from dataclasses import replace

try:
    from .orchestrator import FarmLCA, review_items
    from .regions import get_region
    from . import regions, crop_defaults
    from .inputs import extract_purchased_inputs, total_production_kg
    from .adapter import to_assessment_response
    from . import field_params, fuels, perennials
    from .commodities import reject_unsupported_farm_commodities, UnsupportedCommodityError  # noqa: F401
    from . import farm_flows
except ImportError:
    from orchestrator import FarmLCA, review_items
    from regions import get_region
    import regions
    import crop_defaults
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


def _applies_to(row, food_id) -> bool:
    """A fertiliser / pesticide / lime row with crop_ids [] applies to every crop
    (CONTRACT §1); otherwise only to the listed foods[].id."""
    ids = [str(i) for i in ((row or {}).get("crop_ids") or [])]
    return not ids or food_id is None or str(food_id) in ids


def attribute_to_crop(assessment: dict, food: dict) -> tuple[dict, list[str]]:
    """Copy of `assessment` keeping only the fertiliser, pesticide and lime rows applied to
    `food` (by crop_ids) and compost only when `food` is in compost_crop_ids ([] = all).
    ISO 14044 §4.3.4.2: subdivide the farm into per-crop systems instead of giving every
    crop the farm's input rates. Returns (assessment, notes)."""
    fid = food.get("id")
    name = food.get("name", "crop")
    mp = dict(assessment.get("management_practices") or {})
    notes: list[str] = []
    fert = dict(mp.get("fertilization") or {})
    rows = fert.get("fertilizer_applications") or []
    kept = [r for r in rows if _applies_to(r, fid)]
    if len(kept) != len(rows):
        notes.append(f"{name}: {len(rows) - len(kept)} fertiliser application(s) assigned to "
                     f"other crops excluded (crop_ids)")
        fert["fertilizer_applications"] = kept
        mp["fertilization"] = fert
    pm = dict(mp.get("pest_management") or {})
    for key in ("pesticides", "pesticides_used"):
        rows = pm.get(key) or []
        kept = [r for r in rows if not isinstance(r, dict) or _applies_to(r, fid)]
        if len(kept) != len(rows):
            notes.append(f"{name}: {len(rows) - len(kept)} pesticide application(s) assigned "
                         f"to other crops excluded (crop_ids)")
            pm[key] = kept
            mp["pest_management"] = pm
    sm = dict(mp.get("soil_management") or {})
    lime = sm.get("lime_applications") or []
    kept = [r for r in lime if _applies_to(r, fid)]
    changed_sm = False
    if len(kept) != len(lime):
        notes.append(f"{name}: {len(lime) - len(kept)} lime application(s) assigned to other "
                     f"crops excluded (crop_ids)")
        sm["lime_applications"] = kept
        changed_sm = True
    cids = [str(i) for i in (sm.get("compost_crop_ids") or [])]
    if sm.get("uses_compost") and cids and fid is not None and str(fid) not in cids:
        sm["uses_compost"] = False
        notes.append(f"{name}: compost applied to other crops only (compost_crop_ids); none "
                     f"attributed to this crop")
        changed_sm = True
    if changed_sm:
        mp["soil_management"] = sm
    if fid is None and any((r or {}).get("crop_ids") for r in
                           (fert.get("fertilizer_applications") or []) + lime):
        notes.append(f"validation warning: {name} has no foods[].id, so crop-specific "
                     f"input rows could not be attributed; all rows applied")
    out = dict(assessment)
    if assessment.get("management_practices") is not None or mp:
        out["management_practices"] = mp
    return out, notes


def _null_fertiliser(row) -> bool:
    """CONTRACT §1: a fertiliser row of type 'None' or with a zero rate / zero applications
    carries no burden in either the Python or the Rust path."""
    r = row or {}
    if str(r.get("fertilizer_type") or "").strip().lower() == "none":
        return True
    try:
        if float(r.get("application_rate") or 0) <= 0:
            return True
        aps = r.get("applications_per_season")
        return aps is not None and float(aps) <= 0
    except (TypeError, ValueError):
        return False


def drop_null_fertiliser(assessment: dict) -> tuple[dict, list[str]]:
    mp = assessment.get("management_practices") or {}
    fert = mp.get("fertilization") or {}
    rows = fert.get("fertilizer_applications") or []
    kept = [r for r in rows if not _null_fertiliser(r)]
    if len(kept) == len(rows):
        return assessment, []
    out = {**assessment, "management_practices": {
        **mp, "fertilization": {**fert, "fertilizer_applications": kept}}}
    return out, [f"{len(rows) - len(kept)} fertiliser row(s) of type 'None' or with a zero "
                 f"rate / zero applications skipped (no burden)"]


def _unassigned_rows(assessment: dict) -> list[str]:
    """Warnings for input rows whose crop_ids match no food (their burden would vanish)."""
    ids = {str(f.get("id")) for f in assessment.get("foods") or [] if f.get("id") is not None}
    if not ids:
        return []
    mp = assessment.get("management_practices") or {}
    groups = (("fertiliser", (mp.get("fertilization") or {}).get("fertilizer_applications")),
              ("pesticide", (mp.get("pest_management") or {}).get("pesticides")),
              ("lime", (mp.get("soil_management") or {}).get("lime_applications")))
    out = []
    for label, rows in groups:
        for r in rows or []:
            cids = {str(i) for i in ((r or {}).get("crop_ids") or [])}
            if cids and not (cids & ids):
                out.append(f"{WARNING_PREFIX}{label} row "
                           f"'{r.get('fertilizer_type') or r.get('active_ingredient') or r.get('material') or label}' "
                           f"lists crop_ids {sorted(cids)} that match no crop; excluded")
    return out


def _admin_region(assessment: dict) -> str | None:
    sm = assessment.get("study_meta") or {}
    return (sm.get("admin_region") or (assessment.get("farm_profile") or {}).get("region")
            or None)


def _climate_engine(eng, assessment: dict):
    """Per-run engine view whose region carries the IPCC wet/dry parameters of the farm's
    admin region (CONTRACT §2, regions.climate_zone_for) and, in Canada, prefers the farm's
    province among sub-national datasets. The cached engine is never mutated: a shallow
    copy shares the store, matcher and flow map. Returns (engine, note)."""
    admin = _admin_region(assessment)
    code = eng.region.code
    note = regions.climate_disclosure(code, admin)
    rec = regions.admin_climate(code, admin)
    region = regions.with_admin_locations(eng.region, admin)
    if rec and rec.get("wetness") in ("wet", "dry"):
        region = regions.with_climate(region, rec["wetness"])
        region = replace(region, field_sources={**region.field_sources, "climate_zone": note})
    if region is eng.region:
        return eng, note
    view = copy.copy(eng)
    view.region = region
    return view, note


def derive_seasons(assessment: dict, region_code: str) -> tuple[dict, list[str]]:
    """Fill a blank foods[].seasonal_factor from planting_months and the admin region's rainy
    season (CONTRACT §1, regions.rainy_season_months; rule in
    crop_defaults.derive_seasonal_factor). An explicit seasonal_factor always wins."""
    admin = _admin_region(assessment)
    rainy = regions.rainy_season_months(region_code, admin)
    foods, notes, changed = [], [], False
    for f in assessment.get("foods") or []:
        if f.get("seasonal_factor") or not isinstance(f, dict):
            foods.append(f)
            continue
        factor, note = crop_defaults.derive_seasonal_factor(f.get("planting_months"), rainy)
        if factor:
            f = {**f, "seasonal_factor": factor}
            changed = True
        notes.append(f"{f.get('name', 'crop')}: {note}")
        foods.append(f)
    if not changed:
        return assessment, notes
    return {**assessment, "foods": foods}, notes


def _soc_management(assessment: dict, region, res=None):
    """Soil carbon from management (engine/soil_carbon.py, E): reported separately per ISO
    14067, never in the headline (CONTRACT §2). Whole-farm record for multi-crop farms."""
    rec = getattr(res, "soc_management", None) if res is not None else None
    if rec is not None:
        return rec
    try:
        try:
            from . import soil_carbon
        except ImportError:
            import soil_carbon  # type: ignore
        return soil_carbon.soc_management(assessment, region)
    except (ImportError, AttributeError):
        return None


def _pass_throughs(res, eng, assessment: dict, soc, per_crop: dict | None = None) -> None:
    """Attributes engine/adapter.py copies to the response with getattr (F-lcia):
    soc_management, needs_review (farm level), climate_zone_used and per_crop_results (each
    crop's OWN product system: raw method categories, crop totals)."""
    if soc is not None:
        res.soc_management = soc
    if per_crop:
        foods = {_crop_label(f): f for f in assessment.get("foods") or []}
        res.per_crop_results = [
            {"label": label, "crop_id": (foods.get(label) or {}).get("id"),
             "quantity_kg": (foods.get(label) or {}).get("quantity_kg"),
             "area_ha": (foods.get(label) or {}).get("area_allocated"),
             "impacts_total": {c: dict(v) for c, v in r.impacts.items()},
             "needs_review": r.review_required}
            for label, r in per_crop.items()]
    res.needs_review = bool(review_items(res.input_matches))
    ef1 = eng.region.ipcc_n2o_ef1
    res.climate_zone_used = ("dry" if ef1 == regions.EF1_DRY else
                             "wet" if ef1 == regions.EF1_WET_SYNTHETIC else "aggregated")


def _distinct_products(foods: list[dict]) -> int:
    return len({" ".join(str(f.get("name") or "").lower().split()) for f in foods})


def _review_flag(out: dict) -> dict:
    """Publication gate: any background match flagged needs_review makes the whole result
    review_required, listed in data_quality.warnings (audit 3.17 / rec 27)."""
    items = review_items(out.get("input_matches") or [])
    out["review_required"] = bool(items)
    out["review_items"] = items
    if items:
        dq = out.setdefault("data_quality", {})
        warnings = list(dq.get("warnings") or [])
        msg = (f"{len(items)} background dataset match(es) need review before publication: "
               + "; ".join(f"'{i['input']}' -> '{i['matched']}'" for i in items[:5])
               + (" ..." if len(items) > 5 else ""))
        if msg not in warnings:
            warnings.append(msg)
        dq["warnings"] = warnings
    return out


def _farm_refrigerant_leakage(assessment: dict, method) -> float:
    """kg CO2e/yr of cold-store leakage the adapter books at farm level (inputs.refrigerant_
    leakage, D1/F); 0 when none."""
    try:
        try:
            from .inputs import refrigerant_leakage
        except ImportError:
            from inputs import refrigerant_leakage  # type: ignore
        rec = refrigerant_leakage(assessment, method) or {}
        return float(rec.get("kg_co2e") or 0.0)
    except Exception:
        return 0.0


def _per_crop_units(out: dict, assessment: dict) -> dict:
    """Functional units for a farm with several products: per-crop per-kg (each crop's own
    product system / its own kg) plus the farm per-ha. The farm per-kg headline divides the
    summed burden by summed kg of different crops, which is not a product footprint (ISO
    14044 §4.2.3.2); it is flagged, not removed, so existing clients keep working."""
    foods = assessment.get("foods") or []
    fu = out.setdefault("functional_units", {})
    multi = _distinct_products(foods) > 1
    per_crop = {}
    total_area = sum((f.get("area_allocated") or 0.0) for f in foods)
    leak = _farm_refrigerant_leakage(assessment, out.get("lcia_method"))
    for f in foods:
        qkg = f.get("quantity_kg") or 0.0
        label = f"{f.get('name', 'crop')} ({(qkg or 1.0):.0f}kg)"
        mids = dict((out.get("breakdown_by_food") or {}).get(label) or {})
        area = f.get("area_allocated") or 0.0
        gw = mids.get("Global warming")
        if leak and gw and total_area > 0:
            # farm cold-store leakage is booked once by the adapter at farm level; per crop it
            # follows the same area share as the refrigerant top-up input (_sub_assessment)
            mids["Global warming"] = {**gw, "value": (gw.get("value") or 0.0)
                                      + leak * area / total_area}
        per_crop[label] = {
            "crop_id": f.get("id"), "name": f.get("name"), "quantity_kg": qkg, "area_ha": area,
            "midpoint_impacts_per_kg": {
                c: {"value": (m.get("value") or 0.0) / qkg, "unit": f"{m.get('unit') or ''} per kg"}
                for c, m in mids.items()} if qkg else None,
            "midpoint_impacts_per_ha": {
                c: {"value": (m.get("value") or 0.0) / area, "unit": f"{m.get('unit') or ''} per ha"}
                for c, m in mids.items()} if area else None,
        }
    fu["per_crop"] = per_crop
    fu["headline"] = "per_ha" if multi else "per_kg"
    if isinstance(fu.get("per_kg"), dict):
        fu["per_kg"]["mixed_products"] = multi
    if multi:
        dq = out.setdefault("data_quality", {})
        warnings = list(dq.get("warnings") or [])
        msg = (f"farm grows {_distinct_products(foods)} different products: the farm per-kg "
               f"figures divide the summed burden by summed kg of different crops and are not "
               f"a product footprint; use the per-crop per-kg results "
               f"(functional_units.per_crop) or the farm per-ha results")
        if msg not in warnings:
            warnings.append(msg)
        dq["warnings"] = warnings
    return out


def _sub_assessment(assessment: dict, food: dict, share: float) -> dict:
    """Single-crop product system: that crop's food, only the fertiliser / pesticide / lime
    / compost rows attributed to it (attribute_to_crop), and its area-partitioned
    farm-level energy (fuel/electricity/equipment scaled by area share). Per-ha rates on
    the crop's own area drive its field emissions and inputs."""
    sub, _ = attribute_to_crop(assessment, food)
    sub["foods"] = [food]
    ee = assessment.get("equipment_energy")
    if ee:
        def scale(items, key):
            return [{**x, key: (x.get(key) or 0) * share} for x in (items or [])]
        sub["equipment_energy"] = {
            **ee,
            "fuel_consumption": scale(ee.get("fuel_consumption"), "monthly_consumption"),
            "energy_sources": scale(ee.get("energy_sources"), "monthly_consumption"),
            "equipment": scale(ee.get("equipment"), "hours_per_year"),
        }
        st = ee.get("storage")
        if isinstance(st, dict) and st.get("refrigerant_charge_kg"):
            # farm cold-store charge is a farm total, partitioned by area like energy
            sub["equipment_energy"]["storage"] = {
                **st, "refrigerant_charge_kg": st["refrigerant_charge_kg"] * share}
    # A measured farm irrigation volume is a farm total: partition it by area like energy.
    wm = ((sub.get("management_practices") or {}).get("water_management")) or {}
    if wm.get("irrigation_water_m3"):
        mp = dict(sub["management_practices"])
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
    return _review_flag(out)


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
    # admin-region IPCC wet/dry (EF1, EF4, FracLEACH) and season from planting months
    eng, climate_note = _climate_engine(eng, assessment)
    assessment, season_notes = derive_seasons(assessment, eng.region.code)
    assessment, null_notes = drop_null_fertiliser(assessment)
    run_notes = [climate_note] + season_notes + null_notes + _unassigned_rows(assessment)
    total = total_production_kg(assessment)
    foods = assessment.get("foods") or []
    total_area = sum((f.get("area_allocated") or 0) for f in foods)

    if len(foods) > 1 and total_area > 0:
        # Multiple product systems: report progress per crop rather than per input (per-input
        # index would reset each crop and read as going backwards). The inner assess_farm runs
        # without the fine-grained callback for the same reason. The farm result is the SUM
        # of the per-crop systems, each carrying only its own attributed inputs.
        _emit(on_progress, "inventory", "Building the life-cycle inventory")
        per_crop = {}
        n = len(foods)
        for ci, food in enumerate(foods):
            _emit(on_progress, "solve", detail=f"{food.get('name', 'crop')} ({ci + 1}/{n})",
                  index=ci + 1, total=n)
            share = (food.get("area_allocated") or 0) / total_area
            _, attr_notes = attribute_to_crop(assessment, food)
            sub = _sub_assessment(assessment, food, share)
            inputs, sub_in_notes = extract_purchased_inputs(sub)
            kernel_sub, inputs, prep_notes = prepare_farm_run(sub, inputs, eng.region)
            with lock:
                crop_res = eng.assess_farm(kernel_sub, inputs)
                farm_flows.apply(crop_res, eng, sub)   # pesticide AI, irrigation water, composting
            crop_res.notes = attr_notes + list(sub_in_notes) + prep_notes + crop_res.notes
            per_crop[_crop_label(food)] = crop_res
        _emit(on_progress, "characterize", "Characterizing impacts")
        farm = _sum_results(per_crop)
        soc = _soc_management(assessment, eng.region)
        _pass_throughs(farm, eng, assessment, soc, per_crop)
        if run_uncertainty:
            _emit(on_progress, "uncertainty", "Running pedigree screening Monte Carlo")
        _emit(on_progress, "report", "Compiling your report")
        out = to_assessment_response(
            farm, assessment, eng, total,
            assessment_id or str(uuid.uuid4()), run_notes, per_crop=per_crop,
            run_uncertainty=run_uncertainty,
            uncertainty_n=uncertainty_n,
            uncertainty_seed=uncertainty_seed,
        )
        out = _per_crop_units(out, assessment)
        if soc is not None:
            out["soc_management"] = soc
        return _review_flag(lift_validation_warnings(_with_metadata(assessment, out)))

    # single crop / no area -> one whole-farm system (fine-grained per-input progress)
    attr_notes: list[str] = []
    if len(foods) == 1:
        assessment, attr_notes = attribute_to_crop(assessment, foods[0])
    inputs, in_notes = extract_purchased_inputs(assessment)
    kernel_assessment, inputs, prep_notes = prepare_farm_run(assessment, inputs, eng.region)
    in_notes = run_notes + attr_notes + list(in_notes) + prep_notes
    with lock:
        res = eng.assess_farm(kernel_assessment, inputs, on_progress=on_progress)
        farm_flows.apply(res, eng, assessment)   # pesticide AI, irrigation water, composting
    soc = _soc_management(assessment, eng.region, res)
    _pass_throughs(res, eng, assessment, soc)
    if run_uncertainty:
        _emit(on_progress, "uncertainty", "Running pedigree screening Monte Carlo")
    _emit(on_progress, "report", "Compiling your report")
    out = to_assessment_response(
        res, assessment, eng, total,
        assessment_id or str(uuid.uuid4()), in_notes,
        run_uncertainty=run_uncertainty,
        uncertainty_n=uncertainty_n,
        uncertainty_seed=uncertainty_seed,
    )
    if len(foods) > 1:
        out = _per_crop_units(out, assessment)
    if soc is not None:
        out["soc_management"] = soc
    return _review_flag(lift_validation_warnings(_with_metadata(assessment, out)))
