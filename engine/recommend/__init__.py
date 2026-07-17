"""
recommend — the practical-action layer that sits on top of the LCA engine.

The ISO report answers "what is my footprint and is it defensible?". This package
answers "what do I do about it, what does it cost, and when does it pay back?" — by
matching the engine's per-source hotspot attribution against a curated library of
abatement measures.

Design rule (see docs/lca_engineer/RECOMMENDATION_ENGINE_PLAN.md §1): the LLM never
produces a number. Effect sizes, costs, and applicability live in a typed measure
library; matching and ranking are deterministic code; a model only explains and
personalises the already-correct result. This module is the deterministic half.
"""
from .schema import AbatementMeasure, EffectUnit, load_measures, MeasureValidationError
from .matcher import match_measures, MatchedMeasure
from .prices import PriceBook, PriceQuote, PRICE_UNIT
from .economics import (
    estimate_annual_revenue,
    screen_measures,
    build_action_plan,
    recommend,
    RevenueEstimate,
    ScreenedMeasure,
    Recommendation,
)
from .serialize import recommendation_to_dict, guidance_snippets

__all__ = [
    "AbatementMeasure",
    "EffectUnit",
    "load_measures",
    "MeasureValidationError",
    "match_measures",
    "MatchedMeasure",
    "PriceBook",
    "PriceQuote",
    "PRICE_UNIT",
    "estimate_annual_revenue",
    "screen_measures",
    "build_action_plan",
    "recommend",
    "RevenueEstimate",
    "ScreenedMeasure",
    "Recommendation",
    "recommendation_to_dict",
    "guidance_snippets",
]
