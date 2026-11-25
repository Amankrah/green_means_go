"""Engine-side guarantees behind the processing contract: nothing is dropped silently,
packaging is never fabricated, an unknown refrigerant is an error, fuel units are a
closed vocabulary, and an unresolvable region is refused."""
from __future__ import annotations

import pytest

from engine.process_inputs import extract_processing_inputs


def _base_req(**ops):
    return {
        "facility_profile": {"operational_days_per_year": 250, "facility_type": "Mill"},
        "processing_operations": ops,
        "processed_products": [{
            "name": "flour", "annual_production": 10.0, "product_type": "FlourMaize",
            "raw_material_inputs": [{"material_name": "maize", "quantity_per_tonne_output": 1250.0}],
        }],
    }


def test_skipped_rows_always_leave_a_warning_note():
    """Direct engine callers bypass the API bounds; nothing may be dropped silently."""
    req = _base_req(
        energy_management={"monthly_electricity_consumption": -100,
                           "fuel_streams": [{"fuel_type": "Diesel", "monthly_consumption": -5}]},
        water_management={"monthly_water_consumption": -3},
        waste_management={"solid_waste_generation": -10},
        raw_material_sourcing={"average_transport_distance": -50})
    req["processed_products"][0]["raw_material_inputs"].append(
        {"material_name": "bran", "quantity_per_tonne_output": -1})
    req["processed_products"][0]["packaging"] = {"package_size": 0, "packaging_weight_per_unit": -1}
    inputs, notes, _ = extract_processing_inputs(req)
    warnings = [n for n in notes if n.startswith("WARNING")]
    for frag in ("electricity", "fuel stream", "water", "solid waste", "transport distance",
                 "raw material 'bran'", "packaging skipped"):
        assert any(frag in w for w in warnings), (frag, warnings)
    assert not [i for i in inputs if i["kind"] in ("fuel", "water", "waste", "transport", "packaging")]


def test_zero_transport_distance_means_no_inbound_transport_with_a_note():
    inputs, notes, _ = extract_processing_inputs(
        _base_req(raw_material_sourcing={"average_transport_distance": 0}))
    assert not [i for i in inputs if i["kind"] == "transport"]
    assert any("declared as 0 km" in n for n in notes)


def test_no_packaging_means_unpackaged_not_a_fabricated_default():
    inputs, notes, _ = extract_processing_inputs(_base_req())
    assert not [i for i in inputs if i["kind"] == "packaging"]
    assert any("no packaging declared" in n for n in notes)


def test_unknown_refrigerant_is_an_error_not_a_default():
    from engine.refrigerants import refrigerant_co2e, canonical_name, KNOWN_REFRIGERANTS
    assert canonical_name("r 134a") == "R-134a" and canonical_name("Freon-X") is None
    assert "R-404A" in KNOWN_REFRIGERANTS
    with pytest.raises(ValueError):
        refrigerant_co2e("Freon-X", 10.0)
    co2e, note = refrigerant_co2e("R-404A", 2.0)
    assert co2e == 2.0 * 3728.0 and "AR6" in note
    assert refrigerant_co2e("Freon-X", 0.0) == (0.0, "")     # no leak, nothing to characterise


def test_fuel_unit_vocabulary():
    from engine.energy_carriers import normalise_fuel_unit, FUEL_UNITS
    assert normalise_fuel_unit("litres") == "L" and normalise_fuel_unit("KG") == "kg"
    assert normalise_fuel_unit("gallons") is None and normalise_fuel_unit("kWh") is None
    assert set(FUEL_UNITS) == {"L", "kg", "m3", "MJ"}


def test_unresolvable_region_is_refused_not_defaulted():
    from engine.process_service import _resolve_region
    assert _resolve_region({"country": "Ghana", "region": "Greater Accra"}, None) == "GH"
    assert _resolve_region({"country": "Global", "region": "Ontario"}, None) == "CA"
    assert _resolve_region({"country": "Nigeria"}, "ZA") == "ZA"
    with pytest.raises(ValueError):
        _resolve_region({"country": "Atlantis", "region": "Mars"}, None)
