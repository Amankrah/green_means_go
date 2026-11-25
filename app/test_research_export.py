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
            "functional_units": {"per_kg": {"total_kg": 1000.0}},
            "lcia_method": "ReCiPe 2016 v1.03, midpoint (H)",
            "engine_inventory": {
                "n2o-uid": {"name": "Dinitrogen monoxide", "unit": "kg", "amount": 2.0,
                            "compartment": "Emission to air/unspecified", "cas": "10024-97-2"},
                "co2-uid": {"name": "Carbon dioxide, fossil", "unit": "kg", "amount": 300.0,
                            "compartment": "Emission to air/low population density", "cas": "124-38-9"},
            },
            "engine_inventory_by_source": {
                "Field emissions (on-farm)": {"n2o-uid": {"name": "N2O", "unit": "kg", "amount": 2.0}},
                "Urea": {"co2-uid": {"name": "Carbon dioxide, fossil", "unit": "kg", "amount": 300.0}},
            },
        }
        payload["input_matches"][0].update({"uid": "urea-proc-uid", "ref_unit": "kg", "solve_amount": 46.0})
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


def test_export_full_inventory_per_fu_and_brightway(client):
    token, aid = _seed("inv@example.com", client)
    body = client.get(f"/me/assessments/{aid}/export.json", headers=_auth(token)).json()
    inv = body["inventory_per_fu"]
    assert inv["total_kg"] == 1000.0 and inv["n_flows"] == 2
    n2o = next(f for f in inv["flows"] if f["uuid"] == "n2o-uid")
    assert n2o["compartment"] == "Emission to air/unspecified" and n2o["cas"] == "10024-97-2"
    assert n2o["amount_per_fu"] == pytest.approx(0.002)

    bw = body["brightway"]
    act = bw["data"][0]
    assert act["database"] == f"gmg_{aid}" and act["code"] == aid
    types = [e["type"] for e in act["exchanges"]]
    assert types.count("production") == 1
    bio = [e for e in act["exchanges"] if e["type"] == "biosphere"]
    # only the on-site (field) source is a foreground biosphere exchange; the matched input's
    # background flows are represented by the technosphere link, not duplicated.
    assert [e["input"] for e in bio] == [["biosphere3", "n2o-uid"]]
    assert bio[0]["categories"] == ["air", "unspecified"] and bio[0]["amount"] == pytest.approx(0.002)
    tech = [e for e in act["exchanges"] if e["type"] == "technosphere"]
    assert tech[0]["input"] == ["ecoinvent-3.11-cutoff", "urea-proc-uid"]
    assert tech[0]["amount"] == pytest.approx(0.046)


def test_export_csv_inventory_and_brightway_sections(client):
    token, aid = _seed("inv2@example.com", client)
    inv = client.get(f"/me/assessments/{aid}/export.csv?section=inventory", headers=_auth(token))
    assert inv.status_code == 200
    assert inv.text.splitlines()[0] == "uuid,name,compartment,cas,unit,amount_per_fu,amount_total"
    assert "124-38-9" in inv.text
    bw = client.get(f"/me/assessments/{aid}/export.csv?section=brightway", headers=_auth(token))
    assert bw.status_code == 200
    assert "biosphere,Dinitrogen monoxide,air::unspecified" in bw.text
    assert "urea-proc-uid" in bw.text


def test_export_json_has_provenance_and_method(client):
    token, aid = _seed("prov@example.com", client)
    resp = client.get(f"/me/assessments/{aid}/export.json", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    # keys are always present (may be null for older payloads) so scripts can rely on them.
    assert "provenance" in body
    assert "lcia_method" in body
