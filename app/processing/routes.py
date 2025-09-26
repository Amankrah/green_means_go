from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from datetime import datetime
import json
import os
import tempfile
import subprocess

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

# In-memory storage for processing assessments (use database in production)
processing_assessments_db: Dict[str, Dict[str, Any]] = {}

@router.post("/assess", response_model=ProcessingAssessmentResponse)
async def create_processing_assessment(request: ProcessingAssessmentRequest):
    """
    Create a new environmental sustainability assessment for food processing facilities
    """
    try:
        # Prepare data for Rust backend
        rust_input = {
            "country": request.country,
            "facility_profile": request.facility_profile.model_dump(),
            "processing_operations": request.processing_operations.model_dump(),
            "processed_products": [product.model_dump() for product in request.processed_products]
        }
        
        # Add region if provided
        if request.region:
            rust_input["region"] = request.region
        
        # Call Rust backend for processing assessment
        result = await call_rust_processing_backend(rust_input)
        
        # Store in database
        assessment_id = result["id"]
        processing_assessments_db[assessment_id] = result
        
        return ProcessingAssessmentResponse(**result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing assessment failed: {str(e)}")

@router.get("/assess/{assessment_id}", response_model=ProcessingAssessmentResponse)
async def get_processing_assessment(assessment_id: str):
    """
    Retrieve an existing processing assessment by ID
    """
    if assessment_id not in processing_assessments_db:
        raise HTTPException(status_code=404, detail="Processing assessment not found")
    
    return ProcessingAssessmentResponse(**processing_assessments_db[assessment_id])

@router.get("/assessments")
async def list_processing_assessments():
    """
    List all processing assessments
    """
    return {
        "assessments": [
            {
                "id": assessment_id,
                "facility_name": data.get("facility_profile", {}).get("facility_name", "Unknown"),
                "company_name": data.get("facility_profile", {}).get("company_name", "Unknown"),
                "facility_type": data.get("facility_profile", {}).get("facility_type", "General"),
                "country": data["country"],
                "assessment_date": data["assessment_date"],
                "processing_capacity": data.get("facility_profile", {}).get("processing_capacity", 0.0)
            }
            for assessment_id, data in processing_assessments_db.items()
        ],
        "total": len(processing_assessments_db)
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

async def call_rust_processing_backend(data: dict) -> dict:
    """
    Call the Rust backend for processing LCA calculations
    """
    try:
        # Write input to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(data, f)
            temp_file = f.name
        
        # Call Rust binary - Production paths
        rust_binary_release = "../african_lca_backend/target/release/server.exe"
        rust_binary_debug = "../african_lca_backend/target/debug/server.exe"
        
        # Determine which binary to use
        if os.path.exists(rust_binary_release):
            rust_binary = rust_binary_release
        elif os.path.exists(rust_binary_debug):
            rust_binary = rust_binary_debug
        else:
            # Clean up temp file before raising exception
            os.unlink(temp_file)
            raise Exception("Rust backend not found! Please compile with: cargo build --release")
        
        # Execute Rust backend
        result = subprocess.run(
            [rust_binary, temp_file],
            capture_output=True,
            text=True,
            timeout=120,
            cwd="../african_lca_backend"
        )
        
        # Clean up temp file
        os.unlink(temp_file)
        
        if result.returncode != 0:
            raise Exception(f"Rust backend execution failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}")
        
        # Parse and transform Rust backend results
        try:
            # Clean the output by extracting only the JSON part
            stdout_cleaned = result.stdout.strip()
            
            # Find the first '{' character which should be the start of JSON
            json_start = stdout_cleaned.find('{')
            if json_start == -1:
                raise Exception(f"No JSON found in Rust backend output: {stdout_cleaned}")
            
            # Extract only the JSON part
            json_output = stdout_cleaned[json_start:]
            
            # Find the last '}' to ensure we get the complete JSON
            json_end = json_output.rfind('}')
            if json_end != -1:
                json_output = json_output[:json_end + 1]
            
            # Try to parse the JSON
            rust_result = json.loads(json_output)
            return transform_processing_result_to_api_format(rust_result)
            
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON response from Rust backend: {e}\nOutput: {result.stdout}")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rust processing backend error: {str(e)}")

def transform_processing_result_to_api_format(rust_result: dict) -> dict:
    """
    Transform Rust processing backend result format to match Python API format
    """
    try:
        results = rust_result.get("results", {})
        
        # Extract midpoint impacts
        midpoint_impacts = {}
        rust_midpoint = results.get("midpoint_impacts", {})
        for category, data in rust_midpoint.items():
            if isinstance(data, dict) and "value" in data:
                midpoint_impacts[category] = {
                    "value": data["value"],
                    "unit": data.get("unit", "kg CO2-eq"),
                    "uncertainty_range": data.get("uncertainty_range", [0.0, 0.0]),
                    "data_quality_score": data.get("data_quality_score", 0.75),
                    "contributing_sources": data.get("contributing_sources", [])
                }
            else:
                midpoint_impacts[category] = data
        
        # Extract endpoint impacts
        endpoint_impacts = {}
        rust_endpoint = results.get("endpoint_impacts", {})
        for category, data in rust_endpoint.items():
            if isinstance(data, dict) and "value" in data:
                endpoint_impacts[category] = {
                    "value": data["value"],
                    "unit": data.get("unit", "pt"),
                    "uncertainty_range": data.get("uncertainty_range", [0.0, 0.0]),
                    "normalization_factor": data.get("normalization_factor"),
                    "regional_adaptation_factor": data.get("regional_adaptation_factor")
                }
            else:
                endpoint_impacts[category] = data
        
        # Extract single score
        single_score_data = results.get("single_score", {})
        if isinstance(single_score_data, dict):
            single_score = {
                "value": single_score_data.get("value", 0.0),
                "unit": single_score_data.get("unit", "Processing Impact Index"),
                "uncertainty_range": single_score_data.get("uncertainty_range", [0.0, 0.0]),
                "weighting_factors": single_score_data.get("weighting_factors", {}),
                "methodology": single_score_data.get("methodology", "Processing-adapted African LCA")
            }
        else:
            single_score = single_score_data or 0.0
        
        # Extract data quality
        rust_data_quality = results.get("data_quality", {})
        data_quality = {
            "overall_confidence": rust_data_quality.get("overall_confidence", "Medium"),
            "data_source_mix": rust_data_quality.get("data_source_mix", []),
            "regional_adaptation": rust_data_quality.get("regional_adaptation", True),
            "completeness_score": rust_data_quality.get("completeness_score", 0.75),
            "temporal_representativeness": rust_data_quality.get("temporal_representativeness", 0.8),
            "geographical_representativeness": rust_data_quality.get("geographical_representativeness", 0.6),
            "technological_representativeness": rust_data_quality.get("technological_representativeness", 0.7),
            "warnings": rust_data_quality.get("warnings", []),
            "recommendations": rust_data_quality.get("recommendations", [])
        }
        
        # Extract breakdown by product
        breakdown_by_product = {}
        rust_breakdown = results.get("breakdown_by_food", {})  # Rust uses "breakdown_by_food" for both
        for product_name, product_impacts in rust_breakdown.items():
            breakdown_by_product[product_name] = {}
            for category, data in product_impacts.items():
                if isinstance(data, dict) and "value" in data:
                    breakdown_by_product[product_name][category] = {
                        "value": data["value"],
                        "unit": data.get("unit", "kg CO2-eq"),
                        "uncertainty_range": data.get("uncertainty_range", [0.0, 0.0]),
                        "data_quality_score": data.get("data_quality_score", 0.75),
                        "contributing_sources": data.get("contributing_sources", [])
                    }
                else:
                    breakdown_by_product[product_name][category] = data
        
        # Build result structure
        result_data = {
            "id": rust_result.get("id"),
            "facility_profile": rust_result.get("facility_profile", {}),
            "country": rust_result.get("country"),
            "assessment_date": rust_result.get("assessment_date"),
            "midpoint_impacts": midpoint_impacts,
            "endpoint_impacts": endpoint_impacts,
            "single_score": single_score,
            "data_quality": data_quality,
            "breakdown_by_product": breakdown_by_product
        }
        
        # Add recommendations if available
        if "recommendations" in results:
            result_data["recommendations"] = results["recommendations"]
        
        return result_data
    
    except Exception as e:
        raise Exception(f"Processing result transformation failed: {str(e)}")
