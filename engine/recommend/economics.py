#!/usr/bin/env python3
"""
economics.py - the feasibility screen: does a measure make economic sense for THIS farm,
and when does it pay back?

Given the matcher's ranked measures plus the farm's own quantities and the Ghana price
feed, this estimates annual revenue, annualises each measure's cost/saving, computes
payback, assigns an affordability tier, and sequences everything into a phased plan
(do-now / this-year / plan-ahead) - the concrete answer to "over months and years".

All of it is plain arithmetic. No model touches a number here; the recommendation layer
above only explains what this returns. Every estimate carries its assumptions and gaps
explicitly, because the inputs are sparse (a screening assessment rarely knows farm size,
season count, or available capital) and a confident wrong payback is worse than an honest
"insufficient data".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

try:
    from .matcher import MatchedMeasure, match_measures
    from .prices import PriceBook, PriceQuote, PRICE_UNIT
    from .schema import AbatementMeasure, Horizon
except ImportError:
    from matcher import MatchedMeasure, match_measures
    from prices import PriceBook, PriceQuote, PRICE_UNIT
    from schema import AbatementMeasure, Horizon

# Ghana smallholder cost tiers (GHS capex). Deliberately low-scale - this maps onto the
# existing Recommendation.cost_category vocabulary.
_TIER_BOUNDS = [(0, "NoCost"), (500, "LowCost"), (5000, "MediumCost"), (float("inf"), "HighCost")]

# A one-off capex is "self-affordable" if it's within this share of annual revenue;
# above it, the measure is flagged as needing finance. A documented heuristic, not a fact.
_AFFORDABLE_CAPEX_REVENUE_SHARE = 0.25

_QTY_RE = re.compile(r"\(([\d,]+(?:\.\d+)?)\s*kg\)", re.IGNORECASE)


# --- revenue ----------------------------------------------------------------------

@dataclass(frozen=True)
class RevenueLine:
    crop: str
    quantity_kg: float
    price_ghs_per_kg: Optional[float]
    revenue_ghs: Optional[float]
    price_source: str = ""
    priced: bool = True


@dataclass(frozen=True)
class RevenueEstimate:
    total_ghs: Optional[float]           # None when nothing could be priced
    lines: list[RevenueLine]
    currency: str = "GHS"
    basis: str = ""                      # "derived from prices" | "user-provided" | "unknown"
    unit_assumption: str = PRICE_UNIT
    priced_fraction: float = 0.0         # share of crops (by count) that got a price
    stale_prices: bool = False
    gaps: list[str] = field(default_factory=list)


def _quantities(payload: dict[str, Any]) -> list[tuple[str, float]]:
    """(crop_name, kg) pairs from the breakdown. Farm keys embed the qty as 'maize
    (1000kg)'; processing products carry output_kg in their value dict."""
    out: list[tuple[str, float]] = []
    for key, val in (payload.get("breakdown_by_food") or {}).items():
        name = key.split(" (")[0].strip()
        m = _QTY_RE.search(key)
        if name and m:
            out.append((name, float(m.group(1).replace(",", ""))))
    for name, val in (payload.get("breakdown_by_product") or {}).items():
        kg = (val or {}).get("output_kg") if isinstance(val, dict) else None
        if name and kg:
            out.append((name.split(" (")[0].strip(), float(kg)))
    return out


