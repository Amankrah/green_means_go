"""
classify.py: map a user's free text (crop, fertiliser, fuel, raw material, packaging) onto
the controlled vocabulary the engine recognises.

Order of resolution, cheapest and most reproducible first:
  1. exact match on the normalised label            -> confidence 1.0
  2. deterministic synonym table (vocab.SYNONYMS)    -> confidence 1.0
  3. containment of exactly one label / synonym      -> confidence 0.9
     (raw materials use the engine's own longest-substring rule from process_inputs)
  4. committed cache (engine/llm/cache/classify_<kind>.json)
  5. the model, constrained by a JSON-schema enum to the vocabulary (+ NONE)

GMG_LLM=0 stops after step 3 (label None, needs_confirmation True on a miss). Without an
API key, steps 4 still serves committed answers so runs stay reproducible offline.

The model only ever chooses a label. It never supplies a quantity: the confidence it
returns is used solely to raise the "needs user confirmation" flag, and no number from the
model reaches an inventory amount or an impact result (engine/test_llm_no_invented_numbers.py).
"""
from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Optional

from . import cache
from .client import LLMError, StructuredLLM, get_client, llm_globally_disabled
from .vocab import KINDS, SYNONYMS, VOCABULARIES

CONFIRM_THRESHOLD = float(os.getenv("GMG_LLM_CONFIRM_THRESHOLD", "0.8"))
CONTAINS_CONFIDENCE = 0.9
NONE_LABEL = "NONE"

# Synonym / label keys too short or too generic to trust inside a longer phrase
# ("I can't recall" must not become Calcium Ammonium Nitrate). They still match exactly.
_NO_CONTAINMENT = {"an", "can", "tin", "pp", "pea", "oat", "soy", "fame", "none", "organic",
                   "foliar", "essence", "super", "palm", "bean", "rape", "corn"}

_KIND_HELP = {
    "crop": "a harvested agricultural crop",
    "fertiliser": "a purchased mineral or organic fertiliser product",
    "fuel": "a liquid or gaseous fuel burned in farm machinery, generators or facility equipment",
    "raw_material": "an ingredient or crop bought by a food-processing facility",
    "packaging": "the material of a product's packaging",
}


def _result(label, confidence, model, cached, source, reason=None, error=None) -> dict:
    conf = float(confidence) if confidence is not None else 0.0
    if not math.isfinite(conf):
        conf = 0.0
    conf = min(max(conf, 0.0), 1.0)
    out = {
        "label": label,
        "confidence": round(conf, 3),
        "needs_confirmation": label is None or conf < CONFIRM_THRESHOLD,
        "model": model,
        "cached": cached,
        "source": source,
    }
    if reason:
        out["reason"] = reason
    if error:
        out["error"] = error
    return out


def _words(s: str) -> str:
    return f" {s} "


def _deterministic(kind: str, norm: str, vocab: list[str], default_vocab: bool) -> Optional[dict]:
    by_norm = {cache.normalise(v): v for v in vocab}
    syn = {cache.normalise(k): v for k, v in SYNONYMS.get(kind, {}).items() if v in vocab}

    for cand in (norm, re.sub(r"(es|s)$", "", norm)):
        if cand in by_norm:
            return _result(by_norm[cand], 1.0, "deterministic", False, "exact")
        if cand in syn:
            return _result(syn[cand], 1.0, "deterministic", False, "synonym")

    if kind == "raw_material" and default_vocab:
        # Same rule the engine applies in process_inputs._raw_material_match: longest key
        # found as a substring wins (refined ingredients before farm-gate crops).
        from engine.process_inputs import REFINED_MATERIAL_HINTS, RAW_MATERIAL_HINTS
        expanded = norm
        for k, v in syn.items():
            if _words(k) in _words(norm):
                expanded = f"{expanded} {v}"
        for table in (REFINED_MATERIAL_HINTS, RAW_MATERIAL_HINTS):
            for key in sorted(table, key=len, reverse=True):
                if key in expanded:
                    return _result(key, CONTAINS_CONFIDENCE, "deterministic", False, "contains")
        return None

    hits: dict[str, int] = {}
    for key, label in list(by_norm.items()) + list(syn.items()):
        if len(key) < 3 or key in _NO_CONTAINMENT:
            continue
        if _words(key) in _words(norm):
            hits[label] = max(hits.get(label, 0), len(key))
    if not hits:
        return None
    best = max(hits.values())
    top = [lab for lab, ln in hits.items() if ln == best]
    others = [lab for lab in hits if lab not in top]
    # Two different labels named in one phrase ("maize and cowpea") is ambiguous: ask the
    # model (or the user) rather than silently dropping one.
    if len(top) == 1 and not others:
        return _result(top[0], CONTAINS_CONFIDENCE, "deterministic", False, "contains")
    return None


