from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from typing import Dict, Any, Optional
from datetime import datetime
import json
import os
import sys
import tempfile
import subprocess
from pathlib import Path

from sqlalchemy.orm import Session

from db import get_db
from assessment_stream import stream_assessment, SSE_MEDIA_TYPE, SSE_HEADERS
from models import Assessment, AssessmentType, Farm, User
from auth.deps import get_current_user
from store import (
    ConcurrencyError,
    get_owned_assessment,
    list_owned_assessments,
    replace_assessment,
    save_assessment,
)

# The validated engine (Rust LCI kernel + supply-chain solver + canonical CFs) is the
# default served path. Set USE_LEGACY_RUST_LCIA=1 to fall back to the old Rust
# hardcoded-LCIA path (kept only for comparison/emergencies).
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
USE_VALIDATED_ENGINE = os.getenv("USE_LEGACY_RUST_LCIA", "0") != "1"

from .models import (
    AssessmentRequest,
    AssessmentResponse,
    FarmType,
    FarmingSystem,
    ProductionSystem,
    SoilType,
    CroppingPattern,
    SeasonalFactor,
    ScenarioPatchBody,
    RecharacterizeBody,
    ReviewStatusBody,
    VALID_COUNTRIES,
    VALID_FOOD_CATEGORIES
)

# Create router for production endpoints
router = APIRouter(tags=["production"])


def _resolve_farm_id(request: AssessmentRequest, user: User, db: Session) -> Optional[str]:
    """If the request attaches a farm, confirm it belongs to the current user."""
    if not request.farm_id:
        return None
    farm = db.get(Farm, request.farm_id)
    if farm is None or farm.created_by_user_id != user.id:
        raise HTTPException(status_code=404, detail="Farm not found")
    return farm.id


def _request_archive(request: AssessmentRequest) -> dict:
    """Persistable request for later edit/re-run (engine input + optional form snapshot)."""
    return {
        "api": request.model_dump(mode="json", exclude={"form_snapshot"}),
        "form": request.form_snapshot,
    }


def _build_farm_rust_input(request: AssessmentRequest) -> dict:
    rust_input = {
        "company_name": request.company_name,
        "country": request.country,
        "foods": [food.model_dump(exclude_none=False) for food in request.foods],
    }
    if request.region:
        rust_input["region"] = request.region
    if request.farm_profile:
        rust_input["farm_profile"] = request.farm_profile.model_dump()
    if request.management_practices:
        rust_input["management_practices"] = request.management_practices.model_dump()
    if request.equipment_energy:
        rust_input["equipment_energy"] = request.equipment_energy.model_dump()
        print("[OK] Added equipment_energy to rust_input")
    else:
        print("[SKIP] Skipped equipment_energy (falsy value)")
    return rust_input


async def _run_farm_engine(request: AssessmentRequest) -> dict:
    rust_input = _build_farm_rust_input(request)
    if request.study_meta:
        rust_input["study_meta"] = request.study_meta.model_dump(exclude_none=True)
    if request.ipcc_ef1_scale is not None:
        rust_input["ipcc_ef1_scale"] = request.ipcc_ef1_scale
    if USE_VALIDATED_ENGINE:
        # CPU-bound; run in a worker thread so uvicorn's event loop stays responsive.
        from starlette.concurrency import run_in_threadpool
        from engine.service import run_farm_assessment
        return await run_in_threadpool(
            run_farm_assessment,
            rust_input,
            region=request.region,
            method=request.lcia_method,
            run_uncertainty=bool(request.run_uncertainty),
        )
    return await call_rust_backend(rust_input)


