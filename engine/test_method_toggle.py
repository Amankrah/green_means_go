"""Region default LCIA methods, override plumbing, and inventory recharacterization."""
from __future__ import annotations

import glob
import math
from pathlib import Path

import pytest

from engine.regions import get_region

RECIPE = "ReCiPe 2016 v1.03, midpoint (H)"
EF = "EF v3.1"


def _store() -> str | None:
    hits = glob.glob("data/canonical/*.sqlite") or glob.glob(
        str(Path(__file__).resolve().parents[1] / "data" / "canonical" / "*.sqlite")
    )
    return hits[0] if hits else None


def _climate_value(impacts: dict) -> float | None:
    for cat, v in impacts.items():
        if "climate" in cat.lower():
            return v.get("value")
    return None


def test_ghana_default_recipe():
    assert "ReCiPe" in get_region("GH").default_method


def test_canada_default_ef():
    assert get_region("CA").default_method == EF
    assert get_region("Global").default_method == EF


def test_region_alias_global_is_canada():
    assert get_region("global").code == "CA"


def test_engine_region_default_methods():
    db = _store()
    if not db:
        pytest.skip("canonical store not present")
    from engine.service import _engine

    gh_eng, _ = _engine("GH", None)
    ca_eng, _ = _engine("CA", None)
    assert "ReCiPe" in gh_eng.method
    assert ca_eng.method == EF


def test_same_inventory_recipe_vs_ef_finite_climate():
    db = _store()
    if not db:
        pytest.skip("canonical store not present")
    from ingestion.query import CanonicalQuery

    q = CanonicalQuery(db)
    row = q.conn.execute(
        "SELECT uid FROM processes WHERE name LIKE '%urea%' AND name LIKE '%market%' LIMIT 1"
    ).fetchone()
    if not row:
        pytest.skip("no urea market process in store")
    sc = q.cradle_to_gate(row["uid"], amount=1.0)
    inv = sc.elementary_flows
    assert inv

    recipe = q.characterize_flows(inv, RECIPE)
    ef = q.characterize_flows(inv, EF)
    c_recipe = _climate_value(recipe)
    c_ef = _climate_value(ef)
    assert c_recipe is not None and math.isfinite(c_recipe) and c_recipe > 0
    assert c_ef is not None and math.isfinite(c_ef) and c_ef > 0


def test_recharacterize_from_payload_uses_stored_inventory():
    db = _store()
    if not db:
        pytest.skip("canonical store not present")
    from ingestion.query import CanonicalQuery
    from engine.service import recharacterize_from_payload

    q = CanonicalQuery(db)
    row = q.conn.execute(
        "SELECT uid FROM processes WHERE name LIKE '%urea%' AND name LIKE '%market%' LIMIT 1"
    ).fetchone()
    if not row:
        pytest.skip("no urea market process in store")
    inv = q.cradle_to_gate(row["uid"], amount=2.5).elementary_flows
    assessment = {
        "company_name": "Test",
        "country": "Ghana",
        "region": "GH",
        "foods": [
            {"id": "1", "name": "Maize", "quantity_kg": 1000, "category": "Cereals", "area_allocated": 1.0},
        ],
    }
    payload = {
        "id": "saved-1",
        "engine_inventory": {
            uid: {"name": r.get("name"), "unit": r.get("unit"), "amount": r.get("amount")}
            for uid, r in inv.items()
        },
    }
    out = recharacterize_from_payload(payload, assessment, EF, region="GH")
    assert out is not None
    gwp = out["midpoint_impacts"]["Global warming"]["value"]
    assert math.isfinite(gwp) and gwp > 0
    assert out["lcia_method"] == EF


def test_run_farm_assessment_respects_method_override():
    db = _store()
    if not db:
        pytest.skip("canonical store not present")
    try:
        from engine.rust_kernel import _binary
        if _binary() is None:
            pytest.skip("Rust LCI kernel not built")
    except ImportError:
        pytest.skip("Rust LCI kernel unavailable")

    from engine.service import run_farm_assessment

    assessment = {
        "company_name": "Test",
        "country": "Ghana",
        "region": "GH",
        "foods": [
            {"id": "1", "name": "Maize", "quantity_kg": 1000, "category": "Cereals", "area_allocated": 1.0},
        ],
    }
    default = run_farm_assessment(assessment, region="GH")
    assert default.get("lcia_method") and "ReCiPe" in default["lcia_method"]
    if not default.get("midpoint_impacts"):
        pytest.skip("full farm assessment produced no midpoints in this environment")

    overridden = run_farm_assessment(assessment, region="GH", method=EF)
    assert overridden.get("lcia_method") == EF
    gwp = (overridden.get("midpoint_impacts") or {}).get("Global warming", {}).get("value")
    assert gwp is not None and math.isfinite(gwp) and gwp > 0
    inv = default.get("engine_inventory")
    if inv:
        assert isinstance(inv, dict) and len(inv) > 0
