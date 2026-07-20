"""Tests for read-only share links."""
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


def _seed(email, client):
    token = _signup(client, email).json()["access_token"]
    db = _TestSession()
    try:
        user = db.query(User).filter(User.email == email).one()
        payload = {
            "company_name": "Tamale Agro",
            "country": "Ghana",
            "midpoint_impacts": {"Global warming": {"value": 1.2, "unit": "kg CO2-eq per kg"}},
            "single_score": {"value": 1000.0, "unit": "µPt per kg"},
        }
        a = save_assessment(
            db,
            user_id=user.id,
            a_type=AssessmentType.farm,
            payload=payload,
            title="Share test",
        )
        return token, a.id
    finally:
        db.close()


def test_share_token_returns_read_only_payload_without_auth(client):
    token, aid = _seed("share@example.com", client)
    create = client.post(f"/me/assessments/{aid}/share", headers=_auth(token))
    assert create.status_code == 200, create.text
    share_token = create.json()["token"]

    resp = client.get(f"/share/{share_token}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["read_only"] is True
    assert body["id"] == aid
    assert body["assessment"]["company_name"] == "Tamale Agro"


def test_share_route_does_not_allow_writes(client):
    token, aid = _seed("share-write@example.com", client)
    share_token = client.post(
        f"/me/assessments/{aid}/share", headers=_auth(token)
    ).json()["token"]

    assert client.post(f"/share/{share_token}").status_code == 405
    assert client.delete(f"/share/{share_token}").status_code == 405
    assert client.patch(f"/share/{share_token}", json={"title": "hacked"}).status_code == 405


def test_share_create_requires_owner(client):
    token, aid = _seed("share-owner@example.com", client)
    other = _signup(client, "share-other@example.com").json()["access_token"]
    assert client.post(f"/me/assessments/{aid}/share", headers=_auth(other)).status_code == 404
