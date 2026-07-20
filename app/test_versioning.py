"""API versioning: /v1 canonical surface, root legacy alias, served OpenAPI schema."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from db import Base, get_db

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


def _signup_body(email):
    return {"email": email, "password": "password123", "full_name": "R", "role": "researcher"}


def test_v1_and_root_both_work(client):
    # Same endpoint reachable at the versioned and legacy paths.
    r_root = client.post("/auth/signup", json=_signup_body("root@example.com"))
    r_v1 = client.post("/v1/auth/signup", json=_signup_body("v1@example.com"))
    assert r_root.status_code in (200, 201), r_root.text
    assert r_v1.status_code in (200, 201), r_v1.text
    assert "access_token" in r_v1.json()


def test_openapi_schema_served_with_v1_paths(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    spec = resp.json()
    paths = spec.get("paths", {})
    # Both surfaces documented.
    assert "/v1/auth/login" in paths
    assert "/auth/login" in paths


def test_operation_ids_are_unique(client):
    """Duplicate operationIds break client codegen; the dual mount must not create any."""
    spec = client.get("/openapi.json").json()
    op_ids = []
    for methods in spec.get("paths", {}).values():
        for op in methods.values():
            if isinstance(op, dict) and "operationId" in op:
                op_ids.append(op["operationId"])
    assert len(op_ids) == len(set(op_ids)), "duplicate operationIds in the OpenAPI schema"
    # The /v1 mount is disambiguated with a v1_ prefix.
    assert any(oid.startswith("v1_") for oid in op_ids)


def test_root_advertises_v1(client):
    body = client.get("/").json()
    assert "v1" in body.get("api_versions", {})
