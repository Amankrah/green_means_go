#!/usr/bin/env python3
"""
test_llm_no_invented_numbers.py: the model must never invent an emission factor,
characterisation factor, yield, amount or dataset. Every number in a result must trace to
the canonical store, to a cited constant in code, or to the user's input.

  (a) classification and adjudication run with fake clients that answer with adversarial
      numbers; no model-originated number reaches an inventory amount or impact result.
  (b) narrative: every number in generated text appears in (or is a rounding of) the
      grounding payload; offending sentences are stripped, and text that is mostly
      invented is rejected in favour of the deterministic template.
  (c) a real case-study assessment (canonical store) solved twice, with GMG_LLM=0 and with
      fake adjudication: every impact value is reproduced independently from store
      processes chosen among the matcher's own candidates and the user's amounts.

No test calls the real API.
"""
from __future__ import annotations

import copy
import json
import math
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
for p in (_ROOT, _ROOT / "app"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from engine.inputs import FUEL_MJ_PER_L, extract_purchased_inputs  # noqa: E402
from engine.llm.adjudicate import adjudicate  # noqa: E402
from engine.llm.classify import classify  # noqa: E402
from engine.llm.fakes import FakeLLM  # noqa: E402
from engine.llm.numbers import collect_evidence_numbers, find_numbers, is_traceable  # noqa: E402
from engine.process_inputs import extract_processing_inputs  # noqa: E402

# Numbers an adversarial model tries to smuggle in. None of them occurs in the inputs below.
ADVERSARIAL = [12345.678, 9.87, 777.0, 4.2, 0.0314, 31.4]


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("GMG_LLM_CACHE_DIR", str(tmp_path / "cache"))
    for k in ("GMG_LLM", "GMG_LLM_ADJUDICATE"):
        monkeypatch.delenv(k, raising=False)
    for mod in ("engine.llm.classify", "engine.llm.adjudicate", "engine.llm.client"):
        monkeypatch.setattr(sys.modules[mod], "get_client", lambda: None)
    yield


def _all_numbers(obj) -> list[float]:
    out = []

    def walk(o):
        if isinstance(o, bool) or o is None:
            return
        if isinstance(o, (int, float)):
            out.append(float(o))
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                walk(v)
    walk(obj)
    return out


def _assert_no_adversarial(obj):
    for x in _all_numbers(obj):
        for bad in ADVERSARIAL:
            assert not math.isclose(x, bad, rel_tol=1e-9), f"model number {bad} leaked: {x}"


def _adversarial_classifier(label_for):
    def respond(system, user, schema):
        allowed = schema["properties"]["label"]["enum"]
        text = user.split("User text: ", 1)[1].split("\n", 1)[0]
        label = label_for(text, allowed)
        return {"label": label, "confidence": 12345.678,
                "reason": "Use 9.87 kg CO2e per kg and 777 kg per ha, 31.4% lower."}
    return respond


# ------------------------------------------------------------------------- (a)

def _farm_case() -> dict:
    return json.loads((_ROOT / "engine" / "case_studies" / "ghana_maize_cowpea_intercrop.json")
                      .read_text(encoding="utf-8"))


def _classify_farm_inputs(assessment: dict, client) -> dict:
    """The integration the lead will wire (see handoff): free-text fertiliser and fuel
    names are replaced by their vocabulary label when classification is confident. Only
    strings change; every numeric field is the user's."""
    a = copy.deepcopy(assessment)
    for app in ((a.get("management_practices") or {}).get("fertilization") or {}).get(
            "fertilizer_applications") or []:
        r = classify("fertiliser", app["fertilizer_type"], client=client)
        if r["label"] and not r["needs_confirmation"]:
            app["fertilizer_type"] = r["label"]
    for fu in (a.get("equipment_energy") or {}).get("fuel_consumption") or []:
        r = classify("fuel", fu.get("fuel_type") or "", client=client)
        if r["label"] and not r["needs_confirmation"]:
            fu["fuel_type"] = r["label"]
    return a


def test_a_classification_never_changes_amounts():
    base = _farm_case()
    # make the free text messy so the model path is exercised
    mp = base["management_practices"]["fertilization"]["fertilizer_applications"]
    mp[0]["fertilizer_type"] = "compound fert. (the blue bag)"
    mp[1]["fertilizer_type"] = "white prills, nitrogen"
    base.setdefault("equipment_energy", {})["fuel_consumption"] = [
        {"fuel_type": "gas oil from the roadside seller", "monthly_consumption": 45}]

    want, _ = extract_purchased_inputs(base)
    fake = FakeLLM(_adversarial_classifier(
        lambda text, allowed: "Urea" if "Urea" in allowed and "nitrogen" in text
        else ("NPK Compound" if "NPK Compound" in allowed else allowed[0])))
    classified = _classify_farm_inputs(base, fake)
    got, _ = extract_purchased_inputs(classified)

    assert fake.calls, "the adversarial model path was not exercised"
    # Non-fuel inputs: a relabel changes no amount. A fuel relabel legitimately selects that
    # carrier's cited LHV (the adversarial fake picks the wrong fuel on purpose), so fuels
    # are checked against the cited table instead of the unclassified run.
    nonfuel = lambda xs: [(i["amount"], i["unit"]) for i in xs if i["kind"] != "fuel"]
    assert nonfuel(got) == nonfuel(want)
    _assert_no_adversarial(got)
    # every amount is user number x user number (x area), or x a cited LHV constant
    area = sum(f.get("area_allocated") or 0 for f in base["foods"])
    for inp, app in zip([i for i in got if i["kind"] == "fertiliser"], mp):
        assert inp["amount"] == app["application_rate"] * (app.get("applications_per_season") or 1) * area
    # user litres: metered monthly x 12, or equipment hours x the user's L/h (the pump stops
    # being de-duplicated against the metered stream once that stream is relabelled)
    user_litres = {45 * 12} | {eq["hours_per_year"] * eq["fuel_efficiency"]
                               for eq in base["equipment_energy"]["equipment"]
                               if eq.get("fuel_efficiency") and eq.get("hours_per_year")}
    for fuel in [i for i in got if i["kind"] == "fuel" and "estimated" not in i]:
        assert fuel["native_amount"] in user_litres
        assert fuel["lhv_mj_per_unit"] == FUEL_MJ_PER_L[fuel["fuel"]]  # a cited constant
        assert fuel["amount"] == pytest.approx(fuel["native_amount"] * FUEL_MJ_PER_L[fuel["fuel"]])


def test_a_raw_material_classification_never_changes_amounts():
    req = json.loads((_ROOT / "app" / "processing" / "example_cassava_processing.json")
                     .read_text(encoding="utf-8"))
    want, _, want_kg = extract_processing_inputs(req)
    fake = FakeLLM(_adversarial_classifier(lambda text, allowed: "cassava"))
    req2 = copy.deepcopy(req)
    for p in req2["processed_products"]:
        for ri in p.get("raw_material_inputs") or []:
            r = classify("raw_material", "roots from the bush farm", client=fake)
            if r["label"]:
                ri["material_name"] = r["label"]
    got, _, got_kg = extract_processing_inputs(req2)
    assert got_kg == want_kg
    assert sorted(i["amount"] for i in got) == sorted(i["amount"] for i in want)
    _assert_no_adversarial(got)


def test_a_classify_result_carries_no_model_quantity():
    fake = FakeLLM(_adversarial_classifier(lambda t, allowed: allowed[0]))
    r = classify("crop", "fonio", client=fake)
    nums = [v for k, v in r.items() if isinstance(v, (int, float)) and not isinstance(v, bool)]
    assert nums == [r["confidence"]] and 0.0 <= r["confidence"] <= 1.0
    assert not any(ch.isdigit() for ch in r.get("reason", ""))


# ------------------------------------------------------------------------- (b)

def _assessment_with_iso() -> dict:
    return {
        "company_name": "Tamale Agro Ventures",
        "country": "Ghana",
        "single_score": {"value": 412.73, "unit": "uPt per kg", "band": "medium",
                         "band_basis": "tertiles of benchmark crops"},
        "midpoint_impacts": {
            "Climate change": {"value": 0.8421, "unit": "kg CO2-eq"},
            "Land use": {"value": 3.917, "unit": "m2a crop-eq"},
            "Water use": {"value": 0.0562, "unit": "m3 world-eq"},
        },
        "contribution_by_source": {
            "Urea 46-0-0 fertiliser": {"Climate change": {"value": 0.3104, "unit": "kg CO2-eq"}},
            "Field emissions (on-farm)": {"Climate change": {"value": 0.4377, "unit": "kg CO2-eq"}},
        },
        "input_matches": [{"input": "Urea 46-0-0 fertiliser", "matched": "market for urea",
                           "kind": "fertiliser", "location": "RoW", "source": "ecoinvent 3.11"}],
        "recommendations": [{"title": "Split urea into two applications"}],
        "iso_report": {
            "document_control": {"title": "Cradle-to-gate LCA of maize, Ghana"},
            "scope": {"functional_unit": "1 kg of harvested maize at the farm gate",
                      "boundary_included": "cradle to farm gate",
                      "boundary_excluded": "capital goods",
                      "lcia_method": "EF 3.1",
                      "assumptions_and_limitations": ["IPCC 2019 Tier 1 field emissions"]},
            "inventory_analysis": {"inputs_matched": 4, "notes": []},
            "impact_assessment": {"results_table": []},
            "interpretation": {"significant_issues": ["Field N2O dominates climate change"]},
        },
    }


def _grounding_evidence(assessment: dict) -> list[float]:
    from services.report_grounding import build_grounding_payload
    return collect_evidence_numbers(build_grounding_payload(assessment))


def _assert_all_numbers_traceable(text: str, evidence: list[float]):
    bad = [n["token"] for n in find_numbers(text) if not is_traceable(n, evidence)]
    assert not bad, f"untraceable numbers in narrative: {bad}"


def test_b_narrative_strips_invented_numbers():
    from services.ai_report_generator import PLAIN_FIELDS, generate_narrative
    assessment = _assessment_with_iso()
    evidence = _grounding_evidence(assessment)
    answer = {
        "headline": "Your maize scored 413 uPt per kg, in the medium band.",
        "summary": ("Climate change is 0.84 kg CO2-eq per kg of maize. "
                    "That is 31.4% lower than the Ghana average. Land use is 3.92 m2a crop-eq."),
        "biggest_drivers": "Field emissions (0.44 kg CO2-eq) and urea (0.31 kg CO2-eq) lead.",
        "what_you_can_do": "Split urea into two applications. This would save 777 kg CO2e a year.",
        "caveats": "These are screening results pending review, following ISO 14044.",
    }
    fake = FakeLLM(answer)
    out = generate_narrative(assessment, "plain", client=fake)
    assert out["fallback"] is False and out["model"] == "fake-model"
    _assert_all_numbers_traceable(out["text"], evidence)
    removed_nums = {n for r in out["numbers_removed"] for n in r["numbers"]}
    assert {"31.4", "777"} <= removed_nums
    assert "0.84 kg CO2-eq" in out["text"] and "413" in out["text"]
    assert set(out["sections"]) == set(PLAIN_FIELDS)


def test_b_mostly_invented_narrative_is_rejected_for_template():
    from services.ai_report_generator import ISO_FIELDS, generate_narrative
    assessment = _assessment_with_iso()
    evidence = _grounding_evidence(assessment)
    junk = {f: f"The factor is {x} kg CO2e per kg." for f, x in zip(ISO_FIELDS, ADVERSARIAL)}
    out = generate_narrative(assessment, "iso", client=FakeLLM(junk))
    assert out["fallback"] is True and out["model"] == "deterministic-template"
    assert "rejected" in out["fallback_reason"]
    _assert_all_numbers_traceable(out["text"], evidence)
    for bad in ("12345", "9.87", "777", "4.2"):
        assert bad not in out["text"]


@pytest.mark.parametrize("style", ["plain", "iso"])
def test_b_template_numbers_trace_to_payload(style, monkeypatch):
    from services.ai_report_generator import generate_narrative
    monkeypatch.setenv("GMG_LLM", "0")
    assessment = _assessment_with_iso()
    out = generate_narrative(assessment, style)
    assert out["fallback"] is True and out["numbers_removed"] == []
    _assert_all_numbers_traceable(out["text"], _grounding_evidence(assessment))
    assert out["text"]


# ------------------------------------------------------------------------- (c)

_DB = _ROOT / "data" / "canonical" / "lca_engineer.sqlite"

# Representative store queries per purchased-input kind for the stub matcher. The stub
# mimics the embedding matcher's output shape (a candidate list); which candidate wins is
# then decided by the deterministic rule (first) or by the adjudicator (fake model).
_CANDIDATE_QUERY = {"fertiliser:NPK": "NPK (15-15-15)", "fertiliser:Urea": "urea",
                    "fuel": "diesel, burned in agricultural machinery",
                    "pesticide": "pesticide, unspecified", "compost": "compost"}


@pytest.fixture(scope="module")
def store():
    if not _DB.exists():
        pytest.skip("canonical store not present")
    from ingestion.query import CanonicalQuery
    q = CanonicalQuery(_DB)
    yield q
    q.close()


def _candidates(q, inp) -> list[dict]:
    kind = inp.get("kind")
    key = kind
    if kind == "fertiliser":
        key = "fertiliser:Urea" if "urea" in inp["name"].lower() else "fertiliser:NPK"
    text = _CANDIDATE_QUERY.get(key, inp.get("match_as") or inp["name"])
    out = []
    for p in q.find_processes(text, limit=25):
        full = q.get_process(p["uid"]) or {}
        if full.get("ref_unit") != inp.get("unit"):
            continue
        out.append({"uid": p["uid"], "name": p["name"], "reference_product": full.get("ref_product") or p["name"],
                    "location": p.get("location"), "source": q.source_label(p["uid"]),
                    "ref_unit": full.get("ref_unit"), "score": round(0.8 - 0.01 * len(out), 2)})
        if len(out) == 4:
            break
    return out


def _run(q, inputs, onfarm_lci, client, chosen: dict):
    from engine.orchestrator import FarmLCA
    from engine.regions import get_region
    from engine.flowmap import OnFarmFlowMap

    eng = FarmLCA.__new__(FarmLCA)       # skip the embedding index: the stub supplies candidates
    eng.region = get_region("GH")
    eng.q = q
    eng.fmap = OnFarmFlowMap(_DB)
    eng.method = eng.region.default_method
    by_name = {i.get("match_as") or i["name"]: i for i in inputs}

    def match(text, expand=False, context=None):
        inp = by_name.get(text)
        if inp is None:
            return None
        cands = _candidates(q, inp)
        if not cands:
            return None
        pick = cands[0]
        verdict = adjudicate(text, {"region": "GH", "kind": inp.get("kind"), "unit": inp.get("unit")},
                             cands, client=client)
        if verdict:
            pick = next(c for c in cands if c["uid"] == verdict["uid"])
        chosen[inp["name"]] = pick["uid"]
        return {"uid": pick["uid"], "name": pick["name"], "location": pick["location"], "score": pick["score"]}

    eng._match_input = match
    try:
        return eng.assess(onfarm_lci, inputs)
    finally:
        eng.fmap.close()


def _recompute(q, method, onfarm_lci, inputs, chosen) -> dict:
    """Independent reconstruction from the store: on-farm flows + cradle_to_gate(uid, user amount)."""
    from engine.flowmap import OnFarmFlowMap
    fmap = OnFarmFlowMap(_DB)
    merged: dict = {}

    def add(uid, amt, name, unit):
        r = merged.setdefault(uid, {"name": name, "unit": unit, "amount": 0.0})
        r["amount"] += amt
    try:
        for f in onfarm_lci:
            uid = fmap.resolve(f["substance"])
            if uid:
                add(uid, float(f["quantity"]), f["substance"], f.get("unit"))
    finally:
        fmap.close()
    for inp in inputs:
        uid = chosen.get(inp["name"])
        if not uid:
            continue
        sc = q.cradle_to_gate(uid, amount=float(inp["amount"]))
        for fuid, ef in sc.elementary_flows.items():
            add(fuid, ef["amount"], ef.get("name"), ef.get("unit"))
    return q.characterize_flows(merged, method)


def test_c_case_study_results_trace_to_store_and_user(store, monkeypatch):
    case = _farm_case()
    inputs, _ = extract_purchased_inputs(case)
    # Fertilisers are the classic close-candidate case (urea vs UAN, NPK as N / as K2O ...).
    # Kept to two inputs because every characterisation pass over the store takes ~15 s.
    inputs = [i for i in inputs if i["kind"] == "fertiliser"]
    assert inputs
    user_amounts = {i["name"]: i["amount"] for i in inputs}
    # Field emissions stand in for the Rust kernel output (a fixed, user-derived LCI).
    onfarm = [{"substance": "N2O", "quantity": 1.9, "unit": "kg"},
              {"substance": "CO2", "quantity": 120.0, "unit": "kg"}]

    # baseline: model off
    monkeypatch.setenv("GMG_LLM", "0")
    never = FakeLLM({}, model="must-not-be-called")
    chosen0: dict = {}
    r0 = _run(store, inputs, onfarm, never, chosen0)
    assert never.calls == []
    monkeypatch.delenv("GMG_LLM")

    # adversarial adjudicator: always the LAST candidate, rationale full of invented numbers
    def respond(system, user, schema):
        uids = [u for u in schema["properties"]["choice"]["enum"] if u != "ABSTAIN"]
        return {"choice": sorted(uids)[-1],
                "rationale": "Its factor is 4.2 kg CO2e/kg; use 777 kg instead of the user's amount."}
    fake = FakeLLM(respond)
    chosen1: dict = {}
    r1 = _run(store, inputs, onfarm, fake, chosen1)
    assert fake.calls, "adjudicator was not consulted"

    for res, chosen in ((r0, chosen0), (r1, chosen1)):
        # inventory amounts are the user's
        for row in res.input_matches:
            if row.get("matched"):
                assert row["amount"] == user_amounts[row["input"]]
        # every chosen dataset is a store process among the matcher's candidates
        for name, uid in chosen.items():
            assert store.get_process(uid) is not None
        # every impact value reproduces from store + user amounts
        want = _recompute(store, res.method, onfarm, inputs, chosen)
        assert set(want) == set(res.impacts)
        for cat, v in res.impacts.items():
            assert v["value"] == pytest.approx(want[cat]["value"], rel=1e-9, abs=1e-15), cat
        _assert_no_adversarial({k: v["value"] for k, v in res.impacts.items()})
        _assert_no_adversarial([r["amount"] for r in res.inventory.values()])
