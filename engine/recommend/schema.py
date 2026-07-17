#!/usr/bin/env python3
"""
schema.py - the abatement-measure record (record type 5) and its loader.

This is the typed store the recommendation layer draws numbers from. Every guard in
this file exists to defeat a documented failure mode of LLM-over-PDF systems
(RECOMMENDATION_ENGINE_PLAN.md §3): a measure with no provenance span, an effect with
an untyped unit, or a record with no freshness window is REJECTED at load time, not
silently used. A number that reaches a farmer must be traceable, unit-typed, and dated.

The store is JSONL: one measure per line, so records diff cleanly in review and can be
appended without touching the rest. Load with load_measures(); it raises
MeasureValidationError with the offending id + reason rather than loading a bad record.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Optional

_DEFAULT_LIBRARY = Path(__file__).resolve().parent / "measures.jsonl"
_DEFAULT_REVIEWS = Path(__file__).resolve().parent / "reviews.jsonl"


class MeasureValidationError(ValueError):
    """A measure record failed a structural guarantee (missing provenance, bad unit,
    no freshness window). The message names the record id and the specific failure."""


class EffectUnit(str, Enum):
    """How to read effect.value. Typed so the engine - never the model - does the
    arithmetic, and so a wrong-unit intermediate can't propagate silently."""

    # value is a signed fraction of the driver source's own impact in the target
    # category. -0.25 means "cut this fertiliser's climate impact by 25%".
    FRACTION_OF_DRIVER_IMPACT = "fraction_of_driver_impact"
    # value is a signed fraction of the whole category total.
    FRACTION_OF_CATEGORY_IMPACT = "fraction_of_category_impact"
    # value is an absolute figure per functional unit (kg product / kWh / etc.).
    ABSOLUTE_PER_UNIT = "absolute_per_unit"


class EffectBasis(str, Enum):
    """Where the effect size comes from. A modelled figure must never be presented as
    a measured one - this field is what lets the UI say so."""

    MEASURED = "measured"                 # observed in a field trial / survey
    MODELLED = "modelled"                 # EX-ACT / IPCC Tier calculation
    EXPERT_JUDGEMENT = "expert_judgement"  # extension guidance, no trial


class Horizon(str, Enum):
    """Answers 'over months or years?'. Drives the sequencing of a farmer's plan."""

    QUICK_WIN = "quick_win"    # < 3 months, typically no capital
    MEDIUM = "medium"          # 3-12 months
    STRATEGIC = "strategic"    # 1-3 years, usually capital + finance


@dataclass(frozen=True)
class Applicability:
    """Hard filters, evaluated BEFORE any ranking. This is what stops a UK measure
    reaching a Ghanaian farm (RECOMMENDATION_ENGINE_PLAN.md §3). Empty list / None on a
    dimension means 'unconstrained on that dimension' - the measure applies regardless."""

    regions: tuple[str, ...] = ()               # e.g. ("GH",); () = any region
    climate_zones: tuple[str, ...] = ()
    crops: tuple[str, ...] = ()                  # matched case-insensitively against food names
    systems: tuple[str, ...] = ()               # farm production systems
    scale_ha_min: Optional[float] = None
    scale_ha_max: Optional[float] = None
    prerequisites: tuple[str, ...] = ()          # human-readable flags checked by the matcher


@dataclass(frozen=True)
class Effect:
    value: float
    unit: EffectUnit
    basis: EffectBasis
    uncertainty_low: Optional[float] = None
    uncertainty_high: Optional[float] = None
    yield_effect: Optional[float] = None         # signed fraction; None = not quantified
    note: str = ""


@dataclass(frozen=True)
class Economics:
    """Currency and as_of are mandatory when any figure is present - a cost without a
    date is not usable in a 20%-inflation economy. price_refs point at live price
    records (dereferenced at runtime), never inlined."""

    capex: Optional[float] = None
    opex_delta: Optional[float] = None           # signed; negative = saving
    opex_per: str = ""                           # e.g. "ha/season"
    currency: Optional[str] = None
    as_of: Optional[str] = None                  # ISO date the figures were valid
    labour_delta_days_ha: Optional[float] = None
    price_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class Provenance:
    """NON-NULL by construction. source + span are required; a measure with no exact
    source span does not load. reviewed_by starts null and must be filled by a human
    before the measure is trusted in production (see is_reviewed)."""

    source: str
    span: str
    publication_date: Optional[str] = None
    citation: str = ""
    licence: str = ""
    extraction_confidence: Optional[float] = None
    reviewed_by: Optional[str] = None


