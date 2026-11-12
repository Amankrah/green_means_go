"""
ai_report_generator.py: plain-language and ISO 14044 narrative for a finished assessment,
grounded strictly in services.report_grounding.

History: the 2025 generator (removed in b1b470e, "sanity check") wrote long free-form
reports and could restate numbers it was never given. This rebuild keeps the model in an
interpreter role only:

  * input  : build_grounding_payload(assessment) and nothing else;
  * output : a fixed JSON shape (structured outputs), one string per section;
  * guard  : every number in every section must appear in the grounding payload, or be an
             ordinary rounding of one (engine.llm.numbers). Sentences with any other number
             are removed and listed in `numbers_removed`. If the guard removes too much,
             the model text is rejected and the deterministic template is returned instead.
  * offline: with GMG_LLM=0 or no key, the deterministic template (numbers copied straight
             from the payload) is returned, so the endpoint always answers.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.llm.client import LLMError, StructuredLLM, get_client  # noqa: E402
from engine.llm.numbers import collect_evidence_numbers, guard_text  # noqa: E402

try:  # imported as app package module (services.*) or via a repo-root path
    from services.report_grounding import AI_DISCLAIMER, GROUNDING_RULES, build_grounding_payload
except ImportError:  # pragma: no cover
    from app.services.report_grounding import AI_DISCLAIMER, GROUNDING_RULES, build_grounding_payload

STYLES = ("plain", "iso")

PLAIN_FIELDS = ("headline", "summary", "biggest_drivers", "what_you_can_do", "caveats")
ISO_FIELDS = ("goal_and_scope", "inventory_analysis", "impact_assessment", "interpretation",
              "limitations")

# Reject the model text if the guard strips more than this share of its characters.
MAX_REMOVED_SHARE = 0.35

_SYSTEM_COMMON = (
    GROUNDING_RULES + " "
    "Every number you write must be copied from the grounding JSON; you may round it. "
    "Do not calculate new numbers: no sums, differences, ratios, percentages or unit "
    "conversions that are not already in the JSON. Prefer words to numbers when unsure. "
    "Do not use em dashes. No markdown headings or tables."
)

_SYSTEM = {
    "plain": (
        "You explain a farm or food-processing life cycle assessment to its owner in plain, "
        "everyday language: short sentences, no jargon (explain any unavoidable term in a few "
        "words). Point to the owner's own figures: the single score and its band, the biggest "
        "contributors, and the practical recommendations listed in the grounding JSON. "
        "These are screening results pending independent review; say so once, gently. "
        + _SYSTEM_COMMON
    ),
    "iso": (
        "You draft the narrative sections of an ISO 14044 life cycle assessment report "
        "(goal and scope, life cycle inventory, impact assessment, interpretation, "
        "limitations) for a technical reader. Use precise LCA terminology, state the "
        "functional unit, system boundary, LCIA method and data sources exactly as given, "
        "and report results with their units. Mention limitations and data-quality notes "
        "that are present in the JSON; never add new ones. "
        + _SYSTEM_COMMON
    ),
}


def _schema(fields: tuple[str, ...]) -> dict:
    return {
        "type": "object",
        "properties": {f: {"type": "string"} for f in fields},
        "required": list(fields),
        "additionalProperties": False,
    }


def _fmt(v: Any) -> str:
    """Format a payload number to at most 4 significant figures (a rounding the guard accepts)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return str(v)
    if v == 0:
        return "0"
    if abs(v) >= 1000:
        return f"{round(v):,}"
    return f"{v:.4g}"


def _impact_lines(payload: dict, n: int = 3) -> list[str]:
    out = []
    for row in (payload.get("midpoint_impacts") or [])[:n]:
        if row.get("value") is None:
            continue
        unit = f" {row['unit']}" if row.get("unit") else ""
        out.append(f"{row.get('category')}: {_fmt(row['value'])}{unit}")
    return out


def _driver_lines(payload: dict, n: int = 3) -> list[str]:
    ca = payload.get("contribution_analysis") or {}
    out = []
    for row in (ca.get("by_source") or [])[:n]:
        if not isinstance(row, dict):
            continue
        src = row.get("source") or row.get("name") or row.get("input")
        if src:
            out.append(str(src))
    return out


def _rec_lines(payload: dict, n: int = 3) -> list[str]:
    out = []
    for r in (payload.get("recommendations") or [])[:n]:
        if isinstance(r, dict):
            t = r.get("title") or r.get("measure") or r.get("action") or r.get("name")
            if t:
                out.append(str(t))
        elif isinstance(r, str):
            out.append(r)
    return out


