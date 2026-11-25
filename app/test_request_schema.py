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


def test_ws1_advanced_food_fields_accepted_and_validated():
    d = json.loads(json.dumps(FRONTEND_FARM_PAYLOAD))
    d["foods"][0]["land_use_change"] = {"previous_land_use": "forest", "years_since_conversion": 5}
    d["foods"][0]["residue_management"] = {"fraction_removed": 0.3, "fraction_burnt": 0.1}
    d["foods"][0]["establishment"] = {"immature_years": 3, "productive_years": 25, "input_share": 0.1}
    r = AssessmentRequest(**d)
    assert r.foods[0].land_use_change.previous_land_use == "forest"
    d["foods"][0]["residue_management"]["fraction_burnt"] = 1.5
    with pytest.raises(ValidationError):
        AssessmentRequest(**d)


# ---------------------------------------------------------------------------------------
# Hardening (contract audit, docs/contract_audit/audit_farm_payload.json): bounds, closed
# vocabularies and cross-field rules. Each case used to be ACCEPTED by the API.
# ---------------------------------------------------------------------------------------
def _farm(**patch):
    d = json.loads(json.dumps(FRONTEND_FARM_PAYLOAD))
    for path, value in patch.items():
        keys = path.split(".")
        cur = d
        for k in keys[:-1]:
            cur = cur[int(k)] if isinstance(cur, list) else cur[k]
        last = keys[-1]
        if isinstance(cur, list):
            cur[int(last)] = value
        else:
            cur[last] = value
    return d


def _rejects(d, needle=None):
    with pytest.raises(ValidationError) as e:
        AssessmentRequest(**d)
    if needle:
        assert needle.lower() in str(e.value).lower(), str(e.value)


@pytest.mark.parametrize("path,value,needle", [
    ("foods.0.area_allocated", -2, "greater than 0"),
    ("foods.0.area_allocated", 0, "greater than 0"),
    ("foods.0.area_allocated", 1e9, "less than or equal"),
    ("foods.0.quantity_kg", 0, "greater than 0"),
    ("foods.0.quantity_kg", float("nan"), "finite"),
    ("foods.0.quantity_kg", float("inf"), "finite"),
    ("foods.0.post_harvest_losses", 150, "less than or equal"),
    ("management_practices.fertilization.fertilizer_applications.0.application_rate", -200, "greater than or equal"),
    ("management_practices.fertilization.fertilizer_applications.0.application_rate", 1e9, "less than or equal"),
    ("management_practices.fertilization.fertilizer_applications.0.applications_per_season", 99, "less than or equal"),
    ("management_practices.soil_management.compost_application_rate", -10, "greater than or equal"),
    ("management_practices.soil_management.compost_application_rate", 1e6, "less than or equal"),
    ("management_practices.water_management.irrigation_water_m3", -1, "greater than or equal"),
    ("management_practices.pest_management.pesticides.0.application_rate", 1e4, "less than or equal"),
    ("management_practices.pest_management.pesticides.0.active_ingredient_content", 1.5, "less than or equal"),
    ("equipment_energy.equipment.0.hours_per_year", -5, "greater than or equal"),
    ("equipment_energy.equipment.0.hours_per_year", 20000, "less than or equal"),
    ("equipment_energy.energy_sources.0.monthly_consumption", -40, "greater than or equal"),
    ("equipment_energy.fuel_consumption.0.monthly_consumption", 1e12, "less than or equal"),
    ("farm_profile.total_farm_size", 0, "greater than 0"),
    ("farm_profile.farming_experience", -1, "greater than or equal"),
    ("logistics.distance_to_market_km", -25, "greater than or equal"),
    ("ipcc_ef1_scale", 0, "greater than 0"),
])
def test_numeric_bounds_rejected(path, value, needle):
    _rejects(_farm(**{path: value}), needle)


def test_empty_foods_rejected():
    _rejects(_farm(foods=[]), "at least 1")