def _cache_key(kind: str, norm: str, vocab: list[str], default_vocab: bool) -> str:
    if default_vocab:
        return norm
    h = hashlib.sha1("|".join(sorted(vocab)).encode("utf-8")).hexdigest()[:10]
    return f"{norm}#v{h}"


def _schema(vocab: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "label": {"type": "string", "enum": list(vocab) + [NONE_LABEL]},
            "confidence": {"type": "number"},
            "reason": {"type": "string"},
        },
        "required": ["label", "confidence", "reason"],
        "additionalProperties": False,
    }


_SYSTEM = (
    "You normalise free-text entries from farmers and food processors in West and Southern "
    "Africa and Canada for a life cycle assessment tool. You are given the kind of entry, "
    "the user's text, and a closed list of labels the tool understands. Pick the single "
    "label the user most plausibly meant, considering local trade names, French and local "
    "language terms, abbreviations and misspellings. If no label is a reasonable match, or "
    "the text names several different things, answer NONE. Report your confidence between "
    "0 and 1 that the label is what the user meant; be conservative when the text is vague. "
    "Give a one-sentence reason without any numbers. Never estimate quantities."
)


def classify(kind: str, text: str, vocabulary: list[str] | None = None, *,
             client: StructuredLLM | None = None, use_model: bool = True) -> dict:
    """Map `text` to one label of `kind`'s controlled vocabulary.

    Returns {"label": str|None, "confidence": float, "needs_confirmation": bool,
             "model": str, "cached": bool, "source": str[, "reason", "error"]}.
    `client` injects a model client (tests use fakes); default is the shared real client.
    """
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r}; expected one of {KINDS}")
    default_vocab = vocabulary is None
    vocab = list(vocabulary) if vocabulary is not None else list(VOCABULARIES[kind])
    if not vocab:
        raise ValueError("vocabulary is empty")
    norm = cache.normalise(text)
    if not norm:
        return _result(None, 0.0, "deterministic", False, "empty")

    det = _deterministic(kind, norm, vocab, default_vocab)
    if det:
        return det

    if llm_globally_disabled():
        return _result(None, 0.0, "deterministic", False, "disabled")

    cname = f"classify_{kind}"
    ckey = _cache_key(kind, norm, vocab, default_vocab)
    hit = cache.get(cname, ckey)
    if hit is not None:
        label = hit.get("label")
        if label is not None and label not in vocab:
            label = None
        return _result(label, hit.get("confidence", 0.0), hit.get("model", "cache"), True,
                       "cache", reason=hit.get("reason"))

    llm = client if client is not None else (get_client() if use_model else None)
    if llm is None:
        return _result(None, 0.0, "deterministic", False, "no_model")

    user = (f"Kind: {kind} ({_KIND_HELP[kind]})\n"
            f"User text: {text!r}\n"
            f"Allowed labels: {vocab}\n"
            f"Answer {NONE_LABEL} if none fits.")
    try:
        ans = llm.complete_json(system=_SYSTEM, user=user, schema=_schema(vocab),
                                max_tokens=2048, effort="low")
    except LLMError as e:
        return _result(None, 0.0, getattr(llm, "model", "unknown"), False, "error", error=str(e))

    raw_label = ans.get("label")
    label = raw_label if isinstance(raw_label, str) and raw_label in vocab else None
    conf = ans.get("confidence")
    try:
        conf = float(conf)
    except (TypeError, ValueError):
        conf = 0.0
    if label is None:
        conf = 0.0
    reason = ans.get("reason") if isinstance(ans.get("reason"), str) else None
    if reason:
        reason = re.sub(r"\d", "#", reason)[:300]  # rationale text carries no numbers
    model = getattr(llm, "model", "unknown")
    res = _result(label, conf, model, False, "model", reason=reason)
    cache.put(cname, ckey, {"text": norm, "kind": kind, "label": label,
                            "confidence": res["confidence"], "reason": reason, "model": model})
    return res
