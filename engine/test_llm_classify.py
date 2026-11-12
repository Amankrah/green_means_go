#!/usr/bin/env python3
"""
test_llm_classify.py: unit tests for the intelligence layer (engine/llm) with fake model
clients. No test here calls the real API; the optional live smoke test runs only with
GMG_LLM_LIVE=1.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.llm import cache as llm_cache  # noqa: E402
from engine.llm import client as llm_client  # noqa: E402
from engine.llm.adjudicate import adjudicate  # noqa: E402
from engine.llm.classify import CONFIRM_THRESHOLD, classify  # noqa: E402
from engine.llm.client import LLMError  # noqa: E402
from engine.llm.fakes import FakeLLM  # noqa: E402
from engine.llm.numbers import (  # noqa: E402
    collect_evidence_numbers, guard_text, redact_untraceable, untraceable_numbers)
from engine.llm.vocab import FUELS, PACKAGING, RAW_MATERIALS, VOCABULARIES  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    """Every test gets an empty cache dir and no inherited flags; never the committed cache."""
    monkeypatch.setenv("GMG_LLM_CACHE_DIR", str(tmp_path / "cache"))
    for k in ("GMG_LLM", "GMG_LLM_ADJUDICATE"):
        monkeypatch.delenv(k, raising=False)
    # Make sure no test can reach the real API through the default client.
    monkeypatch.setattr(llm_client, "get_client", lambda: None)
    c_mod = sys.modules["engine.llm.classify"]  # the package re-exports the functions
    a_mod = sys.modules["engine.llm.adjudicate"]  # under the same names as the modules
    monkeypatch.setattr(c_mod, "get_client", lambda: None)
    monkeypatch.setattr(a_mod, "get_client", lambda: None)
    yield


# ---------------------------------------------------------------- vocabularies

def test_vocabularies_come_from_engine_code():
    from engine.inputs import FUEL_MJ_PER_L
    from engine.process_inputs import PACKAGING_MATCH, RAW_MATERIAL_HINTS, REFINED_MATERIAL_HINTS
    assert {"diesel", "petrol", "kerosene", "lpg", "biodiesel"} <= set(FUELS)
    assert all(k in FUELS or k == "gasoline" for k in FUEL_MJ_PER_L)
    assert set(PACKAGING) == set(PACKAGING_MATCH)
    assert set(RAW_MATERIALS) == set(RAW_MATERIAL_HINTS) | set(REFINED_MATERIAL_HINTS)
    for crop in ("groundnut", "millet", "rice", "tomato", "onion", "cotton", "maize", "sorghum",
                 "sesame", "sugarcane", "citrus", "grapes", "apples", "pears"):
        assert crop in VOCABULARIES["crop"], crop


# ---------------------------------------------------------------- classify, deterministic

@pytest.mark.parametrize("kind,text,label,source", [
    ("fuel", "AGO", "diesel", "synonym"),
    ("fuel", "PMS", "petrol", "synonym"),
    ("fuel", "DPK", "kerosene", "synonym"),
    ("fuel", "Diesel", "diesel", "exact"),
    ("fertiliser", "NPK 15-15-15", "NPK Compound", "synonym"),
    ("fertiliser", "urea fertiliser", "Urea", "contains"),
    ("crop", "Groundnuts", "groundnut", "synonym"),
    ("crop", "paddy rice", "rice", "synonym"),
    ("raw_material", "Maize kernels", "maize", "contains"),
    ("raw_material", "corn flour", "corn flour", "exact"),
    ("packaging", "polythene bag", "PlasticBag", "synonym"),
])
def test_deterministic_hits_never_call_model(kind, text, label, source):
    fake = FakeLLM({"label": "NONE", "confidence": 0.0, "reason": ""})
    r = classify(kind, text, client=fake)
    assert r["label"] == label and r["source"] == source
    assert r["needs_confirmation"] is False and r["model"] == "deterministic"
    assert fake.calls == []


def test_short_synonyms_do_not_fire_inside_phrases():
    r = classify("fertiliser", "I can not recall the name", use_model=False)
    assert r["label"] is None


def test_two_crops_in_one_phrase_is_ambiguous():
    r = classify("crop", "maize and cowpea", use_model=False)
    assert r["label"] is None and r["needs_confirmation"] is True


# ---------------------------------------------------------------- classify, model path

def test_model_label_constrained_and_cached(tmp_path):
    fake = FakeLLM({"label": "cassava", "confidence": 0.93, "reason": "gari is made from cassava"})
    r = classify("crop", "gari", client=fake)
    assert r == {**r, "label": "cassava", "needs_confirmation": False, "model": "fake-model",
                 "cached": False, "source": "model"}
    # enum in the schema is the vocabulary plus NONE
    enum = fake.calls[0]["schema"]["properties"]["label"]["enum"]
    assert set(enum) == set(VOCABULARIES["crop"]) | {"NONE"}
    # second call served from the cache, no new model call
    r2 = classify("crop", "  GARI ", client=fake)
    assert r2["cached"] is True and r2["label"] == "cassava" and len(fake.calls) == 1
    data = json.loads((Path(os.environ["GMG_LLM_CACHE_DIR"]) / "classify_crop.json").read_text())
    assert "gari" in data


def test_low_confidence_needs_confirmation():
    fake = FakeLLM({"label": "millet", "confidence": CONFIRM_THRESHOLD - 0.01, "reason": "maybe"})
    r = classify("crop", "fonio", client=fake)
    assert r["label"] == "millet" and r["needs_confirmation"] is True


def test_out_of_vocabulary_label_rejected():
    fake = FakeLLM({"label": "quinoa", "confidence": 0.99, "reason": "x"})
    r = classify("crop", "quinoa grain", client=fake)
    assert r["label"] is None and r["confidence"] == 0.0 and r["needs_confirmation"] is True


def test_adversarial_confidence_is_clamped():
    fake = FakeLLM({"label": "Urea", "confidence": 12345.678, "reason": "use 9.87 kg CO2e per kg"})
    r = classify("fertiliser", "white prills", client=fake)
    assert r["confidence"] == 1.0
    assert "9.87" not in r.get("reason", "")


def test_gmg_llm_0_disables_model_and_cache(monkeypatch):
    llm_cache.put("classify_crop", "gari", {"label": "cassava", "confidence": 0.9, "model": "m"})
    monkeypatch.setenv("GMG_LLM", "0")
    fake = FakeLLM({"label": "cassava", "confidence": 0.9, "reason": ""})
    r = classify("crop", "gari", client=fake)
    assert r["label"] is None and r["needs_confirmation"] is True and fake.calls == []


def test_cache_served_without_a_key():
    llm_cache.put("classify_crop", "gari", {"label": "cassava", "confidence": 0.9, "model": "m"})
    r = classify("crop", "gari")  # default client is None in tests (no key)
    assert r["label"] == "cassava" and r["cached"] is True


def test_model_error_returns_no_label_and_is_not_cached():
    fake = FakeLLM({}, error=LLMError("boom"))
    r = classify("crop", "gari", client=fake)
    assert r["label"] is None and r["source"] == "error"
    assert llm_cache.get("classify_crop", "gari") is None


def test_custom_vocabulary():
    fake = FakeLLM({"label": "B", "confidence": 0.9, "reason": ""})
    r = classify("crop", "something", vocabulary=["A", "B"], client=fake)
    assert r["label"] == "B"
    assert set(fake.calls[0]["schema"]["properties"]["label"]["enum"]) == {"A", "B", "NONE"}


# ---------------------------------------------------------------- adjudicate

CANDS = [
    {"uid": "u1", "name": "market for urea | urea", "reference_product": "urea",
     "location": "RoW", "source": "ecoinvent 3.11", "ref_unit": "kg", "score": 0.71},
    {"uid": "u2", "name": "urea ammonium nitrate production", "reference_product": "urea ammonium nitrate",
     "location": "RER", "source": "ecoinvent 3.11", "ref_unit": "kg", "score": 0.70},
]


def test_adjudicate_picks_given_uid_and_redacts_invented_numbers():
    fake = FakeLLM({"choice": "u1", "rationale": "Same product; factor is 4.2 kg CO2e and score 0.71."})
    r = adjudicate("urea fertiliser", {"region": "GH", "unit": "kg"}, CANDS, client=fake)
    assert r["uid"] == "u1" and r["model"] == "fake-model"
    assert "4.2" not in r["rationale"] and "0.71" in r["rationale"]  # 0.71 is in the evidence
    assert set(fake.calls[0]["schema"]["properties"]["choice"]["enum"]) == {"u1", "u2", "ABSTAIN"}


def test_adjudicate_rejects_unknown_uid_and_abstain():
    assert adjudicate("urea", {"region": "GH"}, CANDS,
                      client=FakeLLM({"choice": "u999", "rationale": ""})) is None
    assert adjudicate("urea x", {"region": "GH"}, CANDS,
                      client=FakeLLM({"choice": "ABSTAIN", "rationale": "none fit"})) is None


def test_adjudicate_cache_key_and_flags(monkeypatch):
    fake = FakeLLM({"choice": "u2", "rationale": "r"})
    assert adjudicate("Urea!", {"region": "GH"}, CANDS, client=fake)["uid"] == "u2"
    # same normalised query, same uids in another order, same region: cache hit
    r = adjudicate("urea", {"region": "gh"}, list(reversed(CANDS)), client=fake)
    assert r["uid"] == "u2" and r["cached"] is True and len(fake.calls) == 1
    # different region: new call
    adjudicate("urea", {"region": "NG"}, CANDS, client=fake)
    assert len(fake.calls) == 2
    for flag in ("GMG_LLM_ADJUDICATE", "GMG_LLM"):
        monkeypatch.setenv(flag, "0")
        assert adjudicate("urea", {"region": "GH"}, CANDS, client=fake) is None
        monkeypatch.delenv(flag)
    assert len(fake.calls) == 2


def test_adjudicate_needs_two_candidates_and_a_client():
    assert adjudicate("urea", {}, CANDS[:1], client=FakeLLM({"choice": "u1", "rationale": ""})) is None
    assert adjudicate("urea new", {"region": "GH"}, CANDS) is None  # no key, no cache


# ---------------------------------------------------------------- number guard

def test_number_guard_rounding_rules():
    ev = collect_evidence_numbers({"a": 1234.5678, "b": 0.4217, "c": "ISO 14044 and EF 3.1",
                                   "d": -2.5e-3})
    assert untraceable_numbers("about 1,235 kg and 1234.57 and 1,200", ev) == []
    assert untraceable_numbers("42% of the total, or 0.42", ev) == []
    assert untraceable_numbers("EF 3.1 per ISO 14044; CO2 and N2O, PM2.5", ev) == []
    assert untraceable_numbers("-0.0025 and 2.5e-3", ev) == []
    assert untraceable_numbers("three inputs, the top 3", ev) == []
    assert untraceable_numbers("cut by 37.5%", ev) == ["37.5"]
    assert untraceable_numbers("5 kg of urea", ev) == ["5"]
    assert untraceable_numbers("1,300 kg", ev) == ["1,300"]


def test_guard_text_drops_only_offending_sentences():
    ev = [12.3]
    clean, removed = guard_text("Climate is 12.3 kg. You could save 40% by switching. Good.", ev)
    assert clean == "Climate is 12.3 kg. Good."
    assert removed[0]["numbers"] == ["40"]
    assert redact_untraceable("score 12.3 not 99", ev) == "score 12.3 not [n]"


# ---------------------------------------------------------------- client hygiene

def test_client_errors_never_carry_the_key(monkeypatch):
    secret = "sk-ant-test-SECRET-should-not-leak"
    monkeypatch.setenv("ANTHROPIC_API_KEY", secret)
    llm_client._reset_for_tests()
    try:
        c = llm_client.AnthropicJSONClient(model="claude-opus-5-5")
        assert secret not in repr(c)

        class Boom(Exception):
            pass

        def explode(**kw):
            raise Boom(f"failure with key {secret}")
        monkeypatch.setattr(c._sdk.messages, "create", explode)
        with pytest.raises(LLMError) as ei:
            c.complete_json(system="s", user="u", schema={"type": "object"})
        assert secret not in str(ei.value) and ei.value.__cause__ is None
    finally:
        llm_client._reset_for_tests()


# ---------------------------------------------------------------- optional live smoke test

@pytest.mark.skipif(os.getenv("GMG_LLM_LIVE") != "1", reason="live API smoke test; set GMG_LLM_LIVE=1")
def test_live_smoke(monkeypatch):
    monkeypatch.undo()  # restore the real get_client and env
    monkeypatch.setenv("GMG_LLM_CACHE_DIR", os.environ.get("GMG_LLM_CACHE_DIR_LIVE", str(Path(
        os.environ.get("TMP", "/tmp")) / "gmg_llm_live_cache")))
    llm_client._reset_for_tests()
    real = llm_client.get_client()
    assert real is not None, "no ANTHROPIC_API_KEY available"
    r = classify("fuel", "gas oil for the tractor (AGO 50)", client=real)
    assert r["label"] in ("diesel", None)
    r = classify("crop", "gari", client=real)
    assert r["label"] == "cassava" and r["source"] == "model"
    a = adjudicate("urea fertiliser", {"region": "GH", "kind": "fertiliser", "unit": "kg"},
                   CANDS, client=real)
    assert a is None or a["uid"] == "u1"


def test_label_inside_a_longer_name_is_only_a_suggestion():
    # Bambara groundnut (Vigna subterranea) is not groundnut (Arachis hypogaea); ASN is not
    # ammonium sulphate. Without a model they come back as suggestions to confirm.
    for kind, text, label in (("crop", "bambara groundnut", "groundnut"),
                              ("fertiliser", "ammonium sulfate nitrate", "Ammonium Sulphate")):
        r = classify(kind, text, use_model=False)
        assert r["label"] == label and r["needs_confirmation"] is True
        assert r["source"] == "contains_weak"
    # generic extra words do not weaken a match
    assert classify("crop", "maize grain local variety")["needs_confirmation"] is False
    assert classify("fertiliser", "NPK 20-10-10 + S")["label"] == "NPK Compound"


def test_weak_containment_defers_to_the_model():
    fake = FakeLLM({"label": "NONE", "confidence": 0.0, "reason": "a different legume"})
    r = classify("crop", "bambara groundnut", client=fake)
    assert len(fake.calls) == 1 and r["label"] is None and r["needs_confirmation"] is True
