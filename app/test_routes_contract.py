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
