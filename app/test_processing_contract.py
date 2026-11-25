"""Processing request contract: bounds, closed lists, cross-field validators and the
completeness gate. Every rejected case below was ACCEPTED before the hardening (see
docs/contract_audit/audit_processing_payload.json, probes P1 to P32).

Companion to test_request_schema.py, which holds the frontend fixture.
"""
import json

import pytest
from pydantic import ValidationError

from processing.models import ProcessingAssessmentRequest, ProcessingAssessmentResponse
from test_request_schema import FRONTEND_PROCESSING_PAYLOAD


def _proc(**overrides):
    d = json.loads(json.dumps(FRONTEND_PROCESSING_PAYLOAD))
    for dotted, value in overrides.items():
        node = d
        parts = dotted.split(".")
        for p in parts[:-1]:
            node = node[int(p)] if p.isdigit() else node[p]
        last = parts[-1]
        node[int(last) if last.isdigit() else last] = value
    return d


def _rejects(payload, fragment=None):
    with pytest.raises(ValidationError) as e:
        ProcessingAssessmentRequest(**payload)
    if fragment:
        assert fragment.lower() in str(e.value).lower(), str(e.value)
    return e.value


MINIMAL_PROCESSING_PAYLOAD = {           # audit probe P1: accepted before, nothing to assess
    "country": "Ghana",
    "facility_profile": {"facility_name": "x", "company_name": "x", "facility_type": "General",
                         "processing_capacity": 1},
    "processed_products": [{"id": "p1", "name": "p", "product_type": "Other", "annual_production": 1}],
}


def test_minimal_payload_is_rejected_by_completeness_gate():
    err = _rejects(MINIMAL_PROCESSING_PAYLOAD)
    text = str(err).lower()
    assert "no raw material" in text or "no energy input" in text


def test_minimal_payload_passes_once_complete():
    d = json.loads(json.dumps(MINIMAL_PROCESSING_PAYLOAD))
    d["processed_products"][0]["raw_material_inputs"] = [
        {"material_name": "Maize kernels", "quantity_per_tonne_output": 1050}]
    d["processing_operations"] = {"energy_management": {"monthly_electricity_consumption": 100}}
    r = ProcessingAssessmentRequest(**d)
    assert r.processed_products[0].packaging is None        # no fabricated packaging default


def test_energy_required():
    d = _proc()
    d["processing_operations"]["energy_management"] = {}
    _rejects(d, "no energy input")


def test_default_ratio_satisfies_mass_balance_but_other_does_not():
    # PalmOil has a cited conversion ratio, so no raw material is needed ...
    ProcessingAssessmentRequest(**_proc())
    # ... but product type Other at a General facility has none.
    d = _proc(**{"processed_products.0.product_type": "Other"})
    d["facility_profile"]["facility_type"] = "General"
    _rejects(d, "no raw material declared")


@pytest.mark.parametrize("dotted,value,fragment", [
    ("processed_products.0.annual_production", 0, "greater than 0"),
    ("processed_products.0.annual_production", -5, "greater than 0"),
    ("processed_products.0.annual_production", 1e12, "less than or equal"),
    ("facility_profile.processing_capacity", 0, "greater than 0"),
    ("facility_profile.operational_days_per_year", -1, "greater than or equal"),
    ("facility_profile.operational_days_per_year", 100000, "less than or equal"),
    ("facility_profile.operational_days_per_year", 250.5, "integer"),
    ("facility_profile.operational_hours_per_day", 25, "less than or equal"),
    ("facility_profile.facility_name", "", "at least 1"),
    ("processing_operations.energy_management.monthly_electricity_consumption", -100, "greater than or equal"),
    ("processing_operations.energy_management.renewable_energy_percentage", 250, "less than or equal"),
    ("processing_operations.energy_management.fuel_streams.0.monthly_consumption", -30, "greater than 0"),
    ("processing_operations.energy_management.fuel_streams.0.monthly_consumption", 0, "greater than 0"),
    ("processing_operations.water_management.monthly_water_consumption", -3, "greater than or equal"),
    ("processing_operations.waste_management.solid_waste_generation", -10, "greater than or equal"),
    ("processing_operations.waste_management.organic_waste_percentage", 500, "less than or equal"),
    ("processing_operations.waste_management.byproduct_utilization.0.percentage_utilized", 900, "less than or equal"),
    ("processing_operations.raw_material_sourcing.average_transport_distance", -50, "greater than or equal"),
    ("processing_operations.raw_material_sourcing.local_sourcing_percentage", 150, "less than or equal"),
    ("processing_operations.raw_material_sourcing.storage_practices", {"storage_loss_percentage": 80}, "less than or equal"),
    ("processed_products.0.packaging.package_size", 0, "greater than 0"),
    ("processed_products.0.packaging.packaging_weight_per_unit", -1, "greater than 0"),
    ("processed_products.0.economic_value", -3, "greater than or equal"),
    ("processed_products.0.name", "", "at least 1"),
])
def test_numeric_and_text_bounds(dotted, value, fragment):
    _rejects(_proc(**{dotted: value}), fragment)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_rejects_nan_and_infinity(value):
    _rejects(_proc(**{"processed_products.0.annual_production": value}))
    _rejects(_proc(**{"processing_operations.energy_management.monthly_electricity_consumption": value}))


