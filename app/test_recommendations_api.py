"""
Integration test for GET /assess/{id}/recommendations.

Reuses the in-memory-DB pattern from test_auth_workspace: it inserts a saved farm
assessment (with the hotspot fields the recommender reads) directly through the store,
then hits the endpoint as its owner. The recommendation pipeline itself is deterministic
and covered in engine/recommend; this proves the HTTP wiring, ownership scoping, and the
serialized shape.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from db import Base, get_db
from models import AssessmentType, User
from store import save_assessment

_engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
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


def _signup(client, email, role="farmer"):
    return client.post("/auth/signup", json={
        "email": email, "password": "password123", "full_name": "T", "role": role,
    })


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def _ghana_farm_payload():
    """Minimal AssessmentResponse-shaped payload with the hotspot fields the recommender
    reads (Ghana maize, urea-dominated)."""
    return {
        "id": None,
        "company_name": "Tamale Agro",
        "country": "Ghana",
        "assessment_date": "2026-07-16T00:00:00",
        "midpoint_impacts": {"Climate change": 1.0},
        "endpoint_impacts": {"Human Health": 0.1},
        "single_score": {"value": 0.5, "unit": "pt", "uncertainty_range": [0.4, 0.6],
                         "weighting_factors": {}, "methodology": "RegionalPriorities"},
        "data_quality": {"confidence_level": "Medium"},
        "breakdown_by_food": {"maize (2000kg)": {"Climate change": 1.0}},
        "input_matches": [
            {"input": "Urea 46-0-0 fertiliser", "kind": "fertiliser", "matched": "urea"},
            {"input": "diesel, burned in agricultural machinery", "kind": "fuel", "matched": "d"},
        ],
        "contribution_by_source": {
            "Urea 46-0-0 fertiliser": {"Climate change": {"value": 0.6, "unit": "kg CO2-eq"}},
            "diesel, burned in agricultural machinery": {"Climate change": {"value": 0.4, "unit": "kg CO2-eq"}},
        },
        "iso_report": {"interpretation": {"contribution_analysis": {"by_source": [
            {"source": "Urea 46-0-0 fertiliser", "per_kg": 0.6, "share": 0.6},
            {"source": "diesel, burned in agricultural machinery", "per_kg": 0.4, "share": 0.4},
        ]}}},
    }


def _make_assessment(email, client):
    token = _signup(client, email).json()["access_token"]
    db = _TestSession()
    try:
        user = db.query(User).filter(User.email == email).one()
        a = save_assessment(
            db, user_id=user.id, a_type=AssessmentType.farm, payload=_ghana_farm_payload(),
            request_payload={"api": {"farm_profile": {"total_farm_size": 4.2},
                                     "management_practices": {"fertilization": {"uses_fertilizers": True}}}},
        )
        return token, a.id
    finally:
        db.close()


def test_recommendations_returns_costed_sequenced_plan(client):
    token, aid = _make_assessment("farmer@example.com", client)
    resp = client.get(f"/assess/{aid}/recommendations", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # shape
    assert body["assessment_id"] == aid
    assert "revenue" in body and "plan" in body and "measures" in body
    # The library was team-approved on go-live and the endpoint defaults to reviewed_only,
    # so every surfaced measure is signed off: no pending-review banner, no draft measures.
    assert body["pending_review"] is False
    assert isinstance(body["disclaimer"], str)

    # a urea-dominated Ghana maize farm surfaces nitrogen measures targeting the urea hotspot
    ids = [m["id"] for m in body["measures"]]
    assert any(mid.startswith("meas.n.") for mid in ids), ids
    top = body["measures"][0]
    assert top["targets_source"] == "Urea 46-0-0 fertiliser"
    assert top["provenance"]["source"], "measure missing provenance source"
    assert top["reviewed"] is True, "reviewed_only endpoint surfaced a draft measure"
    assert all(m["reviewed"] for m in body["measures"]), "an unreviewed measure leaked"

    # the plan is phased, and every measure lands in exactly one phase
    phases = body["plan"]["phases"]
    keys = [p["key"] for p in phases]
    assert keys == [k for k in ["start_now", "this_year", "plan_ahead"] if k in keys]
    assert sum(len(p["measures"]) for p in phases) == len(body["measures"])


def test_recommendations_owner_scoped(client):
    _, aid = _make_assessment("owner@example.com", client)
    intruder = _signup(client, "intruder@example.com").json()["access_token"]
    resp = client.get(f"/assess/{aid}/recommendations", headers=_auth(intruder))
    assert resp.status_code == 404  # not-owned looks identical to not-found (no leak)


def test_recommendations_requires_auth(client):
    _, aid = _make_assessment("owner2@example.com", client)
    assert client.get(f"/assess/{aid}/recommendations").status_code == 401
