#!/usr/bin/env python3
"""
matcher.py - deterministic hotspot -> measure matcher.

Consumes a saved assessment payload (the AssessmentResponse dict that lands in
Assessment.payload_json) and returns ranked candidate measures. No model, no
similarity search, no arithmetic on impact values beyond reading the shares the engine
already computed. This is the half of the recommendation layer that must be correct by
construction; the LLM layer only explains what this returns.

Matching is a funnel:
  1. HARD filters first - region, crop, system, scale, prerequisites - evaluated before
     any ranking (RECOMMENDATION_ENGINE_PLAN.md §3). A measure that fails a filter we can
     evaluate is dropped; a filter we cannot evaluate (data absent from the payload)
     passes and is recorded as a data_gap, because the payload is a screening artifact
     with known holes, and hard-failing on every missing field would return nothing.
  2. The measure must target a source that is actually a hotspot in this assessment.
  3. Survivors are ranked by (hotspot share x effect magnitude).

Effects are NEVER summed across measures - measure interactions are non-additive
(OECD 2015). v1 returns one measure per hotspot source.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

try:
    from .schema import AbatementMeasure, EffectUnit, load_measures
    from .licences import is_commercial_ok
except ImportError:  # allow running as a plain script from the package dir
    from schema import AbatementMeasure, EffectUnit, load_measures
    from licences import is_commercial_ok


# --- region resolution ------------------------------------------------------------

_REGION_ALIASES = {
    "ghana": "GH", "gh": "GH",
    "nigeria": "NG", "ng": "NG",
    "canada": "CA", "ca": "CA", "can": "CA",
    "global": "CA",  # processing API country for Canada
}


def _resolve_region(payload: dict[str, Any], override: Optional[str]) -> Optional[str]:
    if override:
        return override.upper()
    raw = (payload.get("region") or payload.get("country") or "").strip().lower()
    if not raw:
        return None
    if raw in _REGION_ALIASES:
        return _REGION_ALIASES[raw]
    # try the engine's own registry if importable (keeps this in step with regions.py)
    try:
        from regions import get_region  # type: ignore
        return get_region(raw).code
    except Exception:
        return raw.upper()[:2]


# --- payload extraction -----------------------------------------------------------

def _crops(payload: dict[str, Any]) -> set[str]:
    """Crop / product names from the breakdown, lowercased. Keys look like
    'maize (1000kg)' on the farm side and plain product names on the processing side."""
    out: set[str] = set()
    for block in ("breakdown_by_food", "breakdown_by_product"):
        for key in (payload.get(block) or {}):
            name = key.split(" (")[0].strip().lower()
            if name:
                out.add(name)
    return out


def _source_kinds(payload: dict[str, Any]) -> dict[str, str]:
    """Map each declared source name -> its kind, from input_matches. The synthetic
    on-farm source has no input_match, so field-driven measures match by name instead."""
    out: dict[str, str] = {}
    for m in (payload.get("input_matches") or []):
        name = (m.get("input") or "").strip()
        kind = (m.get("kind") or "").strip().lower()
        if name and kind:
            out[name] = kind
    return out


def _climate_shares(payload: dict[str, Any]) -> dict[str, float]:
    """source name -> fraction of climate impact, from the ISO contribution analysis
    (already ranked, per-kg). Falls back to computing shares from contribution_by_source
    if the ISO block is absent."""
    ca = (((payload.get("iso_report") or {}).get("interpretation") or {})
          .get("contribution_analysis") or {})
    rows = ca.get("by_source") or []
    if rows:
        return {(r.get("source") or "").strip(): float(r.get("share") or 0.0) for r in rows}

    # fallback: derive from contribution_by_source for the climate category
    cbs = payload.get("contribution_by_source") or {}
    vals: dict[str, float] = {}
    for src, cats in cbs.items():
        for cat, v in cats.items():
            if "climate" in cat.lower():
                vals[src] = abs(float((v or {}).get("value") or 0.0))
    total = sum(vals.values())
    if total <= 0:
        return {}
    return {s: v / total for s, v in vals.items()}


def _present_kinds(kinds: dict[str, str]) -> set[str]:
    return set(kinds.values())


def _prerequisite_state(flag: str, payload: dict[str, Any], kinds: dict[str, str],
                        crops: set[str]) -> Optional[bool]:
    """Return True (satisfied), False (definitely not), or None (unknown -> data_gap).
    We only return False when the payload gives us positive evidence of absence; most
    farm-structure flags aren't in the response and resolve to None."""
    present = _present_kinds(kinds)
    src_names = " ".join(kinds).lower() + " " + " ".join(payload.get("contribution_by_source") or {}).lower()

    if flag == "uses_fertilizers":
        return "fertiliser" in present or "fertilizer" in present
    if flag == "uses_pesticides":
        return "pesticide" in present
    if flag == "uses_machinery":
        return "fuel" in present
    if flag == "has_refrigeration" or flag == "generates_organic_waste":
        key = "refrigerant" if flag == "has_refrigeration" else "waste"
        return True if (key in present or key in src_names) else None
    if flag == "diesel_processing":
        return True if ("fuel" in present or "diesel" in src_names) else None
    # crop-implied processing flags are really enforced by the crop filter; treat as unknown here
    if flag in ("fish_smoking", "gari_processing", "drying_step", "irrigated_rice"):
        return None
    return None  # unknown flag -> don't block, surface as data_gap