def template_narrative(payload: dict, style: str) -> dict[str, str]:
    """Deterministic narrative: every number is copied from the payload."""
    ss = payload.get("single_score") or {}
    who = payload.get("company_name") or payload.get("title") or "this assessment"
    impacts = _impact_lines(payload)
    drivers = _driver_lines(payload)
    recs = _rec_lines(payload)
    fu = payload.get("functional_unit")
    if style == "plain":
        score = ""
        if ss.get("value") is not None:
            score = f"The overall single score is {_fmt(ss['value'])} {ss.get('unit') or ''}".rstrip()
            score += f", in the '{ss['band']}' band." if ss.get("band") else "."
        return {
            "headline": f"Environmental footprint summary for {who}.",
            "summary": " ".join(x for x in [
                score,
                f"Results are expressed per {fu}." if fu else "",
                ("The largest midpoint results are " + "; ".join(impacts) + ".") if impacts else "",
            ] if x),
            "biggest_drivers": ("The biggest contributors are: " + ", ".join(drivers) + ".") if drivers
                               else "A breakdown by source was not quantified in this study.",
            "what_you_can_do": ("Suggested actions: " + "; ".join(recs) + ".") if recs
                               else "No specific actions were listed for this assessment.",
            "caveats": "These are screening results and a draft pending independent review.",
        }
    scope_bits = []
    if fu:
        scope_bits.append(f"Functional unit: {fu}.")
    if payload.get("boundary_included"):
        scope_bits.append(f"System boundary includes: {payload['boundary_included']}.")
    if payload.get("boundary_excluded"):
        scope_bits.append(f"Excluded: {payload['boundary_excluded']}.")
    if payload.get("lcia_method"):
        scope_bits.append(f"LCIA method: {payload['lcia_method']}.")
    matched = payload.get("input_matches") or []
    inv = (f"{len(matched)} purchased inputs were matched to background datasets: "
           + "; ".join(f"{m.get('input')} -> {m.get('matched')} ({m.get('source')}, {m.get('location')})"
                       for m in matched[:8]) + ".") if matched else \
        "No purchased inputs were matched to background datasets."
    return {
        "goal_and_scope": " ".join(scope_bits) or "Goal and scope were not stated in the grounding data.",
        "inventory_analysis": inv,
        "impact_assessment": ("Leading midpoint results: " + "; ".join(impacts) + ".") if impacts
                             else "Midpoint results were not available.",
        "interpretation": ("Main contributors: " + ", ".join(drivers) + ".") if drivers
                          else "A contribution analysis was not quantified in this study.",
        "limitations": "; ".join(str(x) for x in (payload.get("assumptions_and_limitations") or [])[:6])
                       or "Limitations are listed in the deterministic ISO report.",
    }


def _join(sections: dict[str, str], fields: tuple[str, ...]) -> str:
    return "\n\n".join(sections[f] for f in fields if sections.get(f))


def generate_narrative(assessment_data: dict, style: str = "plain", *,
                       client: Optional[StructuredLLM] = None, use_model: bool = True) -> dict:
    """Generate a grounded narrative for `assessment_data`.

    Raises services.report_grounding.MissingIsoReportError if the assessment has no
    iso_report. Returns {"style", "model", "sections", "text", "numbers_removed",
    "fallback", "disclaimer"}.
    """
    if style not in STYLES:
        raise ValueError(f"style must be one of {STYLES}")
    payload = build_grounding_payload(assessment_data)
    evidence = collect_evidence_numbers(payload)
    fields = PLAIN_FIELDS if style == "plain" else ISO_FIELDS

    llm = client if client is not None else (get_client() if use_model else None)
    model_used, fallback, reason = "deterministic-template", True, "model disabled or no API key"
    sections: dict[str, str] = {}
    removed: list[dict] = []

    if llm is not None:
        import json
        user = ("Grounding JSON for this assessment:\n"
                + json.dumps(payload, indent=1, default=str, ensure_ascii=False)
                + f"\n\nWrite the {'plain-language summary' if style == 'plain' else 'ISO 14044 report narrative'}"
                  " as the JSON object requested. Use only facts from the grounding JSON.")
        try:
            ans = llm.complete_json(system=_SYSTEM[style], user=user, schema=_schema(fields),
                                    max_tokens=16000, effort="medium")
            raw = {f: ans.get(f) if isinstance(ans.get(f), str) else "" for f in fields}
            total = sum(len(v) for v in raw.values()) or 1
            for f in fields:
                clean, rem = guard_text(raw[f], evidence)
                sections[f] = clean.replace(chr(0x2014), ", ")  # house style: no em dashes
                removed.extend({**r, "section": f} for r in rem)
            kept_share = sum(len(v) for v in sections.values()) / total
            if kept_share < 1 - MAX_REMOVED_SHARE or not any(sections.values()):
                reason = "model text rejected: too many untraceable numbers"
                sections = {}
            else:
                model_used, fallback, reason = getattr(llm, "model", "unknown"), False, None
        except LLMError as e:
            reason = f"model call failed: {e}"
            sections = {}

    if not sections:
        sections = template_narrative(payload, style)
        # the template only copies payload numbers; guard anyway so the invariant is uniform
        for f in fields:
            sections[f], rem = guard_text(sections.get(f, ""), evidence)
            removed.extend({**r, "section": f, "template": True} for r in rem)

    out = {
        "style": style,
        "model": model_used,
        "sections": sections,
        "text": _join(sections, fields),
        "numbers_removed": removed,
        "fallback": fallback,
        "disclaimer": AI_DISCLAIMER,
    }
    if reason:
        out["fallback_reason"] = reason
    return out
