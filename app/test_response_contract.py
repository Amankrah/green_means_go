"""Response contract: every top-level key the engine returns must survive FastAPI's
response_model filtering. A key missing from AssessmentResponse is silently dropped on
POST /assess and GET /assess/{id} (the stored payload keeps it, the client never sees it).

The engine-side key lists are read from the adapter / service source with `ast`, so a key
added there without a matching response field fails here.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "app"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from fastapi import FastAPI                                   # noqa: E402
from fastapi.testclient import TestClient                     # noqa: E402

from production.models import AssessmentResponse              # noqa: E402
from processing.models import ProcessingAssessmentResponse    # noqa: E402

# Keys the engine adds that are internal to the run, not part of the API response.
INTERNAL = frozenset()


def _keys_written(path: Path, func: str, var: str) -> set[str]:
    """String keys of `var = {...}`, `var["k"] = ...` and `for key in ("a", ...): var[key] = ...`
    inside function `func`."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == func)
    keys: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == var and isinstance(node.value, ast.Dict):
                    keys |= {k.value for k in node.value.keys
                             if isinstance(k, ast.Constant) and isinstance(k.value, str)}
                if (isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name)
                        and t.value.id == var and isinstance(t.slice, ast.Constant)):
                    keys.add(t.slice.value)
        if isinstance(node, ast.For) and isinstance(node.iter, ast.Tuple):
            writes_var = any(isinstance(s, ast.Subscript) and isinstance(s.value, ast.Name)
                             and s.value.id == var
                             for b in ast.walk(node) if isinstance(b, ast.Assign)
                             for s in b.targets)
            if writes_var:
                keys |= {e.value for e in node.iter.elts
                         if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    return keys


def _farm_engine_keys() -> set[str]:
    keys = _keys_written(ROOT / "engine" / "adapter.py", "to_assessment_response", "out")
    keys |= _keys_written(ROOT / "engine" / "service.py", "_review_flag", "out")
    return keys


def _processing_engine_keys() -> set[str]:
    return _keys_written(ROOT / "engine" / "process_adapter.py", "to_process_response", "resp")


def test_engine_key_extraction_sees_the_new_outputs():
    keys = _farm_engine_keys()
    assert {"soc_management", "per_crop_results", "review_required", "review_items",
            "functional_units", "sensitivity_analysis"} <= keys, keys


def test_every_farm_engine_key_is_a_response_field():
    missing = sorted(_farm_engine_keys() - set(AssessmentResponse.model_fields) - INTERNAL)
    assert not missing, f"AssessmentResponse would drop engine outputs: {missing}"


def test_every_processing_engine_key_is_a_response_field():
    missing = sorted(_processing_engine_keys() - set(ProcessingAssessmentResponse.model_fields))
    assert not missing, f"ProcessingAssessmentResponse would drop engine outputs: {missing}"


def _farm_payload() -> dict:
    return {
        "id": "a1", "company_name": "x", "country": "Ghana",
        "assessment_date": "2026-11-25T00:00:00+00:00",
        "midpoint_impacts": {"Climate change": {"value": 1.0, "unit": "kg CO2-eq",
                                               "uncertainty_range": [0.7, 1.4],
                                               "percentiles": {"p5": 0.8}}},
        "endpoint_impacts": {},
        "single_score": {"value": 10.0, "unit": "uPt", "label": "EF 3.1 weighted single score",
                         "band": "Unavailable", "band_basis": "none",
                         "band_cutoffs": {"low": None, "high": None},
                         "weighting_basis": "EF 3.1 official weights",
                         "normalised_midpoints": {"Climate change": 1e-4},
                         "iso_14044_disclosure": "not for comparative assertions",
                         "future_key": 1},
        "data_quality": {"overall_confidence": "Medium", "regional_adaptation": True,
                         "completeness_score": 1.0, "scorecard": {"x": 1}, "notes": ["n"]},
        "breakdown_by_food": {},
        "functional_units": {"per_kg": {}, "per_ha": {}, "per_crop": [{"crop": "Maize"}]},
        "sensitivity_analysis": {"contribution": {}, "one_at_a_time": [{"case": "EF1"}],
                                 "method_sensitivity": {"ReCiPe": 1}},
        "soc_management": {"value": -120.0, "booked": True, "included_in_headline": False},
        "review_required": True,
        "review_items": [{"input": "Urea", "matched": "urea, as N"}],
        "needs_review": True,
        "climate_zone_used": "dry",
        "per_crop_results": [{"crop_id": "crop_1", "midpoint_impacts_per_kg": {}}],
        "coproduct_allocation": {"Maize": {"factor": 0.9}},
        "provenance": {"store": "ecoinvent 3.11"},
        "engine_inventory_by_source": {"Urea": {}},
    }


def test_new_outputs_survive_response_model_filtering():
    app = FastAPI()

    @app.get("/r", response_model=AssessmentResponse)
    def _r():
        return AssessmentResponse(**_farm_payload())

    body = TestClient(app).get("/r").json()
    for key in ("soc_management", "review_required", "review_items", "needs_review",
                "climate_zone_used", "per_crop_results", "coproduct_allocation", "provenance",
                "engine_inventory_by_source"):
        assert body[key] == _farm_payload()[key], key
    assert body["functional_units"]["per_crop"] == [{"crop": "Maize"}]
    assert body["sensitivity_analysis"]["one_at_a_time"] == [{"case": "EF1"}]
    ss = body["single_score"]
    assert ss["label"] == "EF 3.1 weighted single score"
    assert ss["band_cutoffs"] == {"low": None, "high": None}
    assert ss["iso_14044_disclosure"] and ss["normalised_midpoints"]
    assert ss["future_key"] == 1                      # nested blocks keep unknown keys
    assert body["midpoint_impacts"]["Climate change"]["percentiles"] == {"p5": 0.8}
    assert body["data_quality"]["scorecard"] == {"x": 1}