def test_raw_material_quantity_must_be_positive_and_plausible():
    for qty in (0, -1000):
        d = _proc()
        d["processed_products"][0]["raw_material_inputs"] = [
            {"material_name": "maize", "quantity_per_tonne_output": qty}]
        _rejects(d, "greater than 0")
    d = _proc()
    d["processed_products"][0]["raw_material_inputs"] = [
        {"material_name": "maize", "quantity_per_tonne_output": 1e9}]
    _rejects(d, "less than or equal")


def test_fuel_type_and_unit_are_closed_lists():
    _rejects(_proc(**{"processing_operations.energy_management.fuel_streams.0.fuel_type": "Unobtainium"}))
    _rejects(_proc(**{"processing_operations.energy_management.fuel_streams.0.unit": "gallons"}))
    # synonyms and case are normalised rather than rejected
    r = ProcessingAssessmentRequest(**_proc(**{
        "processing_operations.energy_management.fuel_streams.1.fuel_type": "diesel generator",
        "processing_operations.energy_management.fuel_streams.1.unit": "litres"}))
    s = r.processing_operations.energy_management.fuel_streams[1]
    assert s.fuel_type.value == "Diesel generator" and s.unit.value == "L"
    r = ProcessingAssessmentRequest(**_proc(**{
        "processing_operations.energy_management.fuel_streams.0.fuel_type": "Liquefied Petroleum Gas (LPG)"}))
    assert r.processing_operations.energy_management.fuel_streams[0].fuel_type.value == "LPG"


def test_water_source_is_a_closed_list():
    _rejects(_proc(**{"processing_operations.water_management.water_source": ["Ocean"]}))
    r = ProcessingAssessmentRequest(**_proc(**{
        "processing_operations.water_management.water_source": ["municipal water supply", "River/Stream"]}))
    assert [s.value for s in r.processing_operations.water_management.water_source] == ["Municipal", "River"]


def test_refrigerant_must_be_a_known_gas():
    _rejects(_proc(**{"processing_operations.refrigerant_management":
                      {"refrigerant_type": "Freon-X", "annual_leakage_kg": 5}}), "not a known designation")
    _rejects(_proc(**{"processing_operations.refrigerant_management": {"annual_leakage_kg": 5}}),
             "refrigerant_type is missing")
    _rejects(_proc(**{"processing_operations.refrigerant_management":
                      {"refrigerant_type": "R-134a", "annual_leakage_kg": 1e9}}), "less than or equal")
    r = ProcessingAssessmentRequest(**_proc(**{"processing_operations.refrigerant_management":
                                               {"refrigerant_type": "r 404a", "annual_leakage_kg": 5}}))
    assert r.processing_operations.refrigerant_management.refrigerant_type == "R-404A"
    r = ProcessingAssessmentRequest(**_proc(**{"processing_operations.refrigerant_management":
                                               {"refrigerant_type": "none"}}))
    assert r.processing_operations.refrigerant_management.refrigerant_type == "None"


def test_region_must_resolve():
    _rejects(_proc(country="Global", region="Mars"), "do not resolve")
    # a free-text province falls through to the country (archived example payloads do this)
    ProcessingAssessmentRequest(**_proc(country="Ghana", region="Greater Accra"))
    ProcessingAssessmentRequest(**_proc(country="Global", region="Ontario"))
    _rejects(_proc(country="Canada"), "invalid country")


def test_duplicate_product_names_rejected():
    d = _proc()
    second = json.loads(json.dumps(d["processed_products"][0]))
    second["id"], second["name"] = "product_2", "crude PALM oil"
    d["processed_products"].append(second)
    _rejects(d, "duplicate product name")


def test_economic_allocation_requires_prices():
    _rejects(_proc(allocation_basis="economic"), "economic allocation requires a price")
    d = _proc(allocation_basis="economic")
    d["processed_products"][0]["economic_value"] = 0
    _rejects(d, "economic allocation requires a price")
    d["processed_products"][0]["economic_value"] = 12.5
    ProcessingAssessmentRequest(**d)


def test_byproduct_shares_cannot_exceed_the_waste_stream():
    d = _proc()
    d["processing_operations"]["waste_management"]["byproduct_utilization"] = [
        {"byproduct_name": "a", "utilization_method": "x", "percentage_utilized": 60},
        {"byproduct_name": "b", "utilization_method": "y", "percentage_utilized": 60}]
    _rejects(d, "100% or less")


def test_response_model_tolerates_archived_profiles():
    """Request-side bounds must never make an old saved assessment unreadable."""
    r = ProcessingAssessmentResponse(
        id="x", facility_profile={"facility_name": "", "company_name": "", "facility_type": "Mill",
                                  "processing_capacity": 0.0},
        country="Ghana", assessment_date="2026-01-01T00:00:00", midpoint_impacts={},
        endpoint_impacts={}, single_score=0.0, data_quality={}, breakdown_by_product={})
    assert r.facility_profile["processing_capacity"] == 0.0
