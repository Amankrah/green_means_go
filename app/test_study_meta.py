"""Tests for study_meta persistence on save and research export."""
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

_STUDY_META = {
    "crop_year": 2025,
    "season": "WetSeason",
    "admin_region": "Northern Region",
}


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


def test_study_meta_persisted_on_save_and_export(client):
    token = _signup(client, "meta@example.com").json()["access_token"]
    db = _TestSession()
    try:
        user = db.query(User).filter(User.email == "meta@example.com").one()
        payload = {
            "company_name": "Tamale Agro",
            "country": "Ghana",
            "study_meta": _STUDY_META,
            "midpoint_impacts": {},
            "single_score": {"value": 1.0, "unit": "µPt per kg"},
        }
        a = save_assessment(
            db,
            user_id=user.id,
            a_type=AssessmentType.farm,
            payload=payload,
            request_payload={
                "api": {"company_name": "Tamale Agro", "study_meta": _STUDY_META},
                "form": {},
            },
        )
        aid = a.id
    finally:
        db.close()

    req = client.get(f"/me/assessments/{aid}/request", headers=_auth(token))
    assert req.status_code == 200
    assert req.json()["api"]["study_meta"] == _STUDY_META

    export = client.get(f"/me/assessments/{aid}/export.json", headers=_auth(token))
    assert export.status_code == 200
    assert export.json()["study_meta"] == _STUDY_META