# --- result -----------------------------------------------------------------------

@dataclass
class MatchedMeasure:
    measure: AbatementMeasure
    target_source: str          # the assessment source this measure acts on
    target_share: float         # that source's share of climate impact [0..1]
    score: float                # ranking score = share x |effect|
    data_gaps: list[str] = field(default_factory=list)  # filters we couldn't evaluate

    @property
    def id(self) -> str:
        return self.measure.id


# --- the matcher ------------------------------------------------------------------

def match_measures(payload: dict[str, Any], *, measures: Optional[list[AbatementMeasure]] = None,
                   region_code: Optional[str] = None, as_of: Optional[date] = None,
                   reviewed_only: bool = False, commercial: bool = False,
                   top_n: Optional[int] = None, min_share: float = 0.02,
                   context: Optional[dict[str, Any]] = None) -> list[MatchedMeasure]:
    """Return measures applicable to this assessment, ranked most-impactful first.

    reviewed_only=True drops measures no human has signed off (provenance.reviewed_by is
    null) - production callers should pass True; tests and previews may pass False.

    commercial=True drops measures whose source licence forbids commercial use as it
    stands (CC BY-NC, IPCC-permission-pending, or unconfirmed). Pass True for a commercial
    deployment so a licence-blocked measure can never reach a paying user.

    min_share drops measures whose target source contributes less than that fraction of
    climate impact (default 2%). This is what stops us recommending IPM to a farm whose
    pesticide impact rounds to zero.

    context lets a caller that holds the original request (e.g. the /assess route) supply
    farm structure the saved response omits - {"farm_size_ha": float, "system": str,
    "flags": {name: bool}} - so the scale/system/prerequisite filters become real instead
    of a recorded data gap. Omit it and those filters pass permissively as before.
    """
    lib = measures if measures is not None else load_measures()
    ctx = context or {}
    # A processing assessment keys its breakdown by product; a farm one by food. This
    # decides whether facility measures or farm measures apply, independent of whether the
    # caller supplied a `system`.
    is_processing = "breakdown_by_product" in payload
    region = _resolve_region(payload, region_code)
    crops = _crops(payload)
    kinds = _source_kinds(payload)
    present = _present_kinds(kinds)
    shares = _climate_shares(payload)
    size_ha = ctx.get("farm_size_ha")
    ctx_flags = ctx.get("flags") or {}

    # The library's `systems` is a production-practice axis (conventional/organic/
    # agroforestry/processing). A caller may hand us a value off a different axis - e.g.
    # the request's primary_farming_system uses market orientation (SemiCommercial,
    # Subsistence). Only treat the context system as a hard filter when it's actually in
    # the library vocabulary; otherwise it's a different axis we can't filter on, so leave
    # it as a data gap rather than silently dropping every measure.
    known_systems = {s for m in lib for s in m.applicability.systems}
    _sys = (ctx.get("system") or "").strip().lower() or None
    system = _sys if (_sys in known_systems) else None

    results: list[MatchedMeasure] = []

    for m in lib:
        if reviewed_only and not m.is_reviewed:
            continue
        if commercial and not is_commercial_ok(m.provenance.source):
            continue
        if not m.is_fresh(as_of):
            continue

        # --- HARD region filter ---
        ap = m.applicability
        if ap.regions and region and region not in ap.regions:
            continue

        gaps: list[str] = []

        # --- does this measure target a real hotspot source here? ---
        target_source, target_share = _find_target(m, kinds, present, shares)
        if target_source is None:
            continue
        if target_share < min_share:
            continue

        # --- crop filter (hard where we have crops) ---
        if ap.crops:
            if crops and not _any_match(ap.crops, crops):
                continue
            if not crops:
                gaps.append("crops not in payload")

        # --- prerequisites ---
        blocked = False
        for pre in ap.prerequisites:
            # a caller-supplied flag is authoritative; else infer from the payload
            if pre in ctx_flags:
                state: Optional[bool] = bool(ctx_flags[pre])
            else:
                state = _prerequisite_state(pre, payload, kinds, crops)
            if state is False:
                blocked = True
                break
            if state is None:
                gaps.append(f"prerequisite '{pre}' unverified")
        if blocked:
            continue

        # --- scale filter: hard when the caller supplied farm size, else a data gap ---
        if ap.scale_ha_min is not None or ap.scale_ha_max is not None:
            if size_ha is not None:
                if ap.scale_ha_min is not None and size_ha < ap.scale_ha_min:
                    continue
                if ap.scale_ha_max is not None and size_ha > ap.scale_ha_max:
                    continue
            else:
                gaps.append("farm size not in payload")

        # --- system filter ---
        # `systems` spans two axes at once: 'processing' marks a facility measure, and the
        # rest (conventional/organic/agroforestry) are farm production practices. Route by
        # what kind of assessment this is (derived from the payload, since the request's
        # `system` context is often absent), then refine on the farm practice when known.
        if ap.systems:
            sys_lower = {s.lower() for s in ap.systems}
            has_processing = "processing" in sys_lower
            has_farm = bool(sys_lower - {"processing"})
            if is_processing and not has_processing:
                continue  # farm-only measure on a processing assessment
            if not is_processing and not has_farm:
                continue  # facility-only measure on a farm assessment
            if not is_processing:
                if system is not None:
                    if not _any_match(ap.systems, {system}):
                        continue
                elif has_farm:
                    gaps.append("production system not in payload")

        score = round(target_share * abs(m.effect.value), 6)
        # the data-quality measure has zero effect; give it a tiny floor so it ranks last
        if m.effect.value == 0.0:
            score = 1e-9
        results.append(MatchedMeasure(measure=m, target_source=target_source,
                                      target_share=round(target_share, 4), score=score,
                                      data_gaps=gaps))

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:top_n] if top_n else results