@dataclass(frozen=True)
class AbatementMeasure:
    id: str
    title: str
    driver_kind: str                             # joins to input_matches[].kind
    driver_match: tuple[str, ...]                # substrings matched vs source names
    impact_category: str                         # frontend category name
    applicability: Applicability
    effect: Effect
    economics: Economics
    horizon: Horizon
    provenance: Provenance
    valid_from: str
    staleness_policy: str                        # biweekly|quarterly|seasonal|annual|assessment_cycle
    valid_until: Optional[str] = None
    action_detail: str = ""                      # one-line "what to actually do"
    requires_finance: bool = False               # from horizon.requires_finance in the library

    @property
    def is_reviewed(self) -> bool:
        return bool(self.provenance.reviewed_by)

    def is_fresh(self, as_of: Optional[date] = None) -> bool:
        """A stale record is EXCLUDED, not down-ranked. Embeddings can't detect
        recency, so freshness is a hard structural filter here."""
        if not self.valid_until:
            return True
        ref = as_of or _today()
        try:
            return _parse_date(self.valid_until) >= ref
        except ValueError:
            return True  # unparseable window -> don't silently drop; surface in review


def _today() -> date:
    # date.today() is unavailable under the workflow sandbox; callers that need
    # determinism pass as_of explicitly. In-process (FastAPI) this resolves normally.
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).date()


def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


# --- loading + validation ---------------------------------------------------------

_VALID_STALENESS = {"biweekly", "quarterly", "seasonal", "annual", "assessment_cycle"}


def _require(cond: bool, mid: str, why: str) -> None:
    if not cond:
        raise MeasureValidationError(f"measure '{mid}': {why}")


def _measure_from_dict(d: dict[str, Any]) -> AbatementMeasure:
    mid = d.get("id") or "<no id>"
    _require(d.get("type") == "abatement_measure", mid, "type must be 'abatement_measure'")
    for key in ("id", "title", "valid_from", "staleness_policy"):
        _require(bool(d.get(key)), mid, f"missing required field '{key}'")
    _require(d["staleness_policy"] in _VALID_STALENESS, mid,
             f"staleness_policy must be one of {sorted(_VALID_STALENESS)}")

    targets = d.get("targets") or {}
    _require(bool(targets.get("driver_kind")), mid, "targets.driver_kind is required")
    _require(bool(targets.get("impact_category")), mid, "targets.impact_category is required")

    eff = d.get("effect") or {}
    _require("value" in eff, mid, "effect.value is required")
    try:
        unit = EffectUnit(eff.get("unit"))
    except ValueError:
        raise MeasureValidationError(
            f"measure '{mid}': effect.unit '{eff.get('unit')}' is not a known EffectUnit")
    try:
        basis = EffectBasis(eff.get("basis"))
    except ValueError:
        raise MeasureValidationError(
            f"measure '{mid}': effect.basis '{eff.get('basis')}' is not a known EffectBasis")

    prov = d.get("provenance") or {}
    _require(bool(prov.get("source")), mid, "provenance.source is required (non-null)")
    _require(bool(prov.get("span")), mid,
             "provenance.span is required - a measure must quote its exact source, not paraphrase")

    try:
        horizon = Horizon(d.get("horizon", {}).get("band"))
    except ValueError:
        raise MeasureValidationError(
            f"measure '{mid}': horizon.band '{d.get('horizon', {}).get('band')}' is not a known Horizon")
    requires_finance = bool((d.get("horizon") or {}).get("requires_finance", False))

    ap = d.get("applicability") or {}
    scale = ap.get("scale_ha") or {}
    econ = d.get("economics") or {}

    def _num(v: Any) -> Optional[float]:
        """A figure may be a bare number or a {value, currency, per} object."""
        return v.get("value") if isinstance(v, dict) else v

    def _nested_currency() -> Optional[str]:
        for k in ("capex", "opex_delta"):
            v = econ.get(k)
            if isinstance(v, dict) and v.get("currency"):
                return v["currency"]
        return None

    # currency/as_of apply to every figure, so accept them at the economics level or
    # inline on capex/opex. as_of is always top-level.
    currency = econ.get("currency") or _nested_currency()
    as_of = econ.get("as_of")
    # economics is optional, but if any monetary figure is present, currency + as_of are required.
    has_econ_figure = any(_num(econ.get(k)) is not None for k in ("capex", "opex_delta"))
    if has_econ_figure:
        _require(bool(currency), mid, "economics needs a currency when a cost is given")
        _require(bool(as_of), mid, "economics needs an as_of date when a cost is given")

    return AbatementMeasure(
        id=d["id"],
        title=d["title"],
        driver_kind=targets["driver_kind"],
        driver_match=tuple(targets.get("driver_match") or ()),
        impact_category=targets["impact_category"],
        applicability=Applicability(
            regions=tuple(ap.get("regions") or ()),
            climate_zones=tuple(ap.get("climate_zones") or ()),
            crops=tuple(ap.get("crops") or ()),
            systems=tuple(ap.get("systems") or ()),
            scale_ha_min=scale.get("min"),
            scale_ha_max=scale.get("max"),
            prerequisites=tuple(ap.get("prerequisites") or ()),
        ),
        effect=Effect(
            value=float(eff["value"]),
            unit=unit,
            basis=basis,
            uncertainty_low=(eff.get("uncertainty_range") or {}).get("low"),
            uncertainty_high=(eff.get("uncertainty_range") or {}).get("high"),
            yield_effect=(eff.get("yield_effect") or {}).get("value"),
            note=eff.get("note", ""),
        ),
        economics=Economics(
            capex=_num(econ.get("capex")),
            opex_delta=_num(econ.get("opex_delta")),
            opex_per=(econ.get("opex_delta") or {}).get("per", "") if isinstance(econ.get("opex_delta"), dict) else "",
            currency=currency,
            as_of=as_of,
            labour_delta_days_ha=econ.get("labour_delta_days_ha"),
            price_refs=tuple(econ.get("price_refs") or ()),
        ),
        horizon=horizon,
        provenance=Provenance(
            source=prov["source"],
            span=prov["span"],
            publication_date=prov.get("publication_date"),
            citation=prov.get("citation", ""),
            licence=prov.get("licence", ""),
            extraction_confidence=prov.get("extraction_confidence"),
            reviewed_by=prov.get("reviewed_by"),
        ),
        valid_from=d["valid_from"],
        valid_until=d.get("valid_until"),
        staleness_policy=d["staleness_policy"],
        action_detail=d.get("action_detail", ""),
        requires_finance=requires_finance,
    )


