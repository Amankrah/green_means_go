"""
adjudicate.py: let the model choose between close background-dataset candidates.

Called by the matcher (WS4 wires it into engine/orchestrator.py) when the embedding
matcher's top candidates are close in score or cross product families. The model sees the
user's query, the assessment context (region, input kind, unit, amount description) and
the candidate datasets, and may only:
  * return one of the given uids (enforced by a JSON-schema enum, then re-checked here), or
  * abstain (None), in which case the matcher keeps its own deterministic choice.

It never supplies a factor, an amount or a dataset of its own: the returned uid is looked
up in the canonical store by the caller, and the amount stays the user's.

Disabled (no model call) when GMG_LLM_ADJUDICATE=0 or GMG_LLM=0 or no API key is set.
With the flags at 0 the cache is not consulted either, so a GMG_LLM=0 run is the pure
deterministic baseline. Without a key, committed cache entries are still served so a
case study reproduces offline exactly as it ran online.
Cache key: (normalised query, sorted candidate uids, region).
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Optional

from . import cache
from .client import LLMError, StructuredLLM, get_client, llm_globally_disabled
from .numbers import collect_evidence_numbers, redact_untraceable

ABSTAIN = "ABSTAIN"
CACHE_NAME = "adjudicate"
_MAX_CANDIDATES = 12

_SYSTEM = (
    "You are an LCA practitioner choosing the background dataset that best represents a "
    "purchased input in a cradle-to-gate agricultural or food-processing inventory. You get "
    "the user's description, the assessment context and a short list of candidate datasets "
    "(ecoinvent 3.11 or AGRIBALYSE 3.2) found by an embedding matcher. Choose the candidate "
    "whose reference product is the same good or service the user bought, at the right "
    "life-cycle stage (for example a market or production dataset for a purchased material, "
    "not a treatment or a by-product), in the reference unit the amount is given in, and "
    "with the closest geography to the region (same country, then continent, then RoW / GLO). "
    "Product identity outranks geography. If no candidate is a defensible representation, "
    "answer ABSTAIN. Do not invent datasets, factors or quantities. Write a rationale of at "
    "most two sentences that cites the candidate's name, product, location or unit."
)


def adjudication_disabled() -> bool:
    return llm_globally_disabled() or os.getenv("GMG_LLM_ADJUDICATE", "").strip() == "0"


def _cache_key(query: str, candidates: list[dict], region: Optional[str]) -> tuple[str, dict]:
    norm = cache.normalise(query)
    uids = sorted(str(c.get("uid")) for c in candidates)
    reg = (region or "").upper()
    raw = json.dumps([norm, uids, reg], separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24], {"query": norm, "uids": uids, "region": reg}


def _region_of(context: dict) -> Optional[str]:
    for k in ("region", "region_code", "country"):
        v = (context or {}).get(k)
        if v:
            return str(v)
    return None


def _schema(uids: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "choice": {"type": "string", "enum": list(uids) + [ABSTAIN]},
            "rationale": {"type": "string"},
        },
        "required": ["choice", "rationale"],
        "additionalProperties": False,
    }


def _clean_candidates(candidates: list[dict]) -> list[dict]:
    out, seen = [], set()
    for c in candidates or []:
        if not isinstance(c, dict) or not c.get("uid"):
            continue
        uid = str(c["uid"])
        if uid in seen:
            continue
        seen.add(uid)
        out.append({
            "uid": uid,
            "name": c.get("name"),
            "reference_product": c.get("reference_product"),
            "location": c.get("location"),
            "source": c.get("source"),
            "ref_unit": c.get("ref_unit"),
            "score": c.get("score"),
        })
    return out[:_MAX_CANDIDATES]


def adjudicate(query: str, context: dict, candidates: list[dict], *,
               client: StructuredLLM | None = None) -> dict | None:
    """Pick one candidate uid, or None to abstain / when disabled.

    candidates: [{uid, name, reference_product, location, source, ref_unit, score}, ...]
    returns   : {"uid": str, "rationale": str, "model": str} or None.
    The returned uid is always one of the given candidate uids.
    """
    if adjudication_disabled():
        return None
    cands = _clean_candidates(candidates)
    if len(cands) < 2:
        return None  # nothing to choose between
    valid = {c["uid"] for c in cands}
    context = dict(context or {})
    region = _region_of(context)
    key, meta = _cache_key(query, cands, region)

    hit = cache.get(CACHE_NAME, key)
    if hit is not None:
        uid = hit.get("uid")
        if uid is None or uid not in valid:
            return None
        return {"uid": uid, "rationale": hit.get("rationale") or "", "model": hit.get("model", "cache"),
                "cached": True}

    llm = client if client is not None else get_client()
    if llm is None:
        return None

    evidence = {"query": query, "context": context, "candidates": cands}
    user = ("Purchased input as described by the user: " + json.dumps(query) + "\n"
            "Assessment context: " + json.dumps(context, default=str) + "\n"
            "Candidates (choose by uid):\n" + json.dumps(cands, indent=1, default=str))
    try:
        ans = llm.complete_json(system=_SYSTEM, user=user, schema=_schema(sorted(valid)),
                                max_tokens=4096, effort="low")
    except LLMError:
        return None

    choice = ans.get("choice")
    model = getattr(llm, "model", "unknown")
    rationale = ans.get("rationale") if isinstance(ans.get("rationale"), str) else ""
    # Rationale text may only repeat numbers that are in the evidence (scores, units...).
    rationale = redact_untraceable(rationale, collect_evidence_numbers(evidence))[:600]
    uid = choice if isinstance(choice, str) and choice in valid else None
    cache.put(CACHE_NAME, key, {**meta, "uid": uid, "rationale": rationale, "model": model})
    if uid is None:
        return None
    return {"uid": uid, "rationale": rationale, "model": model, "cached": False}