def _find_target(m: AbatementMeasure, kinds: dict[str, str], present: set[str],
                 shares: dict[str, float]) -> tuple[Optional[str], float]:
    """Pick the assessment source this measure acts on, and its climate share. Prefer a
    kind match; fall back to a name-substring match (for field/name-driven measures).
    Returns the highest-share qualifying source, or (None, 0)."""
    dk = m.driver_kind.lower()
    candidates: list[tuple[str, float]] = []

    # every source that has a share (or a kind) is a matching candidate
    all_sources = set(shares) | set(kinds)
    for src in all_sources:
        sl = src.lower()
        kind = kinds.get(src, "")
        kind_ok = dk in ("any", "field") or (kind and kind == dk)
        name_ok = any(tok.lower() in sl for tok in m.driver_match) if m.driver_match else False
        if kind_ok or name_ok:
            candidates.append((src, shares.get(src, 0.0)))

    # "any" driver (the data-quality measure) attaches to the top hotspot overall
    if dk == "any" and not m.driver_match and shares:
        top = max(shares.items(), key=lambda kv: kv[1])
        return top[0], top[1]

    if not candidates:
        return None, 0.0
    best = max(candidates, key=lambda c: c[1])
    return best[0], best[1]


def _any_match(needles: tuple[str, ...], haystack: set[str]) -> bool:
    for n in needles:
        nl = n.lower()
        for h in haystack:
            if nl in h or h in nl:
                return True
    return False
