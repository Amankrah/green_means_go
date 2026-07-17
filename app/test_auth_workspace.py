"""
Tests for authentication, role gating, and assessment ownership.

Runs against an isolated in-memory SQLite database (via a get_db override) so it never
touches the dev database or the heavy LCA engine. Assessment rows are inserted directly
through the store helper — the engine itself is exercised in the manual verification
flow, not here.
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

# One shared in-memory database for the test session.
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
    # base_url host must be in main.py's TrustedHostMiddleware allowlist.
    return TestClient(main.app, base_url="http://localhost")


def _signup(client, email, role="farmer", password="password123"):
    resp = client.post("/auth/signup", json={
        "email": email, "password": password, "full_name": "Test User", "role": role,
    })
    return resp


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# --- auth ------------------------------------------------------------------------

def test_signup_returns_tokens_and_user(client):
    resp = _signup(client, "a@example.com")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["user"]["email"] == "a@example.com"
    assert body["user"]["role"] == "farmer"
    assert "password" not in body["user"]


def test_duplicate_email_rejected(client):
    _signup(client, "dup@example.com")
    resp = _signup(client, "dup@example.com")
    assert resp.status_code == 409


def test_login_wrong_password(client):
    _signup(client, "b@example.com", password="password123")
    resp = client.post("/auth/login", json={"email": "b@example.com", "password": "wrong"})
    assert resp.status_code == 401


def test_login_success_and_me(client):
    _signup(client, "c@example.com", password="password123")
    resp = client.post("/auth/login", json={"email": "c@example.com", "password": "password123"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    me = client.get("/auth/me", headers=_auth(token))
    assert me.status_code == 200
    assert me.json()["email"] == "c@example.com"


def test_refresh_issues_new_access_token(client):
    refresh = _signup(client, "d@example.com").json()["refresh_token"]
    resp = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    assert resp.json()["access_token"]
    # a refresh token must not be accepted as an access (bearer) token
    bad = client.get("/auth/me", headers=_auth(refresh))
    assert bad.status_code == 401


def test_protected_route_requires_token(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/assessments").status_code == 401


# --- role gating -----------------------------------------------------------------

def test_role_gating_farms_and_facilities(client):
    farmer = _signup(client, "farmer@example.com", role="farmer").json()["access_token"]
    processor = _signup(client, "proc@example.com", role="processor").json()["access_token"]

    # farmer can manage farms but not facilities
    assert client.get("/farms", headers=_auth(farmer)).status_code == 200
    assert client.get("/facilities", headers=_auth(farmer)).status_code == 403
    # processor can manage facilities but not farms
    assert client.get("/facilities", headers=_auth(processor)).status_code == 200
    assert client.get("/farms", headers=_auth(processor)).status_code == 403


def test_external_agents_cannot_manage_farms_or_facilities(client):
    """Researchers and extension officers run assessments but do not own farm/facility
    registries — those belong to farmers and processors."""
    researcher = _signup(client, "research@example.com", role="researcher").json()["access_token"]
    officer = _signup(client, "officer@example.com", role="extension_officer").json()["access_token"]

    assert client.get("/farms", headers=_auth(researcher)).status_code == 403
    assert client.get("/facilities", headers=_auth(researcher)).status_code == 403
    assert client.get("/farms", headers=_auth(officer)).status_code == 403
    assert client.post("/farms", headers=_auth(officer), json={
        "name": "Client Farm", "country": "Canada", "farmer_name": "Jane Doe",
    }).status_code == 403


def test_researcher_can_reach_both_assessment_types(client):
    """The processing endpoints are role-gated; the farm ones only need a login. Assert a
    researcher is not 403'd by either gate (a 422 here is schema validation, i.e. past it)."""
    researcher = _signup(client, "research2@example.com", role="researcher").json()["access_token"]

    for path in ("/assess", "/processing/assess"):
        resp = client.post(path, headers=_auth(researcher), json={})
        assert resp.status_code != 403, f"{path} rejected researcher: {resp.text}"


def test_farmer_still_cannot_run_processing_assessment(client):
    """Adding the researcher role must not widen anyone else's access."""
    farmer = _signup(client, "farmer2@example.com", role="farmer").json()["access_token"]
    assert client.post("/processing/assess", headers=_auth(farmer), json={}).status_code == 403


# --- assessment ownership --------------------------------------------------------

def _make_assessment_for(email, client):
    """Sign up a user and insert one owned farm assessment; return (token, assessment_id)."""
    token = _signup(client, email).json()["access_token"]
    db = _TestSession()
    try:
        user = db.query(User).filter(User.email == email).one()
        # Minimal but AssessmentResponse-valid payload so GET /assess/{id} round-trips.
        payload = {
            "id": None,
            "company_name": "Acme",
            "country": "Canada",
            "assessment_date": "2026-07-16T00:00:00",
            "midpoint_impacts": {"Global warming": 1.0},
            "endpoint_impacts": {"Human Health": 0.1},
            "single_score": {"value": 0.42, "unit": "pt", "uncertainty_range": [0.3, 0.5],
                             "weighting_factors": {}, "methodology": "RegionalPriorities"},
            "data_quality": {"confidence_level": "Medium"},
            "breakdown_by_food": {"Wheat": {"Global warming": 1.0}},
        }
        a = save_assessment(db, user_id=user.id, a_type=AssessmentType.farm, payload=payload)
        return token, a.id
    finally:
        db.close()


def test_owner_can_read_others_cannot(client):
    token_a, aid = _make_assessment_for("owner@example.com", client)
    token_b = _signup(client, "intruder@example.com").json()["access_token"]

    assert client.get(f"/assess/{aid}", headers=_auth(token_a)).status_code == 200
    # not owned looks exactly like not found
    assert client.get(f"/assess/{aid}", headers=_auth(token_b)).status_code == 404


def test_me_assessments_lists_only_own(client):
    token_a, aid = _make_assessment_for("owner2@example.com", client)
    token_b = _signup(client, "other2@example.com").json()["access_token"]

    a_list = client.get("/me/assessments", headers=_auth(token_a)).json()
    assert a_list["total"] == 1
    assert a_list["assessments"][0]["id"] == aid
    assert a_list["assessments"][0]["single_score"] == pytest.approx(0.42)

    b_list = client.get("/me/assessments", headers=_auth(token_b)).json()
    assert b_list["total"] == 0


def test_owner_can_delete_others_cannot(client):
    token_a, aid = _make_assessment_for("del-owner@example.com", client)
    token_b = _signup(client, "del-intruder@example.com").json()["access_token"]

    # Not owned looks like not found
    assert client.delete(f"/me/assessments/{aid}", headers=_auth(token_b)).status_code == 404
    # Owner deletes
    assert client.delete(f"/me/assessments/{aid}", headers=_auth(token_a)).status_code == 204
    # Gone for owner too
    assert client.get(f"/assess/{aid}", headers=_auth(token_a)).status_code == 404
    assert client.delete(f"/me/assessments/{aid}", headers=_auth(token_a)).status_code == 404
