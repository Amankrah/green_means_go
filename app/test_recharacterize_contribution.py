"""Unit tests for engine.service.recharacterize_from_payload.

Regression guard for the method-toggle bug: recharacterizing a saved assessment must
rebuild contribution_by_source (and thus Top sources + pedigree MC) for the NEW method
from the stored per-source flows, and must fall back (return None) when those flows are
absent so the route can do a full re-solve instead of emitting zeroed uncertainty.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine import service  # noqa: E402


class _FakeQuery:
    """Deterministic characterization: GWP = sum(flow amounts) * a per-method factor."""

    def __init__(self, factor: float):
        self.factor = factor

    def characterize_flows(self, flows: dict, method: str) -> dict:
        total = sum((r.get("amount") or 0.0) for r in (flows or {}).values())
        return {"Climate change": {"value": total * self.factor, "unit": "kg CO2-eq"}}


class _FakeRegion:
    name = "Ghana"


class _FakeEngine:
    def __init__(self, factor: float):
        self.q = _FakeQuery(factor)
        self.region = _FakeRegion()
        self.method = "EF v3.1"


class _NoLock:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _patch_engine(monkeypatch, factor: float = 2.0):
    eng = _FakeEngine(factor)
    monkeypatch.setattr(service, "_engine", lambda region_code, method: (eng, _NoLock()))
    monkeypatch.setattr(service, "total_production_kg", lambda assessment: 100.0)
    # Skip the real MC/ISO machinery; assert on the AssessmentResult passed into the adapter.
    captured = {}

    def _fake_to_response(res, assessment, eng, total, aid, *a, **k):
        captured["res"] = res
        return {"id": aid, "midpoint_impacts": {}, "single_score": {}}

    monkeypatch.setattr(service, "to_assessment_response", _fake_to_response)
    return captured


def test_recharacterize_rebuilds_contribution_from_per_source_flows(monkeypatch):
    captured = _patch_engine(monkeypatch, factor=2.0)
    payload = {
        "id": "a1",
        "engine_inventory": {"co2": {"name": "CO2", "unit": "kg", "amount": 5.0}},
        "engine_inventory_by_source": {
            "Field emissions (on-farm)": {"n2o": {"name": "N2O", "unit": "kg", "amount": 1.0}},
            "urea fertiliser": {"co2": {"name": "CO2", "unit": "kg", "amount": 4.0}},
        },
        "input_matches": [{"input": "urea fertiliser", "matched": "Urea", "estimated": False}],
    }

    out = service.recharacterize_from_payload(payload, {"country": "Ghana"}, "EF v3.1")

    assert out is not None
    res = captured["res"]
    # Every source is re-characterized for the new method (not carried over / zeroed).
    assert set(res.contribution_by_source) == {"Field emissions (on-farm)", "urea fertiliser"}
    assert res.contribution_by_source["urea fertiliser"]["Climate change"]["value"] == 8.0  # 4 * 2
    assert res.contribution_by_source["Field emissions (on-farm)"]["Climate change"]["value"] == 2.0
    # on-farm / supply split rebuilt too.
    assert res.contribution["on_farm"]["Climate change"]["value"] == 2.0
    assert res.contribution["supply_chain"]["Climate change"]["value"] == 8.0
    # per-source flows re-attached so a subsequent switch still works.
    assert "urea fertiliser" in res.contribution_flows_by_source
    assert res.input_matches == payload["input_matches"]


def test_recharacterize_falls_back_without_per_source_flows(monkeypatch):
    _patch_engine(monkeypatch)
    payload = {
        "id": "a2",
        "engine_inventory": {"co2": {"name": "CO2", "unit": "kg", "amount": 5.0}},
        # no engine_inventory_by_source (pre-dates the fix)
    }
    assert service.recharacterize_from_payload(payload, {"country": "Ghana"}, "EF v3.1") is None


def test_recharacterize_none_without_inventory(monkeypatch):
    _patch_engine(monkeypatch)
    assert service.recharacterize_from_payload({"id": "a3"}, {"country": "Ghana"}, "EF v3.1") is None
