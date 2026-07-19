"""Unit checks for processing input extraction (refined hints + fuel fallback chain)."""
from __future__ import annotations

from engine.process_inputs import _raw_material_match, extract_processing_inputs


def test_refined_beats_crop_keyword():
    hint, refined = _raw_material_match("Wheat flour")
    assert refined is True
    assert "flour" in hint.lower() or "wheat flour" in hint.lower()

    hint, refined = _raw_material_match("crude palm oil")
    assert refined is True
    assert "palm oil" in hint.lower()

    hint, refined = _raw_material_match("maize grain")
    assert refined is False
    assert "maize grain production" == hint


def test_crop_still_maps_farm_gate():
    hint, refined = _raw_material_match("Yellow maize kernels")
    assert refined is False
    assert hint == "maize grain production"


def test_fuel_fallback_chain_prefers_building_then_heat():
    req = {
        "facility_profile": {"operational_days_per_year": 250},
        "processing_operations": {
            "energy_management": {
                "monthly_fuel_consumption": 100.0,
                "fuel_type": "Diesel",
            }
        },
        "processed_products": [
            {"name": "flour", "annual_production": 1.0, "raw_material_inputs": []}
        ],
    }
    inputs, notes, _ = extract_processing_inputs(req)
    fuel = next(i for i in inputs if i["kind"] == "fuel")
    assert fuel["match_as"] == "diesel, burned in building machine"
    assert fuel["fallbacks"][0] == "heat production, natural gas"
    assert fuel["fallbacks"][-1] == "diesel, burned in agricultural machinery"


def test_refined_raw_material_note():
    req = {
        "facility_profile": {"operational_days_per_year": 250},
        "processing_operations": {},
        "processed_products": [{
            "name": "bread",
            "annual_production": 10.0,
            "raw_material_inputs": [
                {"material_name": "wheat flour", "quantity_per_tonne_output": 800.0},
            ],
        }],
    }
    inputs, notes, _ = extract_processing_inputs(req)
    flour = next(i for i in inputs if i["name"] == "wheat flour")
    assert flour["refined"] is True
    assert any("already-processed ingredient" in n for n in notes)


if __name__ == "__main__":
    test_refined_beats_crop_keyword()
    test_crop_still_maps_farm_gate()
    test_fuel_fallback_chain_prefers_building_then_heat()
    test_refined_raw_material_note()
    print("ok")
