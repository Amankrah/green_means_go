"""The archived request -> recommendation context bridge (app/recommendations/service.py)
reads the CONTRACT §1 seasonality and practice fields."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "app"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from production.models import AssessmentRequest          # noqa: E402
from recommendations.service import _farm_context       # noqa: E402
from test_request_schema import FRONTEND_FARM_PAYLOAD, _contract_payload  # noqa: E402


def _api(d: dict) -> dict:
    return AssessmentRequest(**d).model_dump(mode="json")


def test_seasons_per_year_is_area_weighted_crops_per_year():
    ctx = _farm_context(_api(_contract_payload()))
    # tomato 1 ha x 1 season, rice 1 ha x 2 seasons
    assert ctx["seasons_per_year"] == 1.5


def test_seasons_per_year_absent_for_archived_requests():
    api = _api(FRONTEND_FARM_PAYLOAD)
    for f in api["foods"]:
        f.pop("crops_per_year")
    assert "seasons_per_year" not in _farm_context(api)


def test_rice_water_regime_drives_irrigated_rice_flag():
    d = _contract_payload()
    assert _farm_context(_api(d))["flags"]["irrigated_rice"] is True
    d["foods"][1]["water_regime"] = "rainfed_regular"
    assert _farm_context(_api(d))["flags"]["irrigated_rice"] is False
    d["foods"][1]["water_regime"] = None      # falls back to the farm irrigation system
    assert _farm_context(_api(d))["flags"]["irrigated_rice"] is True


def test_adopted_practices_are_carried():
    practices = _farm_context(_api(_contract_payload()))["practices_adopted"]
    assert {"no_till", "mulching", "cover_crops", "awd"} <= set(practices)
    assert "placed_fertiliser" not in practices   # broadcast


def test_none_fertiliser_rows_do_not_assert_uses_fertilizers():
    api = _api(FRONTEND_FARM_PAYLOAD)
    api["management_practices"]["fertilization"]["fertilizer_applications"][0]["fertilizer_type"] = "None"
    assert _farm_context(api)["flags"]["uses_fertilizers"] is False
