"""Request contract tests: unknown keys are rejected (extra="forbid"), so a renamed field can
never again be silently dropped the way the wizard's `pesticides_used` was.

The two FRONTEND_* fixtures mirror exactly what african-lca-frontend builds
(lib/api.ts transformEnhancedAssessmentToBackend and
lib/processing-assessment-schema.ts buildProcessingPayload). Change them together.
"""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from production.models import AssessmentRequest
from processing.models import ProcessingAssessmentRequest

ROOT = Path(__file__).resolve().parents[1]

FRONTEND_FARM_PAYLOAD = {
    "company_name": "Ama Mensah - Mensah Farms",
    "country": "Ghana",
    "region": "GH",
    "farm_profile": {
        "farmer_name": "Ama Mensah", "farm_name": "Mensah Farms", "total_farm_size": 3.0,
        "farming_experience": 12, "farm_type": "SmallScale", "primary_farming_system": "SemiCommercial",
        "certifications": [], "participates_in_programs": [],
    },
    "management_practices": {
        "soil_management": {
            "soil_type": "SandyLoam", "uses_compost": True, "compost_source": "Farm-made compost",
            "compost_application_rate": 2.0, "conservation_practices": ["Mulching"],
            "soil_testing_frequency": "Every 2-3 years",
        },
        "fertilization": {
            "uses_fertilizers": True,
            "fertilizer_applications": [
                {"fertilizer_type": "Ammonium Sulfate", "npk_ratio": "21-0-0", "application_rate": 100,
                 "applications_per_season": 1, "cost": 300},
            ],
            "soil_test_based": False, "follows_nutrient_plan": False,
        },
        "water_management": {
            "water_source": ["Borehole"], "irrigation_system": "Drip Irrigation",
            "irrigation_water_m3": 1200.0, "water_conservation_practices": ["Rainwater Harvesting"],
        },
        "pest_management": {
            "management_approach": "Integrated Pest Management (IPM)", "uses_ipm": True,
            "pesticides": [
                {"pesticide_type": "Insecticide", "active_ingredient": "Lambda-cyhalothrin",
                 "application_rate": 0.5, "applications_per_season": 2,
                 "active_ingredient_content": 0.025, "target_pests": ["Fall armyworm"]},
            ],
            "pest_monitoring_frequency": "Weekly",
        },
    },
    "equipment_energy": {
        "equipment": [{"equipment_type": "Water Pump", "power_source": "Petrol engine", "age": 2,
                       "hours_per_year": 300, "fuel_efficiency": 1.2}],
        "energy_sources": [{"energy_type": "Solar Panels", "monthly_consumption": 40, "unit": "kWh",
                            "primary_use": "Lighting", "cost": 0, "currency": "GHS"}],
        "fuel_consumption": [{"fuel_type": "Liquefied Petroleum Gas (LPG)", "monthly_consumption": 6,
                              "unit": "kg", "primary_use": "Drying", "cost": 120}],
    },
    "logistics": {"packaging_material": "Polypropylene sacks", "packaging_kg_per_tonne": None,
                  "distance_to_market_km": 25.0, "market_transport_mode": "Pickup truck",
                  "input_transport_km": None},
    "foods": [{
        "id": "crop_1", "name": "Tomato", "quantity_kg": 12000, "category": "Vegetables",
        "crop_type": "Pectomech", "origin_country": "Ghana", "production_system": "Irrigated",
        "seasonal_factor": "DrySeason", "variety": "Pectomech", "area_allocated": 1.0,
        "cropping_pattern": "Monoculture", "intercropping_partners": [], "post_harvest_losses": 20,
        "seed_rate_kg_per_ha": 0.3,
    }],
}

FRONTEND_PROCESSING_PAYLOAD = {
    "country": "Ghana", "region": "GH", "title": "Kumasi Palm Mill", "allocation_basis": "mass",
    "facility_profile": {
        "facility_name": "Kumasi Palm Mill", "company_name": "Kumasi Palm Mill",
        "facility_type": "PalmOilMill", "processing_capacity": 20, "operational_hours_per_day": 10,
        "operational_days_per_year": 220, "location_type": "Rural", "admin_region": "Ashanti",
    },
    "processing_operations": {
        "energy_management": {
            "primary_energy_source": "GridElectricity", "monthly_electricity_consumption": 4000,
            "renewable_energy_percentage": 0,
            "fuel_streams": [{"fuel_type": "Palm kernel shell", "monthly_consumption": 30000, "unit": "kg"},
                             {"fuel_type": "Diesel generator", "monthly_consumption": 400, "unit": "L"}],
        },
        "water_management": {"monthly_water_consumption": 600, "water_source": ["Borehole"],
                             "water_treatment": "BasicFiltration", "wastewater_treatment": "None"},
        "waste_management": {"solid_waste_generation": 500, "organic_waste_percentage": 90,
                             "waste_disposal_method": "Composting",
                             "byproduct_utilization": [{"byproduct_name": "Empty fruit bunches",
                                                        "utilization_method": "Mulch",
                                                        "percentage_utilized": 60}]},
        "raw_material_sourcing": {"average_transport_distance": None, "local_sourcing_percentage": 70,
                                  "transport_mode": "Truck"},
        "refrigerant_management": {},
    },
    "processed_products": [{
        "id": "product_1", "name": "Crude palm oil", "product_type": "PalmOil", "annual_production": 900,
        "raw_material_inputs": [],
        "packaging": {"packaging_material": "Metal", "package_size": 25, "packaging_weight_per_unit": 1.2},
    }],
}