def estimate_annual_revenue(payload: dict[str, Any], pricebook: PriceBook, *,
                            region: Optional[str] = None, as_of: Optional[date] = None,
                            context: Optional[dict[str, Any]] = None) -> RevenueEstimate:
    """Estimate annual revenue as Σ(quantity × price). A user-supplied
    context['annual_revenue_ghs'] overrides the derivation (the honest, accurate path)."""
    ctx = context or {}
    if ctx.get("annual_revenue_ghs") is not None:
        return RevenueEstimate(total_ghs=float(ctx["annual_revenue_ghs"]), lines=[],
                               basis="user-provided", priced_fraction=1.0)

    qtys = _quantities(payload)
    if not qtys:
        return RevenueEstimate(total_ghs=None, lines=[], basis="unknown",
                               gaps=["no crop quantities in assessment"])

    lines: list[RevenueLine] = []
    total = 0.0
    priced = 0
    any_stale = False
    for name, kg in qtys:
        q = pricebook.price(name, region=region, as_of=as_of)
        if q is None:
            lines.append(RevenueLine(crop=name, quantity_kg=kg, price_ghs_per_kg=None,
                                     revenue_ghs=None, priced=False))
            continue
        rev = round(kg * q.price_ghs_per_kg, 2)
        total += rev
        priced += 1
        any_stale = any_stale or q.stale
        lines.append(RevenueLine(crop=name, quantity_kg=kg, price_ghs_per_kg=q.price_ghs_per_kg,
                                 revenue_ghs=rev, price_source=q.source))

    gaps: list[str] = []
    unpriced = [l.crop for l in lines if not l.priced]
    if unpriced:
        gaps.append(f"no price for: {', '.join(unpriced)}")
    if any_stale:
        gaps.append("prices are older than the SRID freshness window")

    return RevenueEstimate(
        total_ghs=round(total, 2) if priced else None,
        lines=lines,
        basis="derived from prices",
        priced_fraction=round(priced / len(qtys), 2),
        stale_prices=any_stale,
        gaps=gaps,
    )


# --- per-measure screen -----------------------------------------------------------

@dataclass
class ScreenedMeasure:
    matched: MatchedMeasure
    capex_ghs: Optional[float]
    annual_saving_ghs: Optional[float]   # signed: +ve = net saving/yr, -ve = net cost/yr,
                                         # None = not estimable (e.g. per-ha, no farm size)
    payback_months: Optional[float]      # only when capex > 0 AND there's a net saving
    cost_tier: str                       # NoCost | LowCost | MediumCost | HighCost
    affordability: str                   # affordable | needs_finance | unknown
    econ_gaps: list[str] = field(default_factory=list)

    @property
    def measure(self) -> AbatementMeasure:
        return self.matched.measure


def _annualise_opex(m: AbatementMeasure, size_ha: Optional[float],
                    seasons_per_year: float) -> tuple[Optional[float], list[str]]:
    """Return (annual opex delta GHS, gaps). Negative delta = a saving. None when the
    per-unit basis needs data we don't have (e.g. per-ha without a farm size)."""
    econ = m.economics
    if econ.opex_delta is None:
        return 0.0, []
    per = (econ.opex_per or "").lower()
    gaps: list[str] = []
    if "month" in per:
        return econ.opex_delta * 12.0, gaps
    if "ha" in per and "season" in per:
        if size_ha is None:
            return None, ["opex is per-hectare but farm size is unknown"]
        return econ.opex_delta * size_ha * seasons_per_year, gaps
    if "season" in per:
        return econ.opex_delta * seasons_per_year, gaps
    # unknown basis - treat the figure as already annual but flag it
    gaps.append(f"opex basis '{econ.opex_per}' assumed annual")
    return econ.opex_delta, gaps


def _cost_tier(capex: Optional[float]) -> str:
    c = capex or 0.0
    for bound, tier in _TIER_BOUNDS:
        if c <= bound:
            return tier
    return "HighCost"


def _affordability(capex: Optional[float], m: AbatementMeasure,
                   revenue: RevenueEstimate, context: dict[str, Any]) -> tuple[str, list[str]]:
    c = capex or 0.0
    if c <= 0:
        return "affordable", []
    cap = context.get("capital_available_ghs")
    if cap is not None:
        return ("affordable" if c <= float(cap) else "needs_finance"), []
    if revenue.total_ghs:
        share = c / revenue.total_ghs
        if share <= _AFFORDABLE_CAPEX_REVENUE_SHARE:
            return "affordable", []
        return "needs_finance", [f"capex is {share:.0%} of estimated annual revenue"]
    # no capital signal and no revenue estimate
    return ("needs_finance" if m.requires_finance else "unknown"), \
           ["no capital or revenue figure to judge affordability"]


