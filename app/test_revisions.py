"""Immutable revision history + optimistic locking."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from db import Base, get_db
from models import AssessmentType, User
from store import (
    ConcurrencyError,
    list_revisions,
    replace_assessment,
    save_assessment,
)

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
    yield
    main.app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(main.app, base_url="http://localhost")


def _user(db):
    u = User(email="r@x.com", full_name="R", role="researcher", password_hash="x")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _payload(score, method="ReCiPe 2016 v1.03, midpoint (H)"):
    return {"company_name": "Farm", "country": "Ghana",
            "single_score": {"value": score}, "lcia_method": method}


def test_initial_save_creates_revision_one():
    db = _TestSession()
    try:
        u = _user(db)
        a = save_assessment(db, user_id=u.id, a_type=AssessmentType.farm, payload=_payload(1000.0))
        assert a.version == 1
        assert a.current_revision_id is not None
        revs = list_revisions(db, a)
        assert len(revs) == 1
        assert revs[0].revision_no == 1
        assert revs[0].reason == "initial"
        assert revs[0].single_score == 1000.0
    finally:
        db.close()


def test_replace_appends_revision_and_bumps_version():
    db = _TestSession()
    try:
        u = _user(db)
        a = save_assessment(db, user_id=u.id, a_type=AssessmentType.farm, payload=_payload(1000.0))
        replace_assessment(db, a, payload=_payload(1200.0, "EF v3.1"), reason="recharacterize")
        assert a.version == 2
        revs = list_revisions(db, a)  # newest first
        assert [r.revision_no for r in revs] == [2, 1]
        assert revs[0].reason == "recharacterize"
        assert revs[0].lcia_method == "EF v3.1"
        # The old revision is preserved intact (history is not destroyed).
        assert revs[1].single_score == 1000.0
        assert revs[1].reason == "initial"
    finally:
        db.close()


def test_optimistic_lock_rejects_stale_write():
    db = _TestSession()
    try:
        u = _user(db)
        a = save_assessment(db, user_id=u.id, a_type=AssessmentType.farm, payload=_payload(1000.0))
        # a.version == 1. A stale client thinks it is version 0.
        with pytest.raises(ConcurrencyError):
            replace_assessment(db, a, payload=_payload(1200.0), expected_version=0)
        # Matching version succeeds.
        replace_assessment(db, a, payload=_payload(1200.0), expected_version=1)
        assert a.version == 2
    finally:
        db.close()


def _seed_via_api(client):
    token = client.post(
        "/auth/signup",
        json={"email": "api@x.com", "password": "password123", "full_name": "R", "role": "researcher"},
    ).json()["access_token"]
    db = _TestSession()
    try:
        u = db.query(User).filter(User.email == "api@x.com").one()
        a = save_assessment(db, user_id=u.id, a_type=AssessmentType.farm, payload=_payload(900.0))
        replace_assessment(db, a, payload=_payload(950.0, "EF v3.1"), reason="uncertainty")
        return token, a.id
    finally:
        db.close()


def test_revisions_api_list_and_get(client):
    token, aid = _seed_via_api(client)
    h = {"Authorization": f"Bearer {token}"}

    lst = client.get(f"/v1/me/assessments/{aid}/revisions", headers=h)
    assert lst.status_code == 200, lst.text
    revs = lst.json()
    assert [r["revision_no"] for r in revs] == [2, 1]
    assert revs[0]["reason"] == "uncertainty"

    one = client.get(f"/me/assessments/{aid}/revisions/1", headers=h)
    assert one.status_code == 200
    body = one.json()
    assert body["revision_no"] == 1
    assert body["payload"]["single_score"]["value"] == 900.0

    assert client.get(f"/me/assessments/{aid}/revisions/99", headers=h).status_code == 404


def test_revisions_api_requires_ownership(client):
    _token, aid = _seed_via_api(client)
    other = client.post(
        "/auth/signup",
        json={"email": "other@x.com", "password": "password123", "full_name": "O", "role": "researcher"},
    ).json()["access_token"]
    r = client.get(
        f"/me/assessments/{aid}/revisions", headers={"Authorization": f"Bearer {other}"}
    )
    assert r.status_code == 404
