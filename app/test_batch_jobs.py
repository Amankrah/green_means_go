"""Async batch re-run jobs + cohort CSV export."""
from __future__ import annotations

import csv
import io
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
import studies.routes as studies_routes
from db import Base, get_db
from models import AssessmentType, User
from store import save_assessment

_engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
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
    # The background worker opens its OWN session; point it at the test database.
    _orig = studies_routes.job_session_factory
    studies_routes.job_session_factory = _TestSession
    yield
    studies_routes.job_session_factory = _orig
    main.app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(main.app, base_url="http://localhost")


def _signup(client, email):
    return client.post(
        "/auth/signup",
        json={"email": email, "password": "password123", "full_name": "R", "role": "researcher"},
    ).json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _payload(score=1.0):
    return {
        "company_name": "Tamale Agro", "country": "Ghana", "region": "GH",
        "assessment_date": "2026-07-19T00:00:00",
        "midpoint_impacts": {"Global warming": {"value": score, "unit": "kg CO2-eq per kg"}},
        "endpoint_impacts": {},
        "single_score": {"value": score, "unit": "µPt per kg", "uncertainty_range": [0.7, 1.4],
                         "weighting_factors": {}, "methodology": "test"},
        "lcia_method": "ReCiPe 2016 v1.03, midpoint (H)",
        "data_quality": {}, "breakdown_by_food": {},
    }


def _seed_assessment(email, *, with_request=True):
    db = _TestSession()
    try:
        user = db.query(User).filter(User.email == email).one()
        req = {"api": {"company_name": "Tamale Agro", "country": "Ghana", "region": "GH",
                       "foods": [{"id": "1", "name": "Maize", "quantity_kg": 3000,
                                  "category": "Cereals", "area_allocated": 2.0}]}, "form": None}
        a = save_assessment(db, user_id=user.id, a_type=AssessmentType.farm,
                            payload=_payload(), request_payload=req if with_request else None)
        return a.id
    finally:
        db.close()


@patch("studies.routes._run_farm_engine", new_callable=AsyncMock)
def test_async_batch_run_completes_and_isolates_failures(mock_run, client):
    token = _signup(client, "job@example.com")
    ok = _seed_assessment("job@example.com")
    bad = _seed_assessment("job@example.com", with_request=False)
    mock_run.return_value = _payload(2.0)

    study_id = client.post(
        "/studies", headers=_auth(token),
        json={"title": "Cohort", "assessment_ids": [ok, bad]},
    ).json()["id"]

    # Submit returns 202 immediately with a job handle.
    sub = client.post(f"/v1/studies/{study_id}/runs", headers=_auth(token))
    assert sub.status_code == 202, sub.text
    job = sub.json()
    assert job["total"] == 2
    job_id = job["id"]

    # TestClient runs the background task synchronously, so by now the job has finished.
    poll = client.get(f"/studies/{study_id}/runs/{job_id}", headers=_auth(token))
    assert poll.status_code == 200, poll.text
    done = poll.json()
    assert done["status"] == "completed"
    assert done["succeeded"] == 1
    assert done["failed"] == 1
    statuses = {r["assessment_id"]: r["status"] for r in done["results_json"]}
    assert statuses[ok] == "ok"
    assert statuses[bad] == "error"


def test_batch_job_ownership_scoped(client):
    token = _signup(client, "owner@example.com")
    aid = _seed_assessment("owner@example.com")
    study_id = client.post(
        "/studies", headers=_auth(token), json={"title": "S", "assessment_ids": [aid]}
    ).json()["id"]
    with patch("studies.routes._run_farm_engine", new_callable=AsyncMock) as m:
        m.return_value = _payload(2.0)
        job_id = client.post(f"/studies/{study_id}/runs", headers=_auth(token)).json()["id"]

    other = _signup(client, "intruder@example.com")
    r = client.get(f"/studies/{study_id}/runs/{job_id}", headers=_auth(other))
    assert r.status_code == 404


def test_cohort_export_csv_is_tidy(client):
    token = _signup(client, "cohort@example.com")
    a1 = _seed_assessment("cohort@example.com")
    a2 = _seed_assessment("cohort@example.com")
    study_id = client.post(
        "/studies", headers=_auth(token), json={"title": "Cohort", "assessment_ids": [a1, a2]}
    ).json()["id"]

    resp = client.get(f"/v1/studies/{study_id}/export.csv", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    rows = list(csv.reader(io.StringIO(resp.text)))
    assert rows[0] == ["assessment_id", "title", "section", "category", "metric", "value", "unit"]
    assert all(len(r) == 7 for r in rows)
    body_ids = {r[0] for r in rows[1:]}
    assert a1 in body_ids and a2 in body_ids  # both assessments represented
    assert any(r[2] == "midpoint" and r[3] == "Global warming" for r in rows[1:])
