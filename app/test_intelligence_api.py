"""Tests for the intelligence endpoints (/classify, /reports/narrative). Fake model only."""
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from db import Base, get_db

_engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
_TestSession = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


def _override_get_db():
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _fresh(tmp_path, monkeypatch):
    Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)
    main.app.dependency_overrides[get_db] = _override_get_db
    monkeypatch.setenv("GMG_LLM_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("GMG_LLM", raising=False)
    for mod in ("engine.llm.classify", "engine.llm.adjudicate", "engine.llm.client",
                "services.ai_report_generator"):
        if mod in sys.modules:
            monkeypatch.setattr(sys.modules[mod], "get_client", lambda: None)
    yield
    main.app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(main.app, base_url="http://localhost")


def _token(client):
    r = client.post("/auth/signup", json={"email": "f@example.com", "password": "password123",
                                          "full_name": "Farmer", "role": "researcher"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_classify_requires_auth(client):
    assert client.post("/classify", json={"kind": "fuel", "text": "AGO"}).status_code == 401


def test_classify_deterministic(client):
    h = _token(client)
    r = client.post("/classify", json={"kind": "fuel", "text": "AGO"}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["label"] == "diesel" and body["needs_confirmation"] is False
    assert body["suggestion_prompt"] is None


def test_classify_model_suggestion_and_unknown(client, monkeypatch):
    from engine.llm.fakes import FakeLLM
    fake = FakeLLM({"label": "millet", "confidence": 0.6, "reason": "fonio is a millet"})
    monkeypatch.setattr(sys.modules["engine.llm.classify"], "get_client", lambda: fake)
    h = _token(client)
    body = client.post("/classify", json={"kind": "crop", "text": "fonio"}, headers=h).json()
    assert body["label"] == "millet" and body["needs_confirmation"] is True
    assert body["suggestion_prompt"] == "Did you mean 'millet'?"
    monkeypatch.setattr(sys.modules["engine.llm.classify"], "get_client", lambda: None)
    body = client.post("/classify", json={"kind": "crop", "text": "zzz unknown"}, headers=h).json()
    assert body["label"] is None and body["needs_confirmation"] is True and body["suggestion_prompt"]


def test_classify_batch_and_vocabulary(client):
    h = _token(client)
    r = client.post("/classify/batch", json={"items": [{"kind": "fuel", "text": "PMS"},
                                                       {"kind": "packaging", "text": "jute sack"}]},
                    headers=h)
    assert [x["label"] for x in r.json()] == ["petrol", "Jute"]
    v = client.get("/classify/vocabulary/fertiliser").json()
    assert "Urea" in v["labels"]
    assert client.post("/classify", json={"kind": "spaceship", "text": "x"}, headers=h).status_code == 422


def test_narrative_endpoint_template_and_missing_iso(client, monkeypatch):
    monkeypatch.setenv("GMG_LLM", "0")
    h = _token(client)
    data = {"single_score": {"value": 412.73, "unit": "uPt per kg", "band": "medium"},
            "midpoint_impacts": {"Climate change": {"value": 0.8421, "unit": "kg CO2-eq"}},
            "iso_report": {"scope": {"functional_unit": "1 kg maize"}}}
    r = client.post("/reports/narrative", json={"style": "plain", "assessment_data": data}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["fallback"] is True and "412.7" in body["text"]
    r = client.post("/reports/narrative", json={"assessment_data": {"x": 1}}, headers=h)
    assert r.status_code == 400
    assert client.post("/reports/narrative", json={}, headers=h).status_code == 404


def test_health_does_not_leak_key(client):
    body = client.get("/intelligence/health").json()
    assert "key" not in " ".join(str(v) for v in body.values()).lower()
