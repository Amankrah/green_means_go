#!/usr/bin/env python3
"""
prices.py — the Ghana commodity price feed (MoFA SRID), loaded into a queryable book.

This is the revenue side of the economic screen. It answers price(commodity) -> GHS/kg
so the recommender can estimate a farm's annual revenue from the quantities the
assessment already carries, then judge whether a measure's cost is affordable.

Two honesty constraints, both from RECOMMENDATION_ENGINE_PLAN.md:

  1. UNIT ASSUMPTION. The SRID export has a bare "Price" column with no unit. We assume
     GHS per kilogram (the dominant convention for these retail/wholesale staple series)
     and surface that assumption on every quote, because a wrong unit scales every
     revenue estimate silently — the exact failure mode the plan flags (unit errors).

  2. FRESHNESS. The gathered file spans Jul-Oct 2025. A price has a date; a quote carries
     a `stale` flag vs the caller's as_of and the feed's own biweekly policy. Embeddings
     can't detect staleness, so it's a structural field here, never inferred.

Farmgate note: even wholesale overstates true farmgate revenue (it includes the trader
margin). We prefer wholesale over retail as the closer proxy and label which was used.
"""
from __future__ import annotations

import csv
import statistics
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

# The SRID file lives under the untracked data/ tree; resolve from repo root but never
# hard-fail if it's absent (a deployment may not ship it) — an empty book degrades to
# "no price data" rather than crashing the recommender.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CSV = _REPO_ROOT / "data" / "recommendations" / "Tier1" / "Commodity prices _04.11.25.csv"

PRICE_UNIT = "GHS/kg (assumed — SRID export carries no unit column)"
_STALE_AFTER_DAYS = 30  # SRID is biweekly; a quote older than this is flagged stale


@dataclass(frozen=True)
class PriceQuote:
    commodity: str              # the query term, echoed back
    matched_commodity: str      # the SRID commodity the price came from
    price_ghs_per_kg: float     # median across matching rows
    source: str                 # "wholesale" | "retail" | "mixed"
    n_obs: int                  # how many rows backed the median
    unit: str = PRICE_UNIT
    latest_date: Optional[str] = None
    stale: bool = False
    note: str = ""


@dataclass(frozen=True)
class _Row:
    commodity_norm: str
    commodity_raw: str
    price: float
    source: str                 # retail | wholesale
    region: str
    day: Optional[date]


def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def _parse_day(s: str) -> Optional[date]:
    # SRID has both dd-mm-yyyy (the 'date' col) and yyyy-mm-dd (the 'market_day' col).
    for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            from datetime import datetime
            return datetime.strptime((s or "").strip(), fmt).date()
        except ValueError:
            continue
    return None


class PriceBook:
    """An in-memory index of commodity -> price rows. Query with price()."""

    def __init__(self, rows: list[_Row]):
        self._by_commodity: dict[str, list[_Row]] = {}
        for r in rows:
            self._by_commodity.setdefault(r.commodity_norm, []).append(r)
        self._all_norms = list(self._by_commodity)
        self.n_rows = len(rows)
        self.latest_day = max((r.day for r in rows if r.day), default=None)

    # --- loading ------------------------------------------------------------------

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "PriceBook":
        p = path or _DEFAULT_CSV
        rows: list[_Row] = []
        if not p.exists():
            return cls(rows)  # empty book — callers see "no price data", not a crash
        with open(p, encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            for raw in reader:
                commodity = (raw.get("commodity") or "").strip()
                price_s = (raw.get("Price") or "").strip()
                if not commodity or not price_s:
                    continue
                try:
                    price = float(price_s)
                except ValueError:
                    continue
                if price <= 0:
                    continue
                src = _norm(raw.get("source") or raw.get("Type") or "")
                if src not in ("retail", "wholesale"):
                    continue  # skip the 61 malformed/shifted rows
                rows.append(_Row(
                    commodity_norm=_norm(commodity),
                    commodity_raw=commodity,
                    price=price,
                    source=src,
                    region=_norm(raw.get("region") or ""),
                    day=_parse_day(raw.get("date") or raw.get("market_day") or ""),
                ))
        return cls(rows)

    # --- query --------------------------------------------------------------------

    def price(self, commodity: str, *, region: Optional[str] = None,
              as_of: Optional[date] = None, prefer: str = "wholesale") -> Optional[PriceQuote]:
        """Median GHS/kg for a commodity. Matches the query name to SRID commodities
        exactly first, then by substring either way ('maize' -> 'white maize'). Prefers
        wholesale rows (closer to farmgate); falls back to retail. Optionally scoped to a
        Ghana admin region. Returns None if nothing matches."""
        want = _norm(commodity)
        if not want:
            return None

        matched = self._match_rows(want)
        if not matched:
            return None
        if region:
            rnorm = _norm(region)
            scoped = [r for r in matched if r.region == rnorm]
            matched = scoped or matched  # fall back to national if region has no rows

        rows = [r for r in matched if r.source == prefer] or matched
        used_source = prefer if any(r.source == prefer for r in matched) else "retail"
        if len({r.source for r in rows}) > 1:
            used_source = "mixed"

        prices = [r.price for r in rows]
        latest = max((r.day for r in rows if r.day), default=None)
        stale = False
        if latest is not None:
            ref = as_of or _today()
            stale = (ref - latest).days > _STALE_AFTER_DAYS

        # pick the SRID name that contributed most rows, for transparency
        from collections import Counter
        matched_name = Counter(r.commodity_raw for r in rows).most_common(1)[0][0]

        return PriceQuote(
            commodity=commodity,
            matched_commodity=matched_name,
            price_ghs_per_kg=round(statistics.median(prices), 4),
            source=used_source,
            n_obs=len(prices),
            latest_date=latest.isoformat() if latest else None,
            stale=stale,
            note="wholesale proxy for farmgate; overstates true farm-gate revenue"
                 if used_source == "wholesale" else "",
        )

    def _match_rows(self, want: str) -> list[_Row]:
        if want in self._by_commodity:
            return self._by_commodity[want]
        # substring either direction, but guard against 1-2 char noise
        out: list[_Row] = []
        for norm, rows in self._by_commodity.items():
            if len(want) >= 3 and (want in norm or norm in want):
                out.extend(rows)
        return out


def _today() -> date:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).date()
