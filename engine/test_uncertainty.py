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
    # Diesel-dominated case: with the corrected (non-doubled) pedigree sigmas the diesel GSD
    # difference is small next to the field GSD (~2), so isolate the source under test.
    mc_e = run_pedigree_mc(_estimated_diesel(gwp_field=0.0), _midpoints(), _FakeEngine(), 1000.0, n=50, seed=11)
    mc_m = run_pedigree_mc(_measured_only(gwp_field=0.0), _midpoints(), _FakeEngine(), 1000.0, n=50, seed=11)
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


def test_processing_model_defaults_uncertainty_on():
    from app.processing.models import (
        ProcessingAssessmentRequest,
        ProcessingAssessmentResponse,
    )

    # Facility path defaults MC on for parity with the farm path...
    assert ProcessingAssessmentRequest.model_fields["run_uncertainty"].default is True
    # ...and the response can carry the MC block (else it is silently dropped).
    assert "uncertainty" in ProcessingAssessmentResponse.model_fields


def test_process_adapter_accepts_uncertainty_kwargs():
    import inspect

    from engine.process_adapter import to_process_response

    params = inspect.signature(to_process_response).parameters
    # process_service passes these through; a signature drift here is what broke the wiring
    # once already, so lock it in.
    assert {"run_uncertainty", "uncertainty_n", "uncertainty_seed"} <= set(params)


class _GroupQ:
    """characterize_flows: climate = 300 x N2O + 30 x CH4; land = occupation; eutro = NO3."""

    def find_method(self, _n):
        return None

    def characterize_flows(self, flows, method):
        out = {"Climate change": {"value": 0.0, "unit": "kg CO2-eq"},
               "Land use": {"value": 0.0, "unit": "m2a"},
               "Eutrophication: marine": {"value": 0.0, "unit": "kg N-eq"}}
        for r in flows.values():
            n = r["name"]
            if n == "N2O":
                out["Climate change"]["value"] += 300 * r["amount"]
            elif n == "CH4_bio":
                out["Climate change"]["value"] += 30 * r["amount"]
            elif n == "land_occ":
                out["Land use"]["value"] += r["amount"]
            elif n == "NO3":
                out["Eutrophication: marine"]["value"] += r["amount"]
        return out


class _GroupEngine(_FakeEngine):
    q = _GroupQ()

    class region:
        climate_zone = "wet"
        name = "Ghana"


def _field_result():
    flows = {"a": {"name": "N2O", "unit": "kg", "amount": 2.0},
             "b": {"name": "CH4_bio", "unit": "kg", "amount": 10.0},
             "c": {"name": "land_occ", "unit": "m2a", "amount": 10000.0},
             "d": {"name": "NO3", "unit": "kg", "amount": 5.0}}
    res = _FakeResult(contribution_by_source={
        "Field emissions (on-farm)": _GroupQ().characterize_flows(flows, "")})
    res.contribution_flows_by_source = {"Field emissions (on-farm)": flows}
    res.inventory = flows
    return res


def test_field_parameters_sampled_separately_with_ipcc_ranges():
    res = _field_result()
    mids = {"Global warming": {"value": 0.9, "unit": "kg CO2-eq per kg"},
            "Land use": {"value": 10.0, "unit": "m2a per kg"},
            "Marine eutrophication": {"value": 0.005, "unit": "kg N-eq per kg"}}
    mc = run_pedigree_mc(res, mids, _GroupEngine(), 1000.0, n=400, seed=3)
    d = mc["field_parameter_distributions"]
    assert d["Field emissions (on-farm) :: N2O"]["parameter"] == "EF1_wet"
    assert d["Field emissions (on-farm) :: N2O"]["range"] == [0.013, 0.019]
    assert d["Field emissions (on-farm) :: CH4"]["range"] == [0.80, 1.76]
    assert d["Field emissions (on-farm) :: NO3"]["parameter"] == "FracLEACH"
    # land occupation is near-certain: much tighter than the old shared field multiplier
    land = mc["percentiles"]["Land use"]
    assert (land["p95"] - land["p5"]) / land["base"] < 0.15
    # nitrate spans the wide FracLEACH range (0.01-0.73 around 0.24)
    eut = mc["percentiles"]["Marine eutrophication"]
    assert eut["p95"] / eut["base"] > 1.5 and eut["p5"] / eut["base"] < 0.6


def test_one_at_a_time_sensitivity_cases():
    from engine.uncertainty import one_at_a_time_sensitivity
    res = _field_result()
    mids = {"Global warming": {"value": 0.9, "unit": "kg CO2-eq per kg"},
            "Marine eutrophication": {"value": 0.005, "unit": "kg N-eq per kg"}}
    oat = one_at_a_time_sensitivity(res, mids, _GroupEngine(), 1000.0)
    cases = {c["case"]: c for c in oat["cases"]}
    # N2O = 600 of 900 g CO2e per kg; EF1 wet high 0.019 / 0.016 -> +18.75 % of 600 -> +12.5 %
    assert cases["EF1 high"]["global_warming_change_pct"] == pytest.approx(100 * 0.6 * (0.019 / 0.016 - 1) / 0.9)
    assert cases["FracLEACH high"]["changes_pct"]["Marine eutrophication"] == pytest.approx(100 * (0.73 / 0.24 - 1))
    assert cases["yield +20%"]["global_warming_change_pct"] == pytest.approx(100 * (1 / 1.2 - 1))
    assert oat["method_sensitivity"] is not None


def test_nh3_range_follows_declared_fertiliser_type():
    from engine.uncertainty import FIELD_PARAMETERS, _nh3_parameter

    def a(*types, compost=False):
        return {"management_practices": {
            "fertilization": {"fertilizer_applications": [
                {"fertilizer_type": t, "application_rate": 50} for t in types]},
            "soil_management": {"uses_compost": compost}}}
    assert _nh3_parameter(a("Urea")) == "FracGASF_urea"
    assert FIELD_PARAMETERS["FracGASF_urea"]["range"] == (0.03, 0.43)
    assert _nh3_parameter(a("Ammonium sulphate")) == "FracGASF_ammonium"
    assert _nh3_parameter(a("Calcium ammonium nitrate")) == "FracGASF_AN"
    assert _nh3_parameter(a("Urea", "NPK 15-15-15")) == "FracGASF"      # mixed -> aggregated
    assert _nh3_parameter(a(compost=True)) == "FracGASM"
    assert _nh3_parameter(None) == "FracGASF"


def test_gsd_classes_present():
    assert "measured_match" in GSD_BY_CLASS
    assert "estimated_activity" in GSD_BY_CLASS
    assert "field_ef" in GSD_BY_CLASS
