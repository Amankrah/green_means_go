from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional
from functools import partial

from sqlalchemy.orm import Session

from db import get_db
from assessment_stream import stream_assessment, SSE_MEDIA_TYPE, SSE_HEADERS
from models import AssessmentType, Facility, User
from auth.deps import require_role
from models import UserRole
from store import (
    get_owned_assessment,
    list_owned_assessments,
    replace_assessment,
    save_assessment,
)

from .models import (
    ProcessingAssessmentRequest, 
    ProcessingAssessmentResponse,
    ProcessingFacilityType,
    ProductType,
    EnergySource,
    LocationType,
    EquipmentAge,
    MaintenanceFrequency,
    AutomationLevel,
    WasteDisposalMethod,
    PackagingMaterial,
    QualityGrade,
    MarketDestination
)

# Create router for processing endpoints
router = APIRouter(prefix="/processing", tags=["processing"])

# Processing assessments are for processor accounts, and for researchers, who study both
# sides of the food system and so run farm and processing assessments alike.
_require_processor = require_role(UserRole.processor, UserRole.researcher)


def _resolve_facility_id(request: ProcessingAssessmentRequest, user: User, db: Session) -> Optional[str]:
    """If the request attaches a facility, confirm it belongs to the current user."""
    if not request.facility_id:
        return None
    facility = db.get(Facility, request.facility_id)
    if facility is None or facility.created_by_user_id != user.id:
        raise HTTPException(status_code=404, detail="Facility not found")
    return facility.id


def _request_archive(request: ProcessingAssessmentRequest) -> dict:
    return {
        "api": request.model_dump(mode="json", exclude={"form_snapshot"}),
        "form": request.form_snapshot,
    }


def _check_region(request: ProcessingAssessmentRequest) -> str:
    """Resolve the engine region up front so an unknown region is a 422, not a 500 or an
    SSE error half-way through a run."""
    from engine.process_service import _resolve_region
    try:
        return _resolve_region(request.model_dump(mode="json", include={"region", "country"}),
                               request.region)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


async def _run_processing_engine(request: ProcessingAssessmentRequest) -> dict:
    # The validated process engine is the only served path; the Rust processing kernel's
    # hardcoded LCIA (processing/lca.rs) is never served.
    from starlette.concurrency import run_in_threadpool
    from engine.process_service import run_process_assessment
    request_dict = request.model_dump(mode="json", exclude={"form_snapshot"})
    return await run_in_threadpool(
        partial(run_process_assessment, run_uncertainty=bool(request.run_uncertainty)),
        request_dict, request.region)


@router.post("/assess", response_model=ProcessingAssessmentResponse)
async def create_processing_assessment(
    request: ProcessingAssessmentRequest,
    user: User = Depends(_require_processor),
    db: Session = Depends(get_db),
):
    """
    Create a new environmental sustainability assessment for food processing facilities
    """
    try:
        facility_id = _resolve_facility_id(request, user, db)
        _check_region(request)
        result = await _run_processing_engine(request)
        save_assessment(
            db, user_id=user.id, a_type=AssessmentType.processing, payload=result,
            facility_id=facility_id, title=request.title,
            request_payload=_request_archive(request),
        )
        return ProcessingAssessmentResponse(**result)

    except HTTPException:
        raise
    except ValueError as e:
        # Engine-level input rejections (unknown region, unknown refrigerant, ...) are the
        # caller's data, not a server fault.
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing assessment failed: {str(e)}")


@router.post("/assess/stream")
async def create_processing_assessment_stream(
    request: ProcessingAssessmentRequest,
    user: User = Depends(_require_processor),
    db: Session = Depends(get_db),
):
    """Same as POST /assess, but streams live per-stage progress as Server-Sent Events and
    persists the result, ending with a terminal `result` (or `error`) event."""
    facility_id = _resolve_facility_id(request, user, db)
    _check_region(request)
    # Capture plain values now: the worker thread / SSE generator must not touch the
    # request-scoped ORM session or lazy attributes.
    request_dict = request.model_dump(mode="json", exclude={"form_snapshot"})
    region = request.region
    run_uncertainty = bool(request.run_uncertainty)
    user_id = user.id
    title = request.title
    archive = _request_archive(request)

    def run_fn(on_progress):
        from engine.process_service import run_process_assessment
        return run_process_assessment(request_dict, region, on_progress=on_progress,
                                      run_uncertainty=run_uncertainty)

    def save_fn(result):
        from db import SessionLocal
        with SessionLocal() as session:
            save_assessment(
                session, user_id=user_id, a_type=AssessmentType.processing, payload=result,
                facility_id=facility_id, title=title, request_payload=archive,
            )

    return StreamingResponse(
        stream_assessment(run_fn, save_fn=save_fn),
        media_type=SSE_MEDIA_TYPE, headers=SSE_HEADERS,
    )


