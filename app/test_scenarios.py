"""Tests for scenario compare (clone → patch → re-solve → delta)."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from db import Base, get_db
from models import AssessmentType, User
from scenarios import ScenarioPatch, apply_scenario_patch, compute_scenario_deltas
from store import save_assessment

_ROOT = Path(__file__).resolve().parents[1]
_CASE = _ROOT / "engine" / "case_studies" / "ghana_maize_cowpea_intercrop.json"

_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSession = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


def _override_get_db():
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _fresh_db():
    Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)
    main.app.dependency_overrides[get_db] = _override_get_db
    yield
    main.app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(main.app, base_url="http://localhost")


def _signup(client, email, role="researcher"):
    return client.post(
        "/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Researcher",
            "role": role,
        },
    )


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _baseline_payload():
    return {
        "company_name": "Tamale Agro",
        "country": "Ghana",
        "region": "GH",
        "assessment_date": "2026-07-19T00:00:00",
        "midpoint_impacts": {
            "Global warming": {"value": 1.2, "unit": "kg CO2-eq per kg"},
            "Land use": {"value": 9.655172413793103, "unit": "m2a crop-eq per kg"},
        },
        "endpoint_impacts": {},
        "single_score": {
            "value": 1000.0,
            "unit": "µPt per kg",
            "methodology": "test",
            "uncertainty_range": [700.0, 1400.0],
            "weighting_factors": {},
        },
        "data_quality": {"notes": []},
        "breakdown_by_food": {},
    }


def _seed_with_request(client, email="scen@example.com"):
    token = _signup(client, email).json()["access_token"]
    case = json.loads(_CASE.read_text(encoding="utf-8"))
    db = _TestSession()
    try:
        user = db.query(User).filter(User.email == email).one()
        a = save_assessment(
            db,
            user_id=user.id,
            a_type=AssessmentType.farm,
            payload=_baseline_payload(),
            title="Ghana baseline",
            request_payload={"api": case, "form": {}},
        )
        return token, a.id, case
    finally:
        db.close()


def test_apply_yield_scale_raises_quantity():
    api = {"foods": [{"name": "Maize", "quantity_kg": 100.0}]}
    out = apply_scenario_patch(api, ScenarioPatch(yield_scale=1.2))
    assert out["foods"][0]["quantity_kg"] == pytest.approx(120.0)
    assert api["foods"][0]["quantity_kg"] == 100.0  # deep copy


def test_apply_patch_requires_scale():
    with pytest.raises(ValueError):
        apply_scenario_patch({"foods": []}, ScenarioPatch())


def test_scenario_patch_empty_422(client):
    token, aid, _ = _seed_with_request(client)
    r = client.post(f"/assess/{aid}/scenarios", headers=_auth(token), json={})
    assert r.status_code == 422


def test_scenario_ownership_404(client):
    token, aid, _ = _seed_with_request(client, "owner-scen@example.com")
    other = _signup(client, "intruder-scen@example.com").json()["access_token"]
    r = client.post(
        f"/assess/{aid}/scenarios",
        headers=_auth(other),
        json={"yield_scale": 1.2},
    )
    assert r.status_code == 404


def test_yield_plus_20_lowers_land_per_kg(client, monkeypatch):
    """Golden: yield_scale=1.2 lowers land per kg vs baseline (and typically single score)."""
    token, aid, case = _seed_with_request(client, "golden@example.com")

    def fake_run(request):
        # Simulate engine: land per kg scales as 1/yield when area fixed.
        scale = 1.0
        # Infer yield scale from request vs case
        base_kg = sum(f["quantity_kg"] for f in case["foods"])
        new_kg = sum(f.quantity_kg for f in request.foods)
        scale = new_kg / base_kg if base_kg else 1.0
        land = 9.655172413793103 / scale
        climate = 1.2 / scale
        score = 1000.0 / scale
        return {
            "id": "scenario-fake",
            "company_name": request.company_name,
            "country": request.country,
            "assessment_date": "2026-07-19T00:00:00",
            "midpoint_impacts": {
                "Global warming": {"value": climate, "unit": "kg CO2-eq per kg"},
                "Land use": {"value": land, "unit": "m2a crop-eq per kg"},
            },
            "endpoint_impacts": {},
            "single_score": {
                "value": score,
                "unit": "µPt per kg",
                "methodology": "test",
                "uncertainty_range": [score * 0.7, score * 1.4],
                "weighting_factors": {},
            },
            "data_quality": {"notes": []},
            "breakdown_by_food": {},
        }

    import production.routes as prod_routes

    async def _fake_engine(request):
        return fake_run(request)

    monkeypatch.setattr(prod_routes, "_run_farm_engine", _fake_engine)

    r = client.post(
        f"/assess/{aid}/scenarios",
        headers=_auth(token),
        json={"name": "Yield +20%", "yield_scale": 1.2},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["baseline_id"] == aid
    assert body["patch"]["yield_scale"] == pytest.approx(1.2)
    land_delta = body["delta_midpoints"]["Land use"]["value"]
    assert land_delta < 0
    assert body["delta_single_score"] < 0
    assert body["title"].startswith("Scenario:")
    assert body["scenario"]["baseline_assessment_id"] == aid


def test_compute_deltas_math():
    b = _baseline_payload()
    s = copy.deepcopy(b)
    s["midpoint_impacts"]["Land use"]["value"] = 8.0
    s["single_score"]["value"] = 900.0
    d = compute_scenario_deltas(b, s)
    assert d["delta_midpoints"]["Land use"]["value"] == pytest.approx(8.0 - 9.655172413793103)
    assert d["delta_single_score"] == pytest.approx(-100.0)