def screen_measures(matched: list[MatchedMeasure], payload: dict[str, Any],
                    pricebook: PriceBook, *, revenue: Optional[RevenueEstimate] = None,
                    region: Optional[str] = None, as_of: Optional[date] = None,
                    context: Optional[dict[str, Any]] = None) -> list[ScreenedMeasure]:
    ctx = context or {}
    size_ha = ctx.get("farm_size_ha")
    seasons = float(ctx.get("seasons_per_year", 1))
    rev = revenue or estimate_annual_revenue(payload, pricebook, region=region,
                                             as_of=as_of, context=ctx)

    out: list[ScreenedMeasure] = []
    for mm in matched:
        m = mm.measure
        annual_opex, gaps = _annualise_opex(m, size_ha, seasons)
        capex = m.economics.capex
        # signed annual cashflow: a negative opex delta is a saving, a positive one a cost.
        # None only when the per-unit basis couldn't be resolved (e.g. per-ha, no size).
        annual_saving = (-annual_opex) if annual_opex is not None else None

        payback = None
        if capex and capex > 0 and annual_saving and annual_saving > 0:
            payback = round(capex / (annual_saving / 12.0), 1)

        afford, afgaps = _affordability(capex, m, rev, ctx)
        out.append(ScreenedMeasure(
            matched=mm,
            capex_ghs=capex,
            annual_saving_ghs=round(annual_saving, 2) if annual_saving is not None else None,
            payback_months=payback,
            cost_tier=_cost_tier(capex),
            affordability=afford,
            econ_gaps=gaps + afgaps,
        ))
    return out


# --- sequencing -------------------------------------------------------------------

_PHASES = [
    (Horizon.QUICK_WIN, "start_now", "Start now (this season)"),
    (Horizon.MEDIUM, "this_year", "Within a year"),
    (Horizon.STRATEGIC, "plan_ahead", "Plan ahead (1-3 years)"),
]


def build_action_plan(screened: list[ScreenedMeasure]) -> dict[str, Any]:
    """Group screened measures into a phased plan, preserving the matcher's within-phase
    impact ranking. This is the 'months and years' sequencing the brief asked for."""
    by_band: dict[Horizon, list[ScreenedMeasure]] = {}
    for s in screened:
        by_band.setdefault(s.measure.horizon, []).append(s)

    phases = []
    for band, key, label in _PHASES:
        items = by_band.get(band, [])
        if items:
            phases.append({"key": key, "label": label, "measures": items})
    return {"phases": phases}


# --- top-level convenience --------------------------------------------------------

@dataclass
class Recommendation:
    """The full result the /assess route will serialise: revenue estimate, screened +
    ranked measures, and the phased plan."""
    revenue: RevenueEstimate
    screened: list[ScreenedMeasure]
    plan: dict[str, Any]


def recommend(payload: dict[str, Any], *, pricebook: Optional[PriceBook] = None,
              region_code: Optional[str] = None, as_of: Optional[date] = None,
              reviewed_only: bool = False, commercial: bool = False,
              context: Optional[dict[str, Any]] = None,
              top_n: Optional[int] = None) -> Recommendation:
    """Run the whole deterministic pipeline: match hotspots -> measures, screen the
    economics, sequence into a plan. The LLM layer (Phase 3) explains this; it does not
    change any number in it."""
    pb = pricebook or PriceBook.load()
    matched = match_measures(payload, region_code=region_code, as_of=as_of,
                             reviewed_only=reviewed_only, commercial=commercial,
                             context=context, top_n=top_n)
    rev = estimate_annual_revenue(payload, pb, region=region_code, as_of=as_of, context=context)
    screened = screen_measures(matched, payload, pb, revenue=rev, region=region_code,
                               as_of=as_of, context=context)
    return Recommendation(revenue=rev, screened=screened, plan=build_action_plan(screened))
