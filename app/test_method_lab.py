"""API-level method toggle / recharacterize tests (mocked engine)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from db import Base, get_db
from models import AssessmentType, User
from production.models import SUPPORTED_LCIA_METHODS
from store import save_assessment

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


def _signup(client, email="method@example.com"):
    return client.post(
        "/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Researcher",
            "role": "researcher",
        },
    ).json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_supported_methods():
    assert "ReCiPe 2016 v1.03, midpoint (H)" in SUPPORTED_LCIA_METHODS
    assert "EF v3.1" in SUPPORTED_LCIA_METHODS


def test_recharacterize_caches_variant(client, monkeypatch):
    token = _signup(client)
    db = _TestSession()
    try:
        user = db.query(User).filter(User.email == "method@example.com").one()
        a = save_assessment(
            db,
            user_id=user.id,
            a_type=AssessmentType.farm,
            payload={
                "company_name": "X",
                "country": "Ghana",
                "assessment_date": "2026-07-19T00:00:00",
                "lcia_method": "ReCiPe 2016 v1.03, midpoint (H)",
                "midpoint_impacts": {
                    "Global warming": {"value": 1.0, "unit": "kg CO2-eq per kg"}
                },
                "endpoint_impacts": {},
                "single_score": {
                    "value": 10.0,
                    "unit": "µPt per kg",
                    "methodology": "ReCiPe",
                    "uncertainty_range": [7.0, 14.0],
                    "weighting_factors": {},
                },
                "data_quality": {"notes": []},
                "breakdown_by_food": {},
                "engine_inventory": {"flow-1": {"name": "CO2", "unit": "kg", "amount": 1.0}},
            },
            request_payload={
                "api": {
                    "company_name": "X",
                    "country": "Ghana",
                    "region": "GH",
                    "foods": [
                        {
                            "id": "1",
                            "name": "Maize",
                            "quantity_kg": 1000,
                            "category": "Cereals",
                            "area_allocated": 1.0,
                        }
                    ],
                }
            },
        )
        aid = a.id
    finally:
        db.close()

    def fake_rechar(payload, assessment, method, region=None):
        return {
            "id": payload.get("id", "v"),
            "company_name": "X",
            "country": "Ghana",
            "assessment_date": "2026-07-19T00:00:00",
            "lcia_method": method,
            "midpoint_impacts": {
                "Global warming": {
                    "value": 2.0 if method and "EF" in method else 1.0,
                    "unit": "kg CO2-eq per kg",
                }
            },
            "endpoint_impacts": {},
            "single_score": {
                "value": 20.0 if method and "EF" in method else 10.0,
                "unit": "µPt per kg",
                "methodology": method or "default",
                "uncertainty_range": [1.0, 2.0],
                "weighting_factors": {},
            },
            "data_quality": {"notes": []},
            "breakdown_by_food": {},
            "functional_units": {},
        }

    import engine.service as svc

    monkeypatch.setattr(svc, "recharacterize_from_payload", fake_rechar)
    monkeypatch.setattr(
        svc,
        "run_farm_assessment",
        lambda *a, **k: pytest.fail("full re-run should not be called when inventory exists"),
    )

    r = client.post(
        f"/assess/{aid}/recharacterize",
        headers=_auth(token),
        json={"lcia_method": "EF v3.1", "apply_as_primary": False},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "EF v3.1" in (body.get("method_variants") or {})
    # Primary midpoints unchanged when apply_as_primary=False
    assert body["midpoint_impacts"]["Global warming"]["value"] == pytest.approx(1.0)


def test_recharacterize_falls_back_without_inventory(client, monkeypatch):
    token = _signup(client, "fallback@example.com")
    db = _TestSession()
    try:
        user = db.query(User).filter(User.email == "fallback@example.com").one()
        a = save_assessment(
            db,
            user_id=user.id,
            a_type=AssessmentType.farm,
            payload={
                "company_name": "X",
                "country": "Ghana",
                "assessment_date": "2026-07-19T00:00:00",
                "midpoint_impacts": {
                    "Global warming": {"value": 1.0, "unit": "kg CO2-eq per kg"}
                },
                "endpoint_impacts": {},
                "single_score": {
                    "value": 10.0,
                    "unit": "µPt per kg",
                    "methodology": "ReCiPe",
                    "uncertainty_range": [7.0, 14.0],
                    "weighting_factors": {},
                },
                "data_quality": {"notes": []},
                "breakdown_by_food": {},
            },
            request_payload={
                "api": {
                    "company_name": "X",
                    "country": "Ghana",
                    "region": "GH",
                    "foods": [
                        {
                            "id": "1",
                            "name": "Maize",
                            "quantity_kg": 1000,
                            "category": "Cereals",
                            "area_allocated": 1.0,
                        }
                    ],
                }
            },
        )
        aid = a.id
    finally:
        db.close()

    def fake_run(assessment, region=None, method=None, **kwargs):
        return {
            "id": kwargs.get("assessment_id") or "v",
            "company_name": "X",
            "country": "Ghana",
            "assessment_date": "2026-07-19T00:00:00",
            "midpoint_impacts": {
                "Global warming": {"value": 3.0, "unit": "kg CO2-eq per kg"}
            },
            "endpoint_impacts": {},
            "single_score": {
                "value": 30.0,
                "unit": "µPt per kg",
                "methodology": method or "default",
                "uncertainty_range": [1.0, 2.0],
                "weighting_factors": {},
            },
            "data_quality": {"notes": []},
            "breakdown_by_food": {},
            "functional_units": {},
        }

    import engine.service as svc

    monkeypatch.setattr(svc, "recharacterize_from_payload", lambda *a, **k: None)
    monkeypatch.setattr(svc, "run_farm_assessment", fake_run)

    r = client.post(
        f"/assess/{aid}/recharacterize",
        headers=_auth(token),
        json={"lcia_method": "EF v3.1", "apply_as_primary": False},
    )
    assert r.status_code == 200, r.text
    assert r.json()["method_variants"]["EF v3.1"]["midpoint_impacts"]["Global warming"]["value"] == pytest.approx(3.0)


def test_bad_method_422(client):
    token = _signup(client, "badm@example.com")
    db = _TestSession()
    try:
        user = db.query(User).filter(User.email == "badm@example.com").one()
        a = save_assessment(
            db,
            user_id=user.id,
            a_type=AssessmentType.farm,
            payload={
                "company_name": "X",
                "country": "Ghana",
                "assessment_date": "2026-07-19T00:00:00",
                "midpoint_impacts": {},
                "endpoint_impacts": {},
                "single_score": {
                    "value": 1.0,
                    "unit": "u",
                    "methodology": "x",
                    "uncertainty_range": [1, 2],
                    "weighting_factors": {},
                },
                "data_quality": {"notes": []},
                "breakdown_by_food": {},
            },
            request_payload={"api": {"company_name": "X", "country": "Ghana", "foods": []}},
        )
        aid = a.id
    finally:
        db.close()
    r = client.post(
        f"/assess/{aid}/recharacterize",
        headers=_auth(token),
        json={"lcia_method": "Not A Method"},
    )
    assert r.status_code == 422
