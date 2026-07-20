"""Pedigree screening Monte Carlo unit tests (CI-fast N=50)."""
from __future__ import annotations

import pytest

from engine.adapter import to_assessment_response
from engine.uncertainty import (
    GSD_BY_CLASS,
    apply_mc_to_midpoints,
    run_pedigree_mc,
    study_gsd,
)


class _FakeResult:
    def __init__(
        self,
        *,
        contribution_by_source=None,
        input_matches=None,
        gwp_per_kg=1.0,
        land_per_kg=10.0,
    ):
        total = 1000.0
        self.impacts = {
            "Climate change": {"value": gwp_per_kg * total, "unit": "kg CO2-eq"},
            "Land use": {"value": land_per_kg * total, "unit": "m2a crop-eq"},
        }
        self.inventory = {}
        self.contribution = {"on_farm": {}, "supply_chain": {}}
        self.contribution_by_source = contribution_by_source or {}
        self.input_matches = input_matches or []
        self.notes = []
        self.method = "ReCiPe 2016 v1.03, midpoint (H)"
        self.region = "Ghana"


class _FakeEngine:
    method = "ReCiPe 2016 v1.03, midpoint (H)"

    class _Q:
        @staticmethod
        def find_method(_name):
            return None

    q = _Q()

    def characterize(self, inventory, method):
        return {}


def _fake_iso(*_a, **_k):
    return {
        "interpretation": {
            "data_quality_scorecard": {"overall": "Medium", "indicators": {}},
        },
        "inventory_analysis": {"inventory_results": {"basis": "test", "flows": []}},
    }


def _midpoints(gwp=1.0, land=10.0):
    return {
        "Global warming": {"value": gwp, "unit": "kg CO2-eq per kg"},
        "Land use": {"value": land, "unit": "m2a crop-eq per kg"},
    }


def _measured_only(gwp_field=0.6, gwp_diesel=0.4):
    total = 1000.0
    return _FakeResult(
        contribution_by_source={
            "Field emissions (on-farm)": {
                "Climate change": {"value": gwp_field * total, "unit": "kg CO2-eq"},
            },
            "diesel, burned in agricultural machinery": {
                "Climate change": {"value": gwp_diesel * total, "unit": "kg CO2-eq"},
            },
        },
        input_matches=[
            {"input": "diesel, burned in agricultural machinery", "matched": "diesel...", "estimated": False},
        ],
    )


def _estimated_diesel(gwp_field=0.6, gwp_diesel=0.4):
    total = 1000.0
    return _FakeResult(
        contribution_by_source={
            "Field emissions (on-farm)": {
                "Climate change": {"value": gwp_field * total, "unit": "kg CO2-eq"},
            },
            "diesel, burned in agricultural machinery": {
                "Climate change": {"value": gwp_diesel * total, "unit": "kg CO2-eq"},
            },
        },
        input_matches=[
            {"input": "diesel, burned in agricultural machinery", "matched": "diesel...", "estimated": True},
        ],
    )


@pytest.fixture(autouse=True)
def _patch_iso(monkeypatch):
    import engine.iso_report as iso_mod

    monkeypatch.setattr(iso_mod, "build_iso_report", _fake_iso)


def test_p5_lt_p50_lt_p95_gwp():
    mc = run_pedigree_mc(_measured_only(), _midpoints(), _FakeEngine(), 1000.0, n=50, seed=7)
    g = mc["percentiles"]["Global warming"]
    assert g["p5"] < g["p50"] < g["p95"]


def test_estimated_widens_vs_measured():
    mc_e = run_pedigree_mc(_estimated_diesel(), _midpoints(), _FakeEngine(), 1000.0, n=50, seed=11)
    mc_m = run_pedigree_mc(_measured_only(), _midpoints(), _FakeEngine(), 1000.0, n=50, seed=11)
    we = mc_e["percentiles"]["Global warming"]["p95"] - mc_e["percentiles"]["Global warming"]["p5"]
    wm = mc_m["percentiles"]["Global warming"]["p95"] - mc_m["percentiles"]["Global warming"]["p5"]
    assert we > wm
    assert study_gsd(_estimated_diesel().input_matches) > study_gsd(_measured_only().input_matches)


def test_seed_reproducibility():
    kwargs = dict(n=50, seed=99)
    a = run_pedigree_mc(_measured_only(), _midpoints(), _FakeEngine(), 1000.0, **kwargs)
    b = run_pedigree_mc(_measured_only(), _midpoints(), _FakeEngine(), 1000.0, **kwargs)
    assert a["percentiles"] == b["percentiles"]
    assert a["single_score"] == b["single_score"]


def test_apply_mc_sets_ranges():
    mid = {"Global warming": {"value": 1.0, "unit": "kg", "uncertainty_range": [0.7, 1.4]}}
    mc = run_pedigree_mc(_estimated_diesel(), mid, _FakeEngine(), 1000.0, n=50, seed=2)
    apply_mc_to_midpoints(mid, mc)
    lo, hi = mid["Global warming"]["uncertainty_range"]
    assert lo < 1.0 < hi


def test_run_uncertainty_false_keeps_flat_band():
    assessment = {
        "company_name": "Test",
        "country": "Ghana",
        "foods": [{"name": "Maize", "quantity_kg": 1000, "area_allocated": 2.0}],
    }
    resp = to_assessment_response(
        _FakeResult(gwp_per_kg=2.5), assessment, _FakeEngine(), 1000.0, "test-id",
        run_uncertainty=False,
    )
    gwp = resp["midpoint_impacts"]["Global warming"]
    val = gwp["value"]
    assert gwp["uncertainty_range"] == pytest.approx([val * 0.7, val * 1.4])
    assert resp.get("uncertainty") is None


def test_run_uncertainty_true_replaces_flat_band_with_mc():
    assessment = {
        "company_name": "Test",
        "country": "Ghana",
        "foods": [{"name": "Maize", "quantity_kg": 1000, "area_allocated": 2.0}],
    }
    resp = to_assessment_response(
        _FakeResult(gwp_per_kg=2.5), assessment, _FakeEngine(), 1000.0, "test-id",
        run_uncertainty=True, uncertainty_n=50,
    )
    unc = resp.get("uncertainty")
    assert unc is not None
    assert unc["n"] == 50
    assert "Global warming" in unc["percentiles"]


def test_api_model_defaults_uncertainty_on():
    from app.production.models import AssessmentRequest

    assert AssessmentRequest.model_fields["run_uncertainty"].default is True


def test_gsd_classes_present():
    assert "measured_match" in GSD_BY_CLASS
    assert "estimated_activity" in GSD_BY_CLASS
    assert "field_ef" in GSD_BY_CLASS
