"""Tests for research export JSON/CSV endpoints."""
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
            "region": "GH",
            "assessment_date": "2026-07-19T00:00:00",
            "midpoint_impacts": {
                "Global warming": {"value": 1.2, "unit": "kg CO2-eq per kg"},
                "Land use": {"value": 9.7, "unit": "m2a crop-eq per kg"},
            },
            "endpoint_impacts": {"Human Health": {"value": 1e-6, "unit": "DALY"}},
            "single_score": {
                "value": 1000.0,
                "unit": "µPt per kg",
                "methodology": "ReCiPe test",
                "uncertainty_range": [700.0, 1400.0],
                "weighting_factors": {},
            },
            "input_matches": [
                {
                    "input": "Urea",
                    "amount": 100.0,
                    "amount_unit": "kg",
                    "matched": "Urea, as N {RoW}",
                    "score": 0.7,
                    "estimated": True,
                    "kind": "fertiliser",
                }
            ],
            "contribution_by_source": {
                "Urea": {"Global warming": {"value": 0.3, "unit": "kg CO2-eq"}},
                "Field emissions (on-farm)": {
                    "Land use": {"value": 9.0, "unit": "m2a crop-eq"}
                },
            },
            "data_quality": {"notes": ["screening defaults used"]},
        }
        a = save_assessment(
            db,
            user_id=user.id,
            a_type=AssessmentType.farm,
            payload=payload,
            title="Ghana case",
            request_payload={"api": {"company_name": "Tamale Agro"}, "form": {}},
        )
        return token, a.id
    finally:
        db.close()


def test_export_json_requires_auth(client):
    assert client.get("/me/assessments/x/export.json").status_code == 401


def test_export_json_owner_ok_intruder_404(client):
    token, aid = _seed("exp@example.com", client)
    other = _signup(client, "other-exp@example.com").json()["access_token"]
    assert client.get(f"/me/assessments/{aid}/export.json", headers=_auth(other)).status_code == 404
    resp = client.get(f"/me/assessments/{aid}/export.json", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == aid
    assert "Global warming" in body["midpoint_impacts"]
    assert body["input_matches"][0]["estimated"] is True
    assert body["contribution_by_source"]["Urea"]
    assert body["methodology"] == "ReCiPe test"
    assert body["request_meta"]["has_api"] is True


def test_export_csv_impacts_is_tidy(client):
    """Default section is a single rectangular table: section,category,metric,value,unit."""
    import csv
    import io

    token, aid = _seed("csv@example.com", client)
    resp = client.get(f"/me/assessments/{aid}/export.csv", headers=_auth(token))
    assert resp.status_code == 200
    rows = list(csv.reader(io.StringIO(resp.text)))
    assert rows[0] == ["section", "category", "metric", "value", "unit"]
    # Every data row is rectangular (no stacked "#" section markers, no blank separators).
    assert all(len(r) == 5 for r in rows), rows
    assert not any(r[0].startswith("#") for r in rows)
    body = resp.text
    assert "midpoint,Global warming,value,1.2" in body
    assert "endpoint,Human Health" in body
    assert "single_score,single_score,value,1000.0" in body
    # unit column is populated from the stored value, not defaulted per category.
    assert "kg CO2-eq per kg" in body


def test_export_csv_sections(client):
    token, aid = _seed("csv2@example.com", client)
    matches = client.get(
        f"/me/assessments/{aid}/export.csv?section=matches", headers=_auth(token)
    )
    assert matches.status_code == 200
    assert matches.text.splitlines()[0].startswith("input,amount,amount_unit")
    assert "Urea" in matches.text
    assert "True" in matches.text or "true" in matches.text.lower()

    contrib = client.get(
        f"/me/assessments/{aid}/export.csv?section=contributions", headers=_auth(token)
    )
    assert contrib.status_code == 200
    assert contrib.text.splitlines()[0] == "source,category,value,unit"
    assert "Urea" in contrib.text

    bad = client.get(
        f"/me/assessments/{aid}/export.csv?section=nope", headers=_auth(token)
    )
    assert bad.status_code == 422


def test_export_json_has_provenance_and_method(client):
    token, aid = _seed("prov@example.com", client)
    resp = client.get(f"/me/assessments/{aid}/export.json", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    # keys are always present (may be null for older payloads) so scripts can rely on them.
    assert "provenance" in body
    assert "lcia_method" in body