@router.post("/assess/{assessment_id}/rerun", response_model=ProcessingAssessmentResponse)
async def rerun_processing_assessment(
    assessment_id: str,
    request: ProcessingAssessmentRequest,
    user: User = Depends(_require_processor),
    db: Session = Depends(get_db),
):
    """Re-run a processing assessment in place. Same id; scores/report replaced."""
    existing = get_owned_assessment(db, user, assessment_id, AssessmentType.processing)
    if existing is None:
        raise HTTPException(status_code=404, detail="Processing assessment not found")

    try:
        facility_id = _resolve_facility_id(request, user, db)
        _check_region(request)
        result = await _run_processing_engine(request)
        updated = replace_assessment(
            db, existing, payload=result,
            facility_id=facility_id, title=request.title,
            request_payload=_request_archive(request),
            reason="rerun",
        )
        # Persist keeps the existing row id; return that payload so the client
        # does not navigate to the engine's freshly minted uuid (404).
        return ProcessingAssessmentResponse(**updated.payload_json)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing assessment re-run failed: {str(e)}")

@router.get("/assess/{assessment_id}", response_model=ProcessingAssessmentResponse)
async def get_processing_assessment(
    assessment_id: str,
    user: User = Depends(_require_processor),
    db: Session = Depends(get_db),
):
    """
    Retrieve one of the current user's processing assessments by ID
    """
    assessment = get_owned_assessment(db, user, assessment_id, AssessmentType.processing)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Processing assessment not found")
    return ProcessingAssessmentResponse(**assessment.payload_json)


@router.get("/assess/{assessment_id}/recommendations")
async def get_processing_recommendations(
    assessment_id: str,
    user: User = Depends(_require_processor),
    db: Session = Depends(get_db),
):
    """Practical, costed, sequenced actions for one saved processing assessment.
    Deterministic (see the farm equivalent); the LLM never produces a number here."""
    assessment = get_owned_assessment(db, user, assessment_id, AssessmentType.processing)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Processing assessment not found")
    from recommendations.service import build_recommendations
    from starlette.concurrency import run_in_threadpool
    return await run_in_threadpool(
        build_recommendations, assessment.payload_json, assessment.request_json,
        is_processing=True,
    )

@router.get("/assessments")
async def list_processing_assessments(
    user: User = Depends(_require_processor),
    db: Session = Depends(get_db),
):
    """
    List the current user's saved processing assessments
    """
    rows = list_owned_assessments(db, user, AssessmentType.processing)
    return {
        "assessments": [
            {
                "id": row.id,
                "title": row.title,
                "facility_name": row.payload_json.get("facility_profile", {}).get("facility_name", "Unknown"),
                "company_name": row.payload_json.get("facility_profile", {}).get("company_name", "Unknown"),
                "facility_type": row.payload_json.get("facility_profile", {}).get("facility_type", "General"),
                "country": row.country,
                "facility_id": row.facility_id,
                "single_score": row.single_score,
                "assessment_date": row.payload_json.get("assessment_date"),
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "processing_capacity": row.payload_json.get("facility_profile", {}).get("processing_capacity", 0.0),
            }
            for row in rows
        ],
        "total": len(rows),
    }

@router.get("/facility-types")
async def get_processing_facility_types():
    """
    Get available processing facility types
    """
    return {
        "facility_types": [e.value for e in ProcessingFacilityType],
        "descriptions": {
            "Mill": "Grain and cereal processing mills",
            "Bakery": "Bread and bakery products",
            "CassivaProcessing": "Cassava flour and processing",
            "RiceProcessing": "Rice milling and processing",
            "PalmOilMill": "Palm oil extraction and processing",
            "CocoaProcessing": "Cocoa powder and butter processing",
            "FishProcessing": "Fish processing and preservation",
            "MeatProcessing": "Meat processing and packaging",
            "DairyProcessing": "Dairy products processing",
            "FruitProcessing": "Fruit juice and dried fruits",
            "VegetableProcessing": "Vegetable processing and canning",
            "General": "General food processing facility"
        }
    }

@router.get("/product-types")
async def get_product_types():
    """
    Get available processed product types
    """
    return {
        "product_types": [e.value for e in ProductType],
        "categories": {
            "Flour": ["FlourMaize", "FlourWheat", "FlourCassava", "FlourPlantain"],
            "Processed Grains": ["RiceProcessed"],
            "Oils": ["PalmOil"],
            "Cocoa": ["CocoaPowder", "CocoaButter"],
            "Baked Goods": ["BakedGoods"],
            "Animal Products": ["ProcessedFish", "ProcessedMeat", "Dairy"],
            "Fruits": ["FruitJuice", "DriedFruits"],
            "Other": ["Other"]
        }
    }

@router.get("/energy-sources")
async def get_energy_sources():
    """
    Get available energy sources for processing facilities
    """
    return {
        "energy_sources": [e.value for e in EnergySource],
        "renewable": ["SolarPower", "HydroElectricity", "WindPower", "Biomass"],
        "fossil": ["GridElectricity", "DieselGenerator", "LPG", "NaturalGas"],
        "recommendations": {
            "Ghana": ["SolarPower", "GridElectricity", "Biomass"],
            "Nigeria": ["SolarPower", "GridElectricity", "NaturalGas"]
        }
    }