_VALID_DECISIONS = {"approved", "rejected", "needs_changes"}


def load_reviews(path: Optional[Path] = None) -> dict[str, dict[str, Any]]:
    """Read the sign-off ledger (reviews.jsonl) and return {measure_id: latest_review}.

    The ledger is append-only: an agronomist adds a line per decision, so a measure can
    be reviewed more than once (e.g. rejected, then approved after a fix). Last line for a
    measure_id wins, which is what lets a re-review supersede an earlier decision. Missing
    file -> no reviews (every measure stays draft). A malformed line raises, because a
    silently-dropped sign-off is a safety hole, not a convenience."""
    p = path or _DEFAULT_REVIEWS
    latest: dict[str, dict[str, Any]] = {}
    if not p.exists():
        return latest
    with open(p, encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError as e:
                raise MeasureValidationError(f"{p.name}:{lineno}: invalid JSON: {e}") from e
            mid = r.get("measure_id")
            _require(bool(mid), mid or "<no id>", "review needs a measure_id")
            _require(bool(r.get("reviewer")), mid, "review needs a reviewer")
            _require(r.get("decision") in _VALID_DECISIONS, mid,
                     f"review decision must be one of {sorted(_VALID_DECISIONS)}")
            latest[mid] = r
    return latest


def load_measures(path: Optional[Path] = None,
                  reviews_path: Optional[Path] = None) -> list[AbatementMeasure]:
    """Load and validate every measure in the JSONL library, then apply the review
    ledger. Raises MeasureValidationError on the first bad record so a malformed measure
    can never reach the matcher. Blank lines and `# ...` comment lines are skipped.

    A measure with an 'approved' review gets provenance.reviewed_by stamped with the
    reviewer, which flips is_reviewed and lets it pass the production reviewed_only gate.
    Other decisions leave it draft."""
    p = path or _DEFAULT_LIBRARY
    reviews = load_reviews(reviews_path)
    measures: list[AbatementMeasure] = []
    seen: set[str] = set()
    with open(p, encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError as e:
                raise MeasureValidationError(f"{p.name}:{lineno}: invalid JSON: {e}") from e
            m = _measure_from_dict(d)
            if m.id in seen:
                raise MeasureValidationError(f"duplicate measure id '{m.id}' at {p.name}:{lineno}")
            seen.add(m.id)
            r = reviews.get(m.id)
            if r and r["decision"] == "approved" and not m.provenance.reviewed_by:
                by = f"{r['reviewer']} ({r.get('reviewed_at', '')})".strip()
                m = replace(m, provenance=replace(m.provenance, reviewed_by=by))
            measures.append(m)
    return measures
