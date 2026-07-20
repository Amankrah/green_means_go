"""Unit tests for per-kg / per-ha dual functional units in the adapter."""
from __future__ import annotations

import pytest

from engine.adapter import to_assessment_response


class _FakeResult:
    def __init__(self):
        self.impacts = {
            "Land use": {"value": 42000.0, "unit": "m2a crop-eq"},
            "Climate change": {"value": 4350.0, "unit": "kg CO2-eq"},
        }
        self.inventory = {}
        self.contribution = {"on_farm": {}, "supply_chain": {}}
        self.contribution_by_source = {}
        self.input_matches = []
        self.notes = []
        self.method = "ReCiPe 2016 v1.03, midpoint (H)"
        self.region = "Ghana"


class _FakeQ:
    def find_method(self, _name):
        return None


class _FakeEngine:
    method = "ReCiPe 2016 v1.03, midpoint (H)"
    q = _FakeQ()

    def characterize(self, inventory, method):
        return {}


def test_per_ha_equals_per_kg_times_kg_per_ha(monkeypatch):
    def _fake_iso(*_a, **_k):
        return {
            "interpretation": {
                "data_quality_scorecard": {"overall": "Medium", "indicators": {}},
            },
            "inventory_analysis": {"inventory_results": {"basis": "test", "flows": []}},
        }

    import engine.iso_report as iso_mod

    monkeypatch.setattr(iso_mod, "build_iso_report", _fake_iso)

    assessment = {
        "company_name": "Test",
        "country": "Ghana",
        "foods": [
            {"name": "Maize", "quantity_kg": 3500, "area_allocated": 2.5},
            {"name": "Cowpea", "quantity_kg": 850, "area_allocated": 1.7},
        ],
    }
    total_kg = 4350.0
    total_ha = 4.2
    resp = to_assessment_response(
        _FakeResult(), assessment, _FakeEngine(), total_kg, "test-id"
    )
    fu = resp["functional_units"]
    assert fu["per_kg"]["total_kg"] == total_kg
    assert fu["per_ha"]["total_ha"] == total_ha
    land_kg = fu["per_kg"]["midpoint_impacts"]["Land use"]["value"]
    land_ha = fu["per_ha"]["midpoint_impacts"]["Land use"]["value"]
    assert land_kg == pytest.approx(42000.0 / 4350.0, rel=1e-6)
    assert land_kg == pytest.approx(9.655172413793103, rel=1e-6)
    assert land_ha == pytest.approx(land_kg * (total_kg / total_ha), rel=1e-6)
    assert land_ha == pytest.approx(10000.0, rel=1e-6)
    assert "intensity" in (fu.get("land_intensity_note") or "").lower()