@router.get("/location-types")
async def get_location_types():
    """
    Get available location types and their characteristics
    """
    return {
        "location_types": [e.value for e in LocationType],
        "characteristics": {
            "Industrial": "Better infrastructure, utility access, higher efficiency",
            "Urban": "Standard infrastructure, good utility access",
            "PeriUrban": "Moderate infrastructure, acceptable utility access",
            "Rural": "Limited infrastructure, potential utility challenges"
        }
    }

@router.get("/equipment-options")
async def get_equipment_options():
    """
    Get equipment age, maintenance, and automation options
    """
    return {
        "equipment_age": [e.value for e in EquipmentAge],
        "maintenance_frequency": [e.value for e in MaintenanceFrequency],
        "automation_level": [e.value for e in AutomationLevel],
        "age_descriptions": {
            "New": "Less than 2 years old - highest efficiency",
            "Recent": "2-5 years old - high efficiency", 
            "Mature": "5-10 years old - standard efficiency",
            "Old": "10-20 years old - reduced efficiency",
            "VeryOld": "Over 20 years old - lowest efficiency"
        }
    }

@router.get("/waste-management-options")
async def get_waste_management_options():
    """
    Get waste management and disposal options
    """
    return {
        "disposal_methods": [e.value for e in WasteDisposalMethod],
        "environmental_impact": {
            "AnaerobicDigestion": "Best - produces biogas, reduces emissions",
            "Composting": "Good - creates useful compost, low emissions",
            "Recycling": "Good - reuses materials",
            "Incineration": "Moderate - energy recovery possible",
            "Landfill": "Poor - generates methane, no resource recovery"
        }
    }

@router.get("/packaging-materials")
async def get_packaging_materials():
    """
    Get packaging material options and sustainability ratings
    """
    return {
        "materials": [e.value for e in PackagingMaterial],
        "sustainability_rating": {
            "Jute": "Excellent - biodegradable, renewable",
            "PaperBag": "Good - recyclable, biodegradable",
            "Cardboard": "Good - recyclable",
            "PlasticBag": "Poor - non-biodegradable",
            "Polypropylene": "Poor - non-biodegradable",
            "Composite": "Variable - depends on composition"
        }
    }

@router.get("/market-destinations")
async def get_market_destinations():
    """
    Get market destination options and their implications
    """
    return {
        "destinations": [e.value for e in MarketDestination],
        "transport_implications": {
            "Local": "Low transport emissions, supports local economy",
            "Regional": "Moderate transport, regional development",
            "National": "Higher transport emissions, broader market",
            "Export": "Highest transport emissions, foreign currency",
            "Mixed": "Balanced approach, diversified risk"
        }
    }

@router.get("/impact-categories")
async def get_processing_impact_categories():
    """
    Get available impact categories specific to processing facilities
    """
    return {
        "midpoint": [
            "Global warming",
            "Energy consumption", 
            "Water consumption",
            "Water scarcity",
            "Wastewater generation",
            "Solid waste generation",
            "Air pollution",
            "Land use",
            "Terrestrial acidification",
            "Freshwater eutrophication",
            "Marine eutrophication",
            "Fossil depletion",
            "Particulate matter formation",
            "Raw material depletion"
        ],
        "endpoint": [
            "Human Health",
            "Resource Scarcity"
        ],
        "processing_specific": [
            "Energy consumption",
            "Wastewater generation", 
            "Solid waste generation",
            "Air pollution",
            "Raw material depletion"
        ]
    }

@router.get("/benchmarks/{facility_type}")
async def get_processing_benchmarks(facility_type: ProcessingFacilityType):
    """
    Get processing benchmarks for specific facility types
    """
    # Sample benchmarks - in production, load from database
    benchmarks = {
        "Mill": {
            "energy_consumption": {"best": 45.0, "average": 75.0, "poor": 120.0, "unit": "kWh/tonne"},
            "water_consumption": {"best": 1.0, "average": 2.0, "poor": 4.0, "unit": "m3/tonne"},
            "waste_generation": {"best": 20.0, "average": 50.0, "poor": 100.0, "unit": "kg/tonne"}
        },
        "RiceProcessing": {
            "energy_consumption": {"best": 85.0, "average": 110.0, "poor": 150.0, "unit": "kWh/tonne"},
            "water_consumption": {"best": 2.5, "average": 3.5, "poor": 5.0, "unit": "m3/tonne"},
            "waste_generation": {"best": 30.0, "average": 60.0, "poor": 120.0, "unit": "kg/tonne"}
        },
        "PalmOilMill": {
            "energy_consumption": {"best": 150.0, "average": 200.0, "poor": 280.0, "unit": "kWh/tonne"},
            "water_consumption": {"best": 5.0, "average": 8.0, "poor": 12.0, "unit": "m3/tonne"},
            "waste_generation": {"best": 100.0, "average": 200.0, "poor": 350.0, "unit": "kg/tonne"}
        }
    }
    
    facility_type_str = facility_type.value
    if facility_type_str not in benchmarks:
        return {"message": f"No benchmarks available for {facility_type_str} yet"}
    
    return {
        "facility_type": facility_type_str,
        "benchmarks": benchmarks[facility_type_str],
        "note": "Benchmarks based on industry data from Ghana and Nigeria"
    }