@pytest.mark.parametrize("path,value", [
    ("management_practices.water_management.irrigation_system", "Teleportation"),
    ("management_practices.water_management.water_source", ["Ocean"]),
    ("management_practices.pest_management.pesticides.0.pesticide_type", "Magic dust"),
    ("management_practices.soil_management.compost_source", "Moon dust"),
    ("equipment_energy.equipment.0.power_source", "Nuclear"),
    ("equipment_energy.energy_sources.0.energy_type", "Fusion"),
    ("equipment_energy.fuel_consumption.0.unit", "gallons"),
])
def test_closed_vocabularies_reject_unknown_values(path, value):
    _rejects(_farm(**{path: value}), "not recognised" if "unit" not in path else "not supported")


def test_vocabularies_normalise_wizard_and_archived_spellings():
    d = _farm(**{
        "management_practices.water_management.irrigation_system": "Sprinkler",
        "management_practices.water_management.water_source": ["river", "Borehole", "borehole"],
        "management_practices.soil_management.compost_source": "Farm-made compost (fosse fumiere)",
        "equipment_energy.equipment.0.power_source": "Diesel",
        "equipment_energy.energy_sources.0.energy_type": "Grid Electricity",
        "equipment_energy.fuel_consumption.0.unit": "litres",
    })
    r = AssessmentRequest(**d)
    wm = r.management_practices.water_management
    assert wm.irrigation_system.value == "Sprinkler System"
    assert [w.value for w in wm.water_source] == ["River/Stream", "Borehole"]
    assert r.management_practices.soil_management.compost_source.value == "Farm-made compost"
    assert r.equipment_energy.equipment[0].power_source.value == "Diesel engine"
    assert r.equipment_energy.fuel_consumption[0].unit == "L"


def test_free_text_fertiliser_and_fuel_names_still_accepted():
    """Trade names are classified by the intelligence layer; the API must not block them."""
    d = _farm(**{
        "management_practices.fertilization.fertilizer_applications.0.fertilizer_type": "compound fert. (the blue bag)",
        "equipment_energy.fuel_consumption.0.fuel_type": "gas oil from the roadside seller",
    })
    AssessmentRequest(**d)


def test_area_required_when_inputs_declared():
    d = _farm()
    d["foods"][0].pop("area_allocated")
    _rejects(d, "area_allocated (ha) is required")


def test_area_not_required_for_bare_product_assessment():
    d = {"company_name": "x", "country": "Ghana",
         "foods": [{"id": "1", "name": "Maize", "quantity_kg": 100, "category": "Cereals"}]}
    assert AssessmentRequest(**d).foods[0].area_allocated is None


def test_fertiliser_flag_must_match_rows():
    _rejects(_farm(**{"management_practices.fertilization.uses_fertilizers": False}),
             "uses_fertilizers is false")
    d = _farm(**{"management_practices.fertilization.fertilizer_applications": []})
    _rejects(d, "uses_fertilizers is true")
    # all-zero rows with the flag off are tolerated (the wizard keeps empty rows around)
    d = _farm(**{"management_practices.fertilization.uses_fertilizers": False,
                 "management_practices.fertilization.fertilizer_applications.0.application_rate": 0})
    AssessmentRequest(**d)


def test_compost_flag_requires_rate_and_source():
    _rejects(_farm(**{"management_practices.soil_management.compost_application_rate": 0}),
             "uses_compost is true")
    _rejects(_farm(**{"management_practices.soil_management.compost_source": "Not used"}),
             "uses_compost is true")
    # flag off: rate and source are ignored by the engine, so they are not an error
    AssessmentRequest(**_farm(**{"management_practices.soil_management.uses_compost": False}))


def test_crop_areas_cannot_exceed_farm_size():
    _rejects(_farm(**{"foods.0.area_allocated": 3.5}), "total_farm_size")
    AssessmentRequest(**_farm(**{"foods.0.area_allocated": 3.0}))


def test_bad_region_is_a_validation_error_not_a_500():
    _rejects(_farm(region="Mars"), "unknown region")
    assert AssessmentRequest(**_farm(region="ghana")).region == "GH"
