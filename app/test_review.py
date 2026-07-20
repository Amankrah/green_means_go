"""Tests for review checklist status and ISO JSON sync."""
from __future__ import annotations

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


def _signup(client, email):
    return client.post(
        "/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Researcher",
            "role": "researcher",
        },
    )


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _seed_with_iso(client, email: str):
    token = _signup(client, email).json()["access_token"]
    db = _TestSession()
    try:
        user = db.query(User).filter(User.email == email).one()
        payload = {
            "id": None,
            "company_name": "Test Farm",
            "country": "Ghana",
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
            "review_status": "draft",
            "iso_report": {
                "document_control": {"version": "1.0 (draft, pending independent critical review)"},
                "interpretation": {"public_disclosure": "draft disclosure"},
                "critical_review": {"status": "Required, and still to be done."},
                "conformance_status": "draft conformance",
            },
        }
        a = save_assessment(db, user_id=user.id, a_type=AssessmentType.farm, payload=payload)
        return token, a.id
    finally:
        db.close()


def test_review_status_updates_iso_fields(client):
    token, aid = _seed_with_iso(client, "review@example.com")

    resp = client.post(
        f"/assess/{aid}/review",
        headers=_auth(token),
        json={"review_status": "reviewed_pending_external"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["review_status"] == "reviewed_pending_external"
    iso = body["iso_report"]
    assert iso["document_control"]["review_status"] == "reviewed_pending_external"
    assert "pending external panel" in iso["document_control"]["version"].lower()
    assert "Internal review complete" in iso["critical_review"]["status"]
    assert "reviewed-pending-external" in iso["interpretation"]["public_disclosure"]
