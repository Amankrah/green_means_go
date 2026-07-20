"""
contribution_sankey.py — top-N source ranking for GWP and land from contribution_by_source.

Used by the assessment adapter and research export; suitable for a simple Sankey or bar list
in the results UI without a charting library.
"""
from __future__ import annotations

from typing import Any, Mapping

GWP_CATEGORIES = ("Global warming", "Climate change")
LAND_CATEGORIES = ("Land use",)

SANKEY_CATEGORIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Global warming", GWP_CATEGORIES),
    ("Land use", LAND_CATEGORIES),
)


def _value_for_aliases(
    cats: Mapping[str, Any], aliases: tuple[str, ...]
) -> tuple[float, str | None]:
    for alias in aliases:
        entry = cats.get(alias)
        if isinstance(entry, dict):
            return float(entry.get("value") or 0.0), entry.get("unit")
        if isinstance(entry, (int, float)):
            return float(entry), None
    return 0.0, None


def _rank_sources(
    contribution_by_source: Mapping[str, Any],
    *,
    display_category: str,
    aliases: tuple[str, ...],
    top_n: int,
) -> dict[str, Any]:
    rows: list[tuple[str, float, str | None]] = []
    for source, cats in (contribution_by_source or {}).items():
        if not isinstance(cats, dict):
            continue
        value, unit = _value_for_aliases(cats, aliases)
        if value > 0:
            rows.append((source, value, unit))

    rows.sort(key=lambda r: (-r[1], r[0]))
    total = sum(v for _, v, _ in rows)
    unit = next((u for _, _, u in rows if u), None)

    top = rows[:top_n]
    other_value = sum(v for _, v, _ in rows[top_n:])

    sources = []
    for rank, (source, value, _) in enumerate(top, start=1):
        sources.append(
            {
                "rank": rank,
                "source": source,
                "value": value,
                "share": (value / total) if total else 0.0,
            }
        )

    out: dict[str, Any] = {
        "category": display_category,
        "unit": unit,
        "total": total,
        "sources": sources,
    }
    if other_value > 0:
        out["other"] = {
            "value": other_value,
            "share": other_value / total if total else 0.0,
            "source_count": len(rows) - top_n,
        }
    return out


def build_contribution_sankey(
    contribution_by_source: Mapping[str, Any] | None,
    *,
    top_n: int = 3,
) -> dict[str, Any]:
    """Rank top sources per impact category for Sankey-style visualization."""
    cbs = contribution_by_source or {}
    categories = {
        display: _rank_sources(
            cbs, display_category=display, aliases=aliases, top_n=top_n
        )
        for display, aliases in SANKEY_CATEGORIES
    }
    return {"top_n": top_n, "categories": categories}