@router.post("/assess", response_model=AssessmentResponse)
async def create_assessment(
    request: AssessmentRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new environmental sustainability assessment (supports both simple and comprehensive)
    """
    try:
        farm_id = _resolve_farm_id(request, user, db)
        result = await _run_farm_engine(request)
        save_assessment(
            db, user_id=user.id, a_type=AssessmentType.farm, payload=result,
            farm_id=farm_id, title=request.title,
            request_payload=_request_archive(request),
        )
        return AssessmentResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Assessment failed: {str(e)}")


@router.post("/assess/stream")
async def create_assessment_stream(
    request: AssessmentRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Same as POST /assess (simple or comprehensive), but streams live per-stage progress
    as Server-Sent Events and persists the result, ending with a terminal `result` (or
    `error`) event. Uses the validated engine path."""
    farm_id = _resolve_farm_id(request, user, db)
    # Capture plain values now: the worker thread / SSE generator must not touch the
    # request-scoped ORM session or lazy attributes.
    rust_input = _build_farm_rust_input(request)
    if request.study_meta:
        rust_input["study_meta"] = request.study_meta.model_dump(exclude_none=True)
    if request.ipcc_ef1_scale is not None:
        rust_input["ipcc_ef1_scale"] = request.ipcc_ef1_scale
    region = request.region
    method = request.lcia_method
    run_uncertainty = bool(request.run_uncertainty)
    user_id = user.id
    title = request.title
    archive = _request_archive(request)

    def run_fn(on_progress):
        from engine.service import run_farm_assessment
        return run_farm_assessment(
            rust_input,
            region=region,
            method=method,
            run_uncertainty=run_uncertainty,
            on_progress=on_progress,
        )

    def save_fn(result):
        from db import SessionLocal
        with SessionLocal() as session:
            save_assessment(
                session, user_id=user_id, a_type=AssessmentType.farm, payload=result,
                farm_id=farm_id, title=title, request_payload=archive,
            )

    return StreamingResponse(
        stream_assessment(run_fn, save_fn=save_fn),
        media_type=SSE_MEDIA_TYPE, headers=SSE_HEADERS,
    )


@router.post("/assess/comprehensive", response_model=AssessmentResponse)
async def create_comprehensive_assessment(
    request: AssessmentRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a comprehensive environmental sustainability assessment with farm management details
    """
    if not request.farm_profile or not request.management_practices:
        raise HTTPException(
            status_code=400,
            detail="Comprehensive assessment requires farm_profile and management_practices"
        )

    try:
        farm_id = _resolve_farm_id(request, user, db)
        result = await _run_farm_engine(request)
        save_assessment(
            db, user_id=user.id, a_type=AssessmentType.farm, payload=result,
            farm_id=farm_id, title=request.title,
            request_payload=_request_archive(request),
        )
        return AssessmentResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comprehensive assessment failed: {str(e)}")


@router.post("/assess/{assessment_id}/rerun", response_model=AssessmentResponse)
async def rerun_assessment(
    assessment_id: str,
    request: AssessmentRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Re-run a farm assessment in place. Replaces scores/report for the same id.
    Requires ownership; not found and not owned both return 404."""
    existing = get_owned_assessment(db, user, assessment_id, AssessmentType.farm)
    if existing is None:
        raise HTTPException(status_code=404, detail="Assessment not found")

    try:
        farm_id = _resolve_farm_id(request, user, db)
        result = await _run_farm_engine(request)
        updated = replace_assessment(
            db, existing, payload=result,
            farm_id=farm_id, title=request.title,
            request_payload=_request_archive(request),
            reason="rerun",
        )
        # Return the persisted payload (id kept as the existing row id). The engine
        # mints a fresh uuid each run; navigating to that would 404.
        return AssessmentResponse(**updated.payload_json)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Assessment re-run failed: {str(e)}")

@router.post("/assess/{assessment_id}/scenarios", tags=["research-scenarios"])
async def create_scenario(
    assessment_id: str,
    patch: ScenarioPatchBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Clone archived request, apply yield/N/diesel scales, re-solve, return deltas."""
    from scenarios import (
        ScenarioPatch,
        apply_scenario_patch,
        compute_scenario_deltas,
        default_scenario_title,
    )

    baseline = get_owned_assessment(db, user, assessment_id, AssessmentType.farm)
    if baseline is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    archive = baseline.request_json or {}
    api = archive.get("api")
    if not api:
        raise HTTPException(
            status_code=422,
            detail="Baseline has no archived request_json.api; cannot build a scenario",
        )

    try:
        sp = ScenarioPatch(**patch.model_dump())
        patched_api = apply_scenario_patch(api, sp)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    try:
        req = AssessmentRequest(**{k: v for k, v in patched_api.items() if k != "form_snapshot"})
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid patched request: {e}") from e

    title = default_scenario_title(sp)
    result = await _run_farm_engine(req)
    result["baseline_assessment_id"] = baseline.id
    result["scenario_patch"] = sp.active_scales()
    if req.study_meta:
        result["study_meta"] = req.study_meta.model_dump(exclude_none=True)

    saved = save_assessment(
        db,
        user_id=user.id,
        a_type=AssessmentType.farm,
        payload=result,
        farm_id=baseline.farm_id,
        title=title,
        request_payload={"api": req.model_dump(mode="json", exclude={"form_snapshot"}), "form": archive.get("form")},
    )
    deltas = compute_scenario_deltas(baseline.payload_json or {}, saved.payload_json or {})
    return {
        "baseline_id": baseline.id,
        "scenario_id": saved.id,
        "title": title,
        "patch": sp.active_scales(),
        "delta_midpoints": deltas["delta_midpoints"],
        "delta_single_score": deltas["delta_single_score"],
        "scenario": saved.payload_json,
    }


@router.post("/assess/{assessment_id}/recharacterize", response_model=AssessmentResponse, tags=["research-scenarios"])
async def recharacterize_assessment(
    assessment_id: str,
    body: RecharacterizeBody,
    expected_version: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Re-run characterization with an alternate LCIA method; cache on method_variants.
    Pass ``expected_version`` (the version the client last saw) for optimistic locking:
    a 409 is returned if the assessment was modified in the meantime."""
    from .models import SUPPORTED_LCIA_METHODS

    existing = get_owned_assessment(db, user, assessment_id, AssessmentType.farm)
    if existing is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    method = body.lcia_method
    if method not in SUPPORTED_LCIA_METHODS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported lcia_method: {method}. Must be one of {list(SUPPORTED_LCIA_METHODS)}",
        )

    archive = existing.request_json or {}
    api = archive.get("api")
    if not api:
        raise HTTPException(status_code=422, detail="No archived request to recharacterize")

    try:
        req = AssessmentRequest(**{**api, "lcia_method": method, "form_snapshot": None})
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid archived request: {e}") from e

    from starlette.concurrency import run_in_threadpool
    from engine.service import recharacterize_from_payload, run_farm_assessment

    rust_input = _build_farm_rust_input(req)
    prior_payload = dict(existing.payload_json or {})
    variant = await run_in_threadpool(
        recharacterize_from_payload, prior_payload, rust_input, method, req.region,
    )
    if variant is None:
        variant = await run_in_threadpool(
            run_farm_assessment,
            rust_input,
            region=req.region,
            method=method,
            assessment_id=existing.id,
        )
    else:
        variant["id"] = existing.id

    payload = dict(prior_payload)
    variants = dict(payload.get("method_variants") or {})
    old_method = payload.get("lcia_method") or (archive.get("api") or {}).get("lcia_method")
    if body.apply_as_primary and old_method and old_method != method:
        ss = payload.get("single_score")
        variants[old_method] = {
            "midpoint_impacts": payload.get("midpoint_impacts"),
            "single_score": ss,
            "methodology": ss.get("methodology") if isinstance(ss, dict) else None,
        }
    variants[method] = {
        "midpoint_impacts": variant.get("midpoint_impacts"),
        "single_score": variant.get("single_score"),
        "methodology": (
            (variant.get("single_score") or {}).get("methodology")
            if isinstance(variant.get("single_score"), dict)
            else None
        ),
    }
    payload["method_variants"] = variants
    if variant.get("engine_inventory") and not payload.get("engine_inventory"):
        payload["engine_inventory"] = variant["engine_inventory"]
    # If requested as active method, replace the whole primary result with the variant so
    # every method-dependent section (Top sources, per-source contribution, pedigree MC)
    # reflects the promoted method rather than going stale against the old one.
    if body.apply_as_primary:
        payload["midpoint_impacts"] = variant.get("midpoint_impacts")
        payload["endpoint_impacts"] = variant.get("endpoint_impacts")
        payload["single_score"] = variant.get("single_score")
        payload["functional_units"] = variant.get("functional_units")
        payload["lcia_method"] = method
        for key in (
            "contribution_by_source",
            "contribution_sankey",
            "sensitivity_analysis",
            "uncertainty",
            "engine_inventory_by_source",
            "data_quality",
        ):
            if variant.get(key) is not None:
                payload[key] = variant[key]
        if variant.get("iso_report"):
            payload["iso_report"] = variant["iso_report"]

    try:
        updated = replace_assessment(
            db, existing, payload=payload, title=existing.title,
            request_payload=existing.request_json, reason="recharacterize",
            expected_version=expected_version,
        )
    except ConcurrencyError as e:
        raise HTTPException(
            status_code=409,
            detail=f"Assessment changed (version {e.actual}); re-fetch and retry.",
        ) from e
    return AssessmentResponse(**updated.payload_json)


@router.post("/assess/{assessment_id}/uncertainty", response_model=AssessmentResponse, tags=["research-scenarios"])
async def run_assessment_uncertainty(
    assessment_id: str,
    expected_version: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Re-run with pedigree screening Monte Carlo and persist uncertainty percentiles.
    Pass ``expected_version`` for optimistic locking (409 on a stale write)."""
    existing = get_owned_assessment(db, user, assessment_id, AssessmentType.farm)
    if existing is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    archive = existing.request_json or {}
    api = archive.get("api")
    if not api:
        raise HTTPException(status_code=422, detail="No archived request for uncertainty run")

    try:
        req = AssessmentRequest(**{**api, "run_uncertainty": True, "form_snapshot": None})
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid archived request: {e}") from e

    result = await _run_farm_engine(req)
    # Keep baseline link / variants from prior payload when present.
    prior = existing.payload_json or {}
    if prior.get("method_variants"):
        result["method_variants"] = prior["method_variants"]
    if prior.get("baseline_assessment_id"):
        result["baseline_assessment_id"] = prior["baseline_assessment_id"]
    try:
        updated = replace_assessment(
            db, existing, payload=result, title=existing.title,
            request_payload=_request_archive(req), reason="uncertainty",
            expected_version=expected_version,
        )
    except ConcurrencyError as e:
        raise HTTPException(
            status_code=409,
            detail=f"Assessment changed (version {e.actual}); re-fetch and retry.",
        ) from e
    return AssessmentResponse(**updated.payload_json)


@router.get("/assess/{assessment_id}", response_model=AssessmentResponse)
async def get_assessment(
    assessment_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve one of the current user's farm assessments by ID
    """
    assessment = get_owned_assessment(db, user, assessment_id, AssessmentType.farm)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    payload = dict(assessment.payload_json or {})
    _attach_regional_benchmark(payload, assessment.request_json)
    return AssessmentResponse(**payload)


def _attach_regional_benchmark(payload: dict, request_json: dict | None) -> None:
    """Overlay regional_benchmark on GH farm payloads when not already stored."""
    if payload.get("regional_benchmark"):
        return
    api = (request_json or {}).get("api") or {}
    region = (api.get("region") or payload.get("region") or "").upper()
    country = (api.get("country") or payload.get("country") or "").lower()
    if region != "GH" and country not in ("ghana", "gh"):
        return
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from engine.regional_benchmark import compute_regional_benchmark
    bench = compute_regional_benchmark(api, payload.get("midpoint_impacts"))
    if bench is not None:
        payload["regional_benchmark"] = bench


@router.get("/assess/{assessment_id}/benchmark")
async def get_assessment_benchmark(
    assessment_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Regional MoFA/yield guide overlay for a saved GH farm assessment."""
    assessment = get_owned_assessment(db, user, assessment_id, AssessmentType.farm)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    api = (assessment.request_json or {}).get("api") or {}
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from engine.regional_benchmark import compute_regional_benchmark
    bench = compute_regional_benchmark(api, (assessment.payload_json or {}).get("midpoint_impacts"))
    if bench is None:
        raise HTTPException(status_code=404, detail="Regional benchmark available for Ghana (GH) only")
    return bench


@router.post("/assess/{assessment_id}/review", response_model=AssessmentResponse)
async def set_assessment_review_status(
    assessment_id: str,
    body: ReviewStatusBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set critical-review checklist status and sync ISO document_control fields."""
    from review import VALID_REVIEW_STATUSES, apply_review_status

    if body.review_status not in VALID_REVIEW_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid review_status: {body.review_status}")

    existing = get_owned_assessment(db, user, assessment_id, AssessmentType.farm)
    if existing is None:
        raise HTTPException(status_code=404, detail="Assessment not found")

    payload = apply_review_status(existing.payload_json or {}, body.review_status)
    updated = replace_assessment(
        db, existing, payload=payload, title=existing.title,
        request_payload=existing.request_json, reason="review",
    )
    return AssessmentResponse(**updated.payload_json)


@router.get("/assess/{assessment_id}/recommendations")
async def get_assessment_recommendations(
    assessment_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Practical, costed, sequenced actions for one saved farm assessment.

    Fully deterministic: the engine's hotspot attribution is matched against the curated
    measure library and screened for affordability/payback. No LLM produces any number
    here — the results chat explains this output, it does not generate it.
    """
    assessment = get_owned_assessment(db, user, assessment_id, AssessmentType.farm)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    from recommendations.service import build_recommendations
    from starlette.concurrency import run_in_threadpool
    return await run_in_threadpool(
        build_recommendations, assessment.payload_json, assessment.request_json,
        is_processing=False,
    )

@router.get("/assessments")
async def list_assessments(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List the current user's saved farm assessments
    """
    rows = list_owned_assessments(db, user, AssessmentType.farm)
    return {
        "assessments": [
            {
                "id": row.id,
                "title": row.title,
                "company_name": row.company_name,
                "country": row.country,
                "farm_id": row.farm_id,
                "single_score": row.single_score,
                "assessment_date": row.payload_json.get("assessment_date"),
                "created_at": row.created_at,
                "is_comprehensive": "farm_profile" in row.payload_json
                or "management_analysis" in row.payload_json,
            }
            for row in rows
        ],
        "total": len(rows),
    }

@router.get("/food-categories")
async def get_food_categories():
    """
    Get available food categories
    """
    return {
        "categories": VALID_FOOD_CATEGORIES
    }

@router.get("/countries")
async def get_supported_countries():
    """
    Get supported countries for assessment
    """
    return {
        "countries": VALID_COUNTRIES,
        "default": "Global"
    }

@router.get("/impact-categories")
async def get_impact_categories():
    """
    Get available impact categories
    """
    return {
        "midpoint": [
            "Global warming",
            "Water consumption",
            "Land use", 
            "Terrestrial acidification",
            "Freshwater eutrophication",
            "Marine eutrophication",
            "Biodiversity loss",
            "Soil degradation"
        ],
        "endpoint": [
            "Human Health",
            "Ecosystem Quality", 
            "Resource Scarcity"
        ]
    }

@router.get("/farm-types")
async def get_farm_types():
    """
    Get available farm types for comprehensive assessments
    """
    return {
        "farm_types": [e.value for e in FarmType],
        "farming_systems": [e.value for e in FarmingSystem],
        "production_systems": [e.value for e in ProductionSystem]
    }

@router.get("/management-options")
async def get_management_options():
    """
    Get available management practice options for comprehensive assessments
    """
    return {
        "soil_types": [e.value for e in SoilType],
        "cropping_patterns": [e.value for e in CroppingPattern],
        "seasonal_factors": [e.value for e in SeasonalFactor]
    }

async def call_rust_backend(data: dict) -> dict:
    """
    Call the Rust backend for LCA calculations - Enhanced version supporting both simple and comprehensive assessments
    """
    try:
        # DEBUG: Log what we're sending to Rust
        print("\n" + "="*80)
        print("DATA BEING SENT TO RUST BACKEND:")
        print("="*80)
        if "equipment_energy" in data:
            print(f"[OK] equipment_energy present: {data['equipment_energy']}")
        else:
            print("[WARN] equipment_energy MISSING!")
        print("="*80 + "\n")

        # Write input to temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(data, f, indent=2)
            temp_file = f.name
            print(f"Temp file written: {temp_file}")
        
        # Call Rust binary - Check environment variable first, then fallback to local paths
        rust_binary = os.environ.get('RUST_BACKEND_PATH')

        if not rust_binary or not os.path.exists(rust_binary):
            # Fallback to local development paths
            rust_binary_release = "../african_lca_backend/target/release/server.exe"
            rust_binary_debug = "../african_lca_backend/target/debug/server.exe"
            rust_binary_release_linux = "../african_lca_backend/target/release/server"
            rust_binary_debug_linux = "../african_lca_backend/target/debug/server"

            # Determine which binary to use
            if os.path.exists(rust_binary_release):
                rust_binary = rust_binary_release
            elif os.path.exists(rust_binary_debug):
                rust_binary = rust_binary_debug
            elif os.path.exists(rust_binary_release_linux):
                rust_binary = rust_binary_release_linux
            elif os.path.exists(rust_binary_debug_linux):
                rust_binary = rust_binary_debug_linux
            else:
                # Clean up temp file before raising exception
                os.unlink(temp_file)
                raise Exception(f"Rust backend not found! Checked:\n  - RUST_BACKEND_PATH env var: {os.environ.get('RUST_BACKEND_PATH')}\n  - {rust_binary_release}\n  - {rust_binary_debug}\n  - {rust_binary_release_linux}\n  - {rust_binary_debug_linux}\nPlease compile with: cargo build --release")
        
        # Execute Rust backend
        result = subprocess.run(
            [rust_binary, temp_file],
            capture_output=True,
            text=True,
            timeout=120,  # Increased timeout for comprehensive assessments
            cwd="../african_lca_backend",  # Set working directory
            encoding='utf-8',
            errors='replace'  # Replace unicode errors instead of crashing
        )

        # Print Rust stderr for debugging
        if result.stderr:
            print("RUST STDERR OUTPUT:")
            print(result.stderr)
            print("="*80)
        
        # Clean up temp file
        os.unlink(temp_file)
        
        if result.returncode != 0:
            raise Exception(f"Rust backend execution failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}")
        
        # Parse and transform Rust backend results to match API format
        try:
            # Clean the output by extracting only the JSON part
            stdout_cleaned = result.stdout.strip()
            
            # Find the first '{' character which should be the start of JSON
            json_start = stdout_cleaned.find('{')
            if json_start == -1:
                raise Exception(f"No JSON found in Rust backend output: {stdout_cleaned}")
            
            # Extract only the JSON part and clean up any remaining non-JSON content
            json_output = stdout_cleaned[json_start:]
            
            # Find the last '}' to ensure we get the complete JSON
            json_end = json_output.rfind('}')
            if json_end != -1:
                json_output = json_output[:json_end + 1]
            
            # Try to parse the JSON
            rust_result = json.loads(json_output)
            return transform_rust_result_to_api_format(rust_result)
            
        except json.JSONDecodeError as e:
            # If JSON parsing fails, try to extract JSON more carefully
            try:
                # Split by lines and look for JSON content
                lines = result.stdout.split('\n')
                json_lines = []
                in_json = False
                brace_count = 0
                
                for line in lines:
                    if not in_json and '{' in line:
                        in_json = True
                        # Start from the first brace
                        start_idx = line.find('{')
                        json_lines.append(line[start_idx:])
                        brace_count += line[start_idx:].count('{') - line[start_idx:].count('}')
                    elif in_json:
                        json_lines.append(line)
                        brace_count += line.count('{') - line.count('}')
                        if brace_count == 0:
                            break
                
                if json_lines:
                    json_output = '\n'.join(json_lines)
                    rust_result = json.loads(json_output)
                    return transform_rust_result_to_api_format(rust_result)
                else:
                    raise Exception(f"Could not extract valid JSON from output")
                    
            except json.JSONDecodeError as e2:
                raise Exception(f"Invalid JSON response from Rust backend: {e}\nSecond attempt error: {e2}\nOutput: {result.stdout}")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rust backend error: {str(e)}")

def transform_rust_result_to_api_format(rust_result: dict) -> dict:
    """
    Transform Rust backend result format to match Python API format
    Handles both simple and comprehensive assessment results
    """
    try:
        results = rust_result.get("results", {})
        
        # Check if this is a comprehensive assessment
        is_comprehensive = "management_analysis" in results or "benchmarking" in results or rust_result.get("farm_profile") is not None
        
        # Extract midpoint impacts (preserve complex structure for comprehensive assessments)
        midpoint_impacts = {}
        rust_midpoint = results.get("midpoint_impacts", {})
        for category, data in rust_midpoint.items():
            if isinstance(data, dict) and "value" in data and is_comprehensive:
                # Keep full structure for comprehensive assessments
                midpoint_impacts[category] = {
                    "value": data["value"],
                    "unit": data.get("unit", "kg CO2-eq"),
                    "uncertainty_range": data.get("uncertainty_range", [0.0, 0.0]),
                    "data_quality_score": data.get("data_quality_score", 0.75),
                    "contributing_sources": data.get("contributing_sources", [])
                }
            elif isinstance(data, dict) and "value" in data:
                midpoint_impacts[category] = data["value"]
            else:
                midpoint_impacts[category] = data
        
        # Extract endpoint impacts 
        endpoint_impacts = {}
        rust_endpoint = results.get("endpoint_impacts", {})
        for category, data in rust_endpoint.items():
            if isinstance(data, dict) and "value" in data and is_comprehensive:
                endpoint_impacts[category] = {
                    "value": data["value"],
                    "unit": data.get("unit", "pt"),
                    "uncertainty_range": data.get("uncertainty_range", [0.0, 0.0]),
                    "normalization_factor": data.get("normalization_factor"),
                    "regional_adaptation_factor": data.get("regional_adaptation_factor")
                }
            elif isinstance(data, dict) and "value" in data:
                endpoint_impacts[category] = data["value"]
            else:
                endpoint_impacts[category] = data
        
        # Extract single score
        single_score_data = results.get("single_score", {})
        if isinstance(single_score_data, dict) and is_comprehensive:
            single_score = {
                "value": single_score_data.get("value", 0.0),
                "unit": single_score_data.get("unit", "pt"),
                "uncertainty_range": single_score_data.get("uncertainty_range", [0.0, 0.0]),
                "weighting_factors": single_score_data.get("weighting_factors", {}),
                "methodology": single_score_data.get("methodology", "RegionalPriorities")
            }
        elif isinstance(single_score_data, dict):
            single_score = single_score_data.get("value", 0.0)
        else:
            single_score = single_score_data or 0.0
        
        # Extract data quality (enhanced for comprehensive assessments)
        rust_data_quality = results.get("data_quality", {})
        if is_comprehensive:
            data_quality = {
                "overall_confidence": rust_data_quality.get("overall_confidence", "Medium"),
                "data_source_mix": rust_data_quality.get("data_source_mix", []),
                "regional_adaptation": rust_data_quality.get("regional_adaptation", True),
                "completeness_score": rust_data_quality.get("completeness_score", 0.75),
                "temporal_representativeness": rust_data_quality.get("temporal_representativeness", 0.75),
                "geographical_representativeness": rust_data_quality.get("geographical_representativeness", 0.75),
                "technological_representativeness": rust_data_quality.get("technological_representativeness", 0.75),
                "warnings": rust_data_quality.get("warnings", []),
                "recommendations": rust_data_quality.get("recommendations", [])
            }
        else:
            data_quality = {
                "confidence_level": rust_data_quality.get("overall_confidence", "Medium"),
                "data_source": "CountrySpecific(" + rust_result.get("country", "Global") + ")",
                "regional_adaptation": rust_data_quality.get("regional_adaptation", True),
                "completeness_score": rust_data_quality.get("completeness_score", 0.75),
                "warnings": rust_data_quality.get("warnings", [])
            }
        
        # Extract breakdown by food (preserve structure for comprehensive assessments)
        breakdown_by_food = {}
        rust_breakdown = results.get("breakdown_by_food", {})
        for food_name, food_impacts in rust_breakdown.items():
            breakdown_by_food[food_name] = {}
            for category, data in food_impacts.items():
                if isinstance(data, dict) and "value" in data and is_comprehensive:
                    breakdown_by_food[food_name][category] = {
                        "value": data["value"],
                        "unit": data.get("unit", "kg CO2-eq"),
                        "uncertainty_range": data.get("uncertainty_range", [0.0, 0.0]),
                        "data_quality_score": data.get("data_quality_score", 0.75),
                        "contributing_sources": data.get("contributing_sources", [])
                    }
                elif isinstance(data, dict) and "value" in data:
                    breakdown_by_food[food_name][category] = data["value"]
                else:
                    breakdown_by_food[food_name][category] = data
        
        # Base result structure
        result_data = {
            "id": rust_result.get("id"),
            "company_name": rust_result.get("company_name"),
            "country": rust_result.get("country"),
            "assessment_date": rust_result.get("assessment_date"),
            "midpoint_impacts": midpoint_impacts,
            "endpoint_impacts": endpoint_impacts,
            "single_score": single_score,
            "data_quality": data_quality,
            "breakdown_by_food": breakdown_by_food
        }
        
        # Add enhanced analysis results for comprehensive assessments
        if is_comprehensive:
            if "sensitivity_analysis" in results:
                result_data["sensitivity_analysis"] = results["sensitivity_analysis"]
            if "comparative_analysis" in results:
                result_data["comparative_analysis"] = results["comparative_analysis"]
            if "management_analysis" in results:
                result_data["management_analysis"] = results["management_analysis"]
            if "benchmarking" in results:
                result_data["benchmarking"] = results["benchmarking"]
            if "recommendations" in results:
                result_data["recommendations"] = results["recommendations"]
        
        return result_data
    
    except Exception as e:
        raise Exception(f"Result transformation failed: {str(e)}")
