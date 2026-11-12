"""
engine.llm: the intelligence layer. The model is used only where judgment is needed and a
deterministic rule is not enough, and it never supplies a number to the LCA.

  classify(kind, text, vocabulary=None)       free text -> controlled vocabulary label
  adjudicate(query, context, candidates)      pick one of the matcher's candidate uids or abstain
  numbers.guard_text(text, evidence_numbers)  strip sentences whose numbers are not in the evidence

Environment flags:
  GMG_LLM=0             no model calls at all (deterministic rules only, no cache)
  GMG_LLM_ADJUDICATE=0  no adjudication (classification unaffected)
  GMG_LLM_MODEL         model id override (default from client.DEFAULT_MODEL)
  GMG_LLM_CACHE_DIR     cache directory override (tests point this at a temp dir)
  GMG_LLM_LIVE=1        enables the optional live smoke test
"""
from .adjudicate import adjudicate, adjudication_disabled
from .classify import CONFIRM_THRESHOLD, classify
from .client import LLMError, get_client, has_api_key, llm_globally_disabled

__all__ = [
    "adjudicate", "adjudication_disabled", "classify", "CONFIRM_THRESHOLD",
    "LLMError", "get_client", "has_api_key", "llm_globally_disabled",
]