def test_frontend_farm_payload_validates_and_keeps_pesticides():
    r = AssessmentRequest(**FRONTEND_FARM_PAYLOAD)
    assert len(r.management_practices.pest_management.pesticides) == 1
    assert r.logistics.distance_to_market_km == 25.0


def test_frontend_processing_payload_validates():
    r = ProcessingAssessmentRequest(**FRONTEND_PROCESSING_PAYLOAD)
    assert len(r.processing_operations.energy_management.fuel_streams) == 2


@pytest.mark.parametrize("path", sorted((ROOT / "engine" / "case_studies").glob("*.json")),
                         ids=lambda p: p.stem)
def test_case_studies_validate(path):
    AssessmentRequest(**json.loads(path.read_text(encoding="utf-8")))


@pytest.mark.parametrize("name", ["example_assessment.json", "example_cassava_processing.json"])
def test_processing_examples_validate(name):
    ProcessingAssessmentRequest(**json.loads((ROOT / "app" / "processing" / name).read_text(encoding="utf-8")))


def _with(payload, path, key, value):
    d = json.loads(json.dumps(payload))
    node = d
    for p in path:
        node = node[p]
    node[key] = value
    return d


@pytest.mark.parametrize("path,key", [
    ((), "bogus_top_level"),
    (("management_practices", "pest_management"), "pesticide_list"),
    (("management_practices", "water_management"), "irrigation_volume"),
    (("equipment_energy",), "infrastructure"),
    (("foods", 0), "yield_per_ha"),
])
def test_unknown_farm_keys_rejected(path, key):
    with pytest.raises(ValidationError) as e:
        AssessmentRequest(**_with(FRONTEND_FARM_PAYLOAD, path, key, 1))
    assert "extra" in str(e.value).lower()


@pytest.mark.parametrize("path,key", [
    ((), "bogus"),
    (("processing_operations", "energy_management"), "fuel_type_2"),
    (("processed_products", 0), "shelf_life"),
])
def test_unknown_processing_keys_rejected(path, key):
    with pytest.raises(ValidationError):
        ProcessingAssessmentRequest(**_with(FRONTEND_PROCESSING_PAYLOAD, path, key, 1))


def test_legacy_wizard_keys_are_mapped_or_dropped():
    d = json.loads(json.dumps(FRONTEND_FARM_PAYLOAD))
    pm = d["management_practices"]["pest_management"]
    pm["pesticides_used"] = pm.pop("pesticides")
    pm["monitoring_frequency"] = pm.pop("pest_monitoring_frequency")
    d["foods"][0]["farm_profile"] = d["farm_profile"]          # old wizard nested copies
    r = AssessmentRequest(**d)
    assert r.management_practices.pest_management.pesticides[0].active_ingredient == "Lambda-cyhalothrin"
    assert r.management_practices.pest_management.pest_monitoring_frequency == "Weekly"
    assert "farm_profile" not in r.foods[0].model_dump()


def test_removed_processing_fields_accepted_from_archives_but_not_kept():
    d = json.loads(json.dumps(FRONTEND_PROCESSING_PAYLOAD))
    em = d["processing_operations"]["energy_management"]
    em["backup_generator"] = True
    em["secondary_energy_sources"] = ["DieselGenerator"]
    d["processing_operations"]["equipment_efficiency"] = {"equipment_age": "Old"}
    d["processed_products"][0]["processing_steps"] = [
        {"step_name": "press", "energy_intensity": 20, "water_usage": 100, "duration": 2,
         "yield_efficiency": 90, "emissions_factor": 5}]
    r = ProcessingAssessmentRequest(**d)
    dumped = r.model_dump()
    assert "backup_generator" not in dumped["processing_operations"]["energy_management"]
    assert "equipment_efficiency" not in dumped["processing_operations"]
    assert set(dumped["processed_products"][0]["processing_steps"][0]) == {
        "step_name", "energy_intensity", "water_usage"}
