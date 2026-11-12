"""
numbers.py: the "no invented numbers" guard for model-written text.

A model may phrase results, but every number it writes must already exist in the evidence
it was given (the grounding payload of an assessment, or the candidate list of an
adjudication), allowing only ordinary rounding. Sentences carrying a number that does not
trace to the evidence are removed before the text reaches a user, and are reported.

What counts as traceable for a number x written with k decimals / n significant digits:
  * |x - v| <= half a unit in the last written place, for some evidence value v (or |v|);
  * x equals v rounded to n significant figures (so 1,200 traces to 1234.5);
  * x written as a percentage equals 100 * v for a fraction v (0.42 -> 42%);
  * a bare count 0..10 with no unit or percent sign after it ("three inputs", "top 3");
  * a standard identifier directly after ISO / IPCC / EN / ISO/TS (ISO 14044, IPCC 2019).
Numbers glued to letters (CO2, N2O, PM2.5, m2a) are chemical or unit names, not values.
"""
from __future__ import annotations

import math
import re
from typing import Any, Iterable

_NUM_RE = re.compile(
    r"(?<![\w.])(?P<sign>[-−])?(?P<num>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)"
    r"(?P<exp>[eE][-+]?\d+)?(?![\w])"
)
_PERCENT_AFTER = re.compile(r"\s*(%|per\s?cent)", re.I)
_UNIT_AFTER = re.compile(
    r"\s*(%|per\s?cent|kg|g\b|t\b|tonnes?|tons?|l\b|litres?|liters?|mj|kwh|gj|ha\b|hectares?"
    r"|m2|m3|m²|m³|co2|µpt|upt|mpt|pt\b|points?|km|tkm|years?|days?|months?)", re.I)
_STANDARD_BEFORE = re.compile(r"(ISO(?:/TS)?|IPCC|EN|PAS|ILCD|AR)\s*$", re.I)


def _to_float(m: re.Match) -> float:
    s = m.group("num").replace(",", "")
    if m.group("exp"):
        s += m.group("exp")
    v = float(s)
    return -v if m.group("sign") else v


def _decimals(m: re.Match) -> int:
    num = m.group("num")
    if m.group("exp"):
        return 12  # explicit scientific notation: compare by significant figures only
    return len(num.split(".", 1)[1]) if "." in num else 0


def _sig_digits(m: re.Match) -> int:
    digits = m.group("num").replace(",", "").replace(".", "").lstrip("0")
    if "." not in m.group("num"):
        digits = digits.rstrip("0")
    return max(len(digits), 1)


def _round_sig(v: float, n: int) -> float:
    if v == 0:
        return 0.0
    return round(v, -int(math.floor(math.log10(abs(v)))) + (n - 1))


def find_numbers(text: str) -> list[dict]:
    """All numeric tokens in `text` with their value and context flags."""
    out = []
    for m in _NUM_RE.finditer(text or ""):
        tail = text[m.end():m.end() + 14]
        head = text[max(0, m.start() - 8):m.start()]
        out.append({
            "token": m.group(0), "value": _to_float(m), "start": m.start(), "end": m.end(),
            "decimals": _decimals(m), "sig": _sig_digits(m),
            "percent": bool(_PERCENT_AFTER.match(tail)),
            "has_unit": bool(_UNIT_AFTER.match(tail)),
            "standard": bool(_STANDARD_BEFORE.search(head)),
            "has_point": "." in m.group("num") or bool(m.group("exp")),
        })
    return out


def collect_evidence_numbers(obj: Any) -> list[float]:
    """Every number in a JSON-like structure, including numbers written inside strings."""
    vals: list[float] = []

    def walk(o: Any) -> None:
        if isinstance(o, bool) or o is None:
            return
        if isinstance(o, (int, float)):
            if math.isfinite(float(o)):
                vals.append(float(o))
        elif isinstance(o, str):
            vals.extend(n["value"] for n in find_numbers(o))
        elif isinstance(o, dict):
            for k, v in o.items():
                walk(k)
                walk(v)
        elif isinstance(o, (list, tuple, set)):
            for v in o:
                walk(v)

    walk(obj)
    return vals


def is_traceable(n: dict, evidence: Iterable[float]) -> bool:
    x = n["value"]
    if n["standard"]:
        return True
    if not n["has_point"] and not n["has_unit"] and 0 <= abs(x) <= 10 and float(x).is_integer():
        return True  # a bare count ("three", "top 3"), not a quantity
    half_unit = 0.5 * 10 ** (-n["decimals"]) if n["decimals"] < 12 else 0.0
    for v in evidence:
        cands = [v, abs(v)]
        if n["percent"]:
            cands += [v * 100.0, abs(v) * 100.0]
        for c in cands:
            if half_unit and abs(abs(x) - abs(c)) <= half_unit * (1 + 1e-9) + 1e-12:
                return True
            if c != 0 and math.isclose(abs(_round_sig(c, n["sig"])), abs(x), rel_tol=1e-9):
                return True
            if c == 0 and x == 0:
                return True
    return False


def untraceable_numbers(text: str, evidence: Iterable[float]) -> list[str]:
    ev = list(evidence)
    return [n["token"] for n in find_numbers(text) if not is_traceable(n, ev)]


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'*\-•])")


def guard_text(text: str, evidence: Iterable[float]) -> tuple[str, list[dict]]:
    """Remove every sentence that carries an untraceable number.

    Returns (clean_text, removed) where removed lists {"sentence", "numbers"}. Line breaks
    (paragraphs, bullets) are preserved; a line that loses all its sentences is dropped.
    """
    ev = list(evidence)
    removed: list[dict] = []
    out_lines = []
    for line in (text or "").split("\n"):
        if not line.strip():
            out_lines.append(line)
            continue
        kept = []
        for sent in _SENT_SPLIT.split(line):
            bad = untraceable_numbers(sent, ev)
            if bad:
                removed.append({"sentence": sent.strip(), "numbers": bad})
            else:
                kept.append(sent)
        if kept:
            out_lines.append(" ".join(kept))
    clean = re.sub(r"\n{3,}", "\n\n", "\n".join(out_lines)).strip()
    return clean, removed


def redact_untraceable(text: str, evidence: Iterable[float]) -> str:
    """Replace untraceable numbers in short free text (e.g. a rationale) with '[n]'."""
    ev = list(evidence)
    parts, last = [], 0
    for n in find_numbers(text or ""):
        if not is_traceable(n, ev):
            parts.append(text[last:n["start"]])
            parts.append("[n]")
            last = n["end"]
    parts.append((text or "")[last:])
    return "".join(parts)
