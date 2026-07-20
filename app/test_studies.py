"""Tests for study cohort CRUD, ownership, and batch re-run."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from db import Base, get_db
from models import AssessmentType, User
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


def _minimal_payload(aid: str | None = None):
    return {
        "id": aid,
        "company_name": "Tamale Agro",
        "country": "Ghana",
        "region": "GH",
        "assessment_date": "2026-07-19T00:00:00",
        "midpoint_impacts": {"Global warming": 1.0},
        "endpoint_impacts": {},
        "single_score": {
            "value": 1.0,
            "unit": "pt",
            "uncertainty_range": [0.7, 1.4],
            "weighting_factors": {},
            "methodology": "test",
        },
        "data_quality": {"overall_confidence": "Medium"},
        "breakdown_by_food": {},
    }


def _seed_assessment(email: str, *, with_request: bool = True):
    db = _TestSession()
    try:
        user = db.query(User).filter(User.email == email).one()
        req = {
            "api": {
                "company_name": "Tamale Agro",
                "country": "Ghana",
                "region": "GH",
                "foods": [{
                    "id": "1",
                    "name": "Maize",
                    "quantity_kg": 3000,
                    "category": "Cereals",
                    "area_allocated": 2.0,
                }],
            },
            "form": None,
        }
        a = save_assessment(
            db,
            user_id=user.id,
            a_type=AssessmentType.farm,
            payload=_minimal_payload(),
            request_payload=req if with_request else None,
        )
        return user, a.id
    finally:
        db.close()


def test_study_crud(client):
    token = _signup(client, "crud@example.com").json()["access_token"]
    _, aid = _seed_assessment("crud@example.com")

    create = client.post(
        "/studies",
        headers=_auth(token),
        json={"title": "Northern Ghana 2026", "assessment_ids": [aid]},
    )
    assert create.status_code == 201, create.text
    body = create.json()
    study_id = body["id"]
    assert body["title"] == "Northern Ghana 2026"
    assert body["assessment_ids"] == [aid]

    listed = client.get("/studies", headers=_auth(token)).json()
    assert len(listed) == 1
    assert listed[0]["id"] == study_id

    got = client.get(f"/studies/{study_id}", headers=_auth(token))
    assert got.status_code == 200

    patched = client.patch(
        f"/studies/{study_id}",
        headers=_auth(token),
        json={"title": "Renamed cohort"},
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "Renamed cohort"

    deleted = client.delete(f"/studies/{study_id}", headers=_auth(token))
    assert deleted.status_code == 204
    assert client.get(f"/studies/{study_id}", headers=_auth(token)).status_code == 404


def test_study_non_owner_gets_404(client):
    owner_token = _signup(client, "owner@example.com").json()["access_token"]
    other_token = _signup(client, "other@example.com").json()["access_token"]
    _, aid = _seed_assessment("owner@example.com")

    study_id = client.post(
        "/studies",
        headers=_auth(owner_token),
        json={"title": "Private cohort", "assessment_ids": [aid]},
    ).json()["id"]

    assert client.get(f"/studies/{study_id}", headers=_auth(other_token)).status_code == 404
    assert client.patch(
        f"/studies/{study_id}",
        headers=_auth(other_token),
        json={"title": "Hijack"},
    ).status_code == 404
    assert client.delete(f"/studies/{study_id}", headers=_auth(other_token)).status_code == 404


def test_study_cannot_reference_foreign_assessment(client):
    owner_token = _signup(client, "own2@example.com").json()["access_token"]
    _signup(client, "oth2@example.com")
    _, foreign_aid = _seed_assessment("oth2@example.com")

    resp = client.post(
        "/studies",
        headers=_auth(owner_token),
        json={"title": "Bad refs", "assessment_ids": [foreign_aid]},
    )
    assert resp.status_code == 404


@patch("studies.routes._run_farm_engine", new_callable=AsyncMock)
def test_study_batch_rerun_isolates_failures(mock_run, client):
    token = _signup(client, "batch@example.com").json()["access_token"]
    _, ok1 = _seed_assessment("batch@example.com")
    _, ok2 = _seed_assessment("batch@example.com")
    _, bad = _seed_assessment("batch@example.com", with_request=False)

    mock_run.side_effect = [
        {**_minimal_payload(), "single_score": {"value": 2.0, "unit": "pt",
                                               "uncertainty_range": [1.0, 3.0],
                                               "weighting_factors": {}, "methodology": "test"}},
        RuntimeError("engine blew up"),
    ]

    study_id = client.post(
        "/studies",
        headers=_auth(token),
        json={"title": "Batch", "assessment_ids": [ok1, bad, ok2]},
    ).json()["id"]

    resp = client.post(f"/studies/{study_id}/rerun", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["succeeded"] == 1
    assert data["failed"] == 2
    assert len(data["results"]) == 3

    statuses = {r["assessment_id"]: r["status"] for r in data["results"]}
    assert statuses[ok1] == "ok"
    assert statuses[ok2] == "error"
    assert statuses[bad] == "error"
    assert mock_run.await_count == 2
