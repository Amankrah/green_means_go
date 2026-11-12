"""POST /farm/assess rejects honey/apiculture with a clear 422 (engine/commodities.py)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "app"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from farm.routes import router


def test_farm_assess_rejects_honey_with_422():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    r = client.post("/farm/assess", json={
        "region": "GH",
        "assessment": {"company_name": "Bee co", "country": "Ghana",
                       "foods": [{"id": "1", "name": "Raw honey", "quantity_kg": 200,
                                  "category": "Other"}]},
    })
    assert r.status_code == 422
    assert "apiculture" in r.json()["detail"].lower()
