"""Route-level contract: every AssessmentRequest field the engine reads must reach the
engine input that app/production/routes.py builds.

`logistics` was validated by pydantic, archived with the request and read by
engine/inputs.py, yet _build_farm_rust_input never copied it, so packaging and transport
were silently discarded. The model test and the engine test each passed; nothing tested
the route in between. This test closes that gap and fails when a new field is added to
AssessmentRequest without being forwarded (or added to ENGINE_INPUT_EXCLUDED_FIELDS).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "app"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from production.models import AssessmentRequest            # noqa: E402
from production.routes import (                             # noqa: E402
    ENGINE_INPUT_EXCLUDED_FIELDS,
    _build_farm_rust_input,
    _client_error,
)
from test_request_schema import FRONTEND_FARM_PAYLOAD      # noqa: E402


def _full_request() -> AssessmentRequest:
    d = json.loads(json.dumps(FRONTEND_FARM_PAYLOAD))
    d["study_meta"] = {"crop_year": 2025, "season": "major", "admin_region": "Ashanti"}
    d["ipcc_ef1_scale"] = 1.2
    d["farm_id"] = None
    d["title"] = "contract"
    d["form_snapshot"] = {"step": 3}
    d["lcia_method"] = "EF v3.1"
    d["run_uncertainty"] = False
    return AssessmentRequest(**d)


def test_every_engine_field_is_forwarded():
    req = _full_request()
    built = _build_farm_rust_input(req)
    expected = set(AssessmentRequest.model_fields) - ENGINE_INPUT_EXCLUDED_FIELDS
    missing = sorted(f for f in expected if f not in built)
    assert not missing, (
        f"AssessmentRequest fields not forwarded to the engine: {missing}. Either copy them "
        "in _build_farm_rust_input or list them in ENGINE_INPUT_EXCLUDED_FIELDS with a reason.")
    # and nothing report-only leaks into the engine input
    leaked = sorted(f for f in ENGINE_INPUT_EXCLUDED_FIELDS if f in built)
    assert not leaked


def test_logistics_reaches_engine_with_values():
    built = _build_farm_rust_input(_full_request())
    assert built["logistics"]["distance_to_market_km"] == 25.0
    assert built["logistics"]["packaging_material"] == "Polypropylene sacks"
    assert built["study_meta"] == {"crop_year": 2025, "season": "major", "admin_region": "Ashanti"}
    assert built["ipcc_ef1_scale"] == 1.2


def test_engine_input_is_plain_json():
    """Enum members must arrive as their string values: the engine keys dict lookups and
    keyword matching on them, and str(StrEnum) is the qualified name on Python 3.11+."""
    built = _build_farm_rust_input(_full_request())
    json.dumps(built)   # no custom encoder needed
    wm = built["management_practices"]["water_management"]
    assert wm["irrigation_system"] == "Drip Irrigation"
    assert wm["water_source"] == ["Borehole"]
    assert built["management_practices"]["soil_management"]["compost_source"] == "Farm-made compost"
    assert built["management_practices"]["pest_management"]["pesticides"][0]["pesticide_type"] == "Insecticide"
    assert built["equipment_energy"]["equipment"][0]["power_source"] == "Petrol engine"
    assert built["equipment_energy"]["energy_sources"][0]["energy_type"] == "Solar Panels"
    assert built["farm_profile"]["farm_type"] == "SmallScale"


def test_contract_fields_reach_engine_input():
    """CONTRACT §1 fields are forwarded with their snake_case names and values."""
    from test_request_schema import _contract_payload
    built = _build_farm_rust_input(AssessmentRequest(**_contract_payload()))
    json.dumps(built)
    rice = built["foods"][1]
    assert rice["crops_per_year"] == 2 and rice["growing_period_days"] == 120
    assert rice["planting_months"] == [4, 9] and rice["harvest_months"] == [8, 12]
    assert rice["rotation_sequence"] == ["Cowpea", "Maize"]
    assert rice["water_regime"] == "irrigated_multiple_drainage"
    assert rice["preseason_water_status"] == "non_flooded_lt_180d"
    mp = built["management_practices"]
    sm = mp["soil_management"]
    assert sm["soil_ph"] == 5.8 and sm["cover_crops"] is True
    assert sm["practices_adopted_years_ago"] == 6 and sm["compost_crop_ids"] == ["crop_1"]
    assert sm["lime_applications"] == [
        {"material": "dolomite", "rate_t_per_ha_per_year": 0.5, "crop_ids": ["crop_2"]}]
    fa = mp["fertilization"]["fertilizer_applications"][0]
    assert fa["application_method"] == "broadcast" and fa["brand_name"] == "Yara Sulfan"
    assert fa["crop_ids"] == ["crop_1"]
    assert mp["fertilization"]["timing_strategy"] == "Split Application"
    pest = mp["pest_management"]
    assert pest["pesticides"][0]["brand_name"] == "Karate"
    assert pest["pesticides"][0]["crop_ids"] == ["crop_1", "crop_2"]
    assert pest["uses_economic_thresholds"] is True
    assert mp["water_management"]["drainage_system"] == "Surface drains"
    assert built["equipment_energy"]["storage"] == {
        "facilities": ["Cold Storage", "Metal Silos"], "capacity_tonnes": 20.0,
        "refrigerant": "R-404A", "refrigerant_charge_kg": 4.0}


def test_legacy_rust_lcia_is_never_served(monkeypatch):
    """USE_LEGACY_RUST_LCIA used to route /assess to the Rust kernel's hardcoded LCIA."""
    import asyncio
    import engine.service
    import production.routes as pr
    import processing.routes as proc
    monkeypatch.setenv("USE_LEGACY_RUST_LCIA", "1")
    calls = []
    monkeypatch.setattr(engine.service, "run_farm_assessment",
                        lambda rust_input, **kw: calls.append(kw) or {"served_by": "engine"})
    assert asyncio.run(pr._run_farm_engine(_full_request())) == {"served_by": "engine"}
    assert calls and calls[0]["method"] == "EF v3.1"
    for mod in (pr, proc):
        assert not hasattr(mod, "call_rust_backend")
        assert not hasattr(mod, "call_rust_processing_backend")


def test_excluded_fields_exist_on_model():
    """The allowlist must not drift: every excluded name is a real request field."""
    unknown = ENGINE_INPUT_EXCLUDED_FIELDS - set(AssessmentRequest.model_fields)
    assert not unknown


def test_value_error_maps_to_422():
    exc = _client_error(ValueError("unknown region 'XX'"))
    assert exc is not None and exc.status_code == 422
    assert _client_error(RuntimeError("boom")) is None


def test_unknown_region_rejected_at_the_model():
    d = json.loads(json.dumps(FRONTEND_FARM_PAYLOAD))
    d["region"] = "Mars"
    with pytest.raises(Exception) as e:
        AssessmentRequest(**d)
    assert "region" in str(e.value).lower()


@pytest.mark.parametrize("alias,code", [("ghana", "GH"), ("Nigeria", "NG"), ("sn", "SN"),
                                        ("Saskatchewan", "CA"), ("ZA", "ZA")])
def test_region_aliases_normalised_to_engine_codes(alias, code):
    d = json.loads(json.dumps(FRONTEND_FARM_PAYLOAD))
    d["region"] = alias
    d["country"] = "Global" if code == "CA" else d["country"]
    assert AssessmentRequest(**d).region == code
