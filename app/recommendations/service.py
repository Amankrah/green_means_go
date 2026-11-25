"""
recommendations/service.py - bridge between a saved assessment and the deterministic
recommendation engine (engine/recommend).

It pulls the farm/facility context the *response* payload drops (farm size, production
system, practice flags) out of the archived *request*, runs the deterministic pipeline,
and serialises the result. No LLM here - every number is produced by engine/recommend and
is correct by construction. The chat layer explains this output; it never changes it.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional

from engine.recommend import recommend, recommendation_to_dict, guidance_snippets
from engine.recommend.prices import PriceBook

# Production posture: only signed-off measures reach users. The v1 library was team-
# reviewed and approved on 2026-07-17 (see engine/recommend/reviews.jsonl), so this now
# defaults ON. Any measure added later stays invisible until it too has an 'approved'
# entry in the ledger. Set the env var to "0" only for a preview that wants draft measures.
_REVIEWED_ONLY = os.getenv("RECOMMENDATIONS_REVIEWED_ONLY", "1") == "1"

# Set to "1" for a commercial deployment: drops measures whose source licence forbids
# commercial use as it stands (CC BY-NC, IPCC-permission-pending, unconfirmed). See
# engine/recommend/licences.py and docs/lca_engineer/LICENCES.md.
_COMMERCIAL = os.getenv("RECOMMENDATIONS_COMMERCIAL", "0") == "1"

# The price book is process-wide and read-only; load it once.
_PRICEBOOK: Optional[PriceBook] = None


def _pricebook() -> PriceBook:
    global _PRICEBOOK
    if _PRICEBOOK is None:
        _PRICEBOOK = PriceBook.load()
    return _PRICEBOOK


def _api_request(request_json: Optional[dict]) -> dict:
    """The archived request is {"api": <model_dump>, "form": <snapshot>}. Return the api
    half, or {} if no request was archived (older rows)."""
    if not request_json:
        return {}
    return request_json.get("api") or {}


def _farm_context(api: dict) -> dict[str, Any]:
    """Farm size, production system, and practice flags for the matcher/screen. Absent
    fields simply don't appear - the pipeline treats them as data gaps, not failures."""
    ctx: dict[str, Any] = {}
    fp = api.get("farm_profile") or {}
    if fp.get("total_farm_size") is not None:
        ctx["farm_size_ha"] = fp["total_farm_size"]

    # production practice axis (conventional/organic/agroforestry) comes off the foods,
    # NOT farm_profile.primary_farming_system (which is market orientation, a different
    # axis the matcher deliberately treats as off-vocabulary).
    foods = api.get("foods") or []
    for food in foods:
        ps = food.get("production_system")
        if ps:
            ctx["system"] = ps
            break

    seasons = _seasons_per_year(foods)
    if seasons is not None:
        ctx["seasons_per_year"] = seasons

    mp = api.get("management_practices") or {}
    flags: dict[str, bool] = {}
    fert = mp.get("fertilization") or {}
    if fert.get("uses_fertilizers") is not None:
        rows = fert.get("fertilizer_applications") or []
        # Rows of type "None" are placeholders the engine skips; with rows present, the
        # flag holds only if one is a real application.
        flags["uses_fertilizers"] = bool(fert["uses_fertilizers"]) and (not rows or any(
            str(a.get("fertilizer_type") or "").strip().lower() != "none"
            and (a.get("application_rate") or 0) > 0
            and (a.get("applications_per_season") or 0) > 0
            for a in rows))
    pest = mp.get("pest_management") or {}
    if pest.get("pesticides"):
        flags["uses_pesticides"] = True
    if pest.get("uses_ipm") is not None:
        flags["uses_ipm"] = bool(pest["uses_ipm"])
    irrigated_rice = _irrigated_rice(foods, mp.get("water_management") or {})
    if irrigated_rice is not None:
        flags["irrigated_rice"] = irrigated_rice
    ee = api.get("equipment_energy") or {}
    if ee.get("fuel_consumption") or ee.get("equipment"):
        flags["uses_machinery"] = True
    if flags:
        ctx["flags"] = flags
    practices = _adopted_practices(foods, mp)
    if practices:
        # The matcher drops measures for these (engine/recommend/matcher.py
        # ADOPTED_PRACTICE_STEMS): a farm is never told to adopt what it already does.
        ctx["practices_adopted"] = practices
    return ctx


def _is_rice(food: dict) -> bool:
    return "rice" in (food.get("name") or "").lower()


def _seasons_per_year(foods: list[dict]) -> Optional[float]:
    """Area-weighted crops_per_year (economics multiplies per-ha-per-season opex by it).
    Falls back to the max when no crop has an area; None when no crop states it (archived
    requests), so economics keeps its own default."""
    rows = [(f.get("crops_per_year"), f.get("area_allocated")) for f in foods]
    rows = [(float(c), a) for c, a in rows if c]
    if not rows:
        return None
    weighted = [(c, float(a)) for c, a in rows if a]
    total_area = sum(a for _, a in weighted)
    if total_area > 0:
        return sum(c * a for c, a in weighted) / total_area
    return max(c for c, _ in rows)


def _irrigated_rice(foods: list[dict], water: dict) -> Optional[bool]:
    """True/False only with positive evidence. A rice crop's declared water_regime wins
    over the farm-wide irrigation system."""
    rice = [f for f in foods if _is_rice(f)]
    if not rice:
        return None
    regimes = [f.get("water_regime") for f in rice if f.get("water_regime")]
    if regimes:
        return any(str(r).startswith("irrigated_") for r in regimes)
    irr = (water.get("irrigation_system") or "").lower()
    if irr and "none" not in irr and "rainfed" not in irr:
        return True
    return None


def _adopted_practices(foods: list[dict], mp: dict) -> list[str]:
    soil = mp.get("soil_management") or {}
    cons = " ".join(str(p) for p in (soil.get("conservation_practices") or [])).lower()
    out: list[str] = []
    if "no-till" in cons or "no till" in cons or "zero till" in cons:
        out.append("no_till")
    elif "minimum" in cons or "reduced till" in cons:
        out.append("reduced_tillage")
    if "mulch" in cons:
        out.append("mulching")
    if soil.get("cover_crops"):
        out.append("cover_crops")
    if any(f.get("water_regime") == "irrigated_multiple_drainage" for f in foods if _is_rice(f)):
        out.append("awd")
    fert = mp.get("fertilization") or {}
    methods = {a.get("application_method") for a in (fert.get("fertilizer_applications") or [])}
    if methods & {"band_placement", "incorporated", "side_dressing"}:
        out.append("placed_fertiliser")
    if any((a.get("applications_per_season") or 0) >= 2
           for a in (fert.get("fertilizer_applications") or [])
           if str(a.get("fertilizer_type") or "").strip().lower() != "none"):
        out.append("split_application")
    return out


def _processing_context(api: dict) -> dict[str, Any]:
    """Practice flags for a processing facility, inferred from operations + products."""
    flags: dict[str, bool] = {}
    ops = api.get("processing_operations") or {}
    energy = ops.get("energy_management") or {}
    fuel = (energy.get("fuel_type") or "").lower()
    if energy.get("monthly_fuel_consumption") or fuel:
        flags["uses_machinery"] = True
        if "diesel" in fuel:
            flags["diesel_processing"] = True
    refr = ops.get("refrigerant_management") or {}
    if refr.get("annual_leakage_kg") or refr.get("refrigerant_type"):
        flags["has_refrigeration"] = True
    waste = ops.get("waste_management") or {}
    if (waste.get("organic_waste_percentage") or 0) > 0 or waste.get("solid_waste_generation"):
        flags["generates_organic_waste"] = True
    # drying/smoking are product/facility-shaped; the crop filter does the real gating,
    # so we assert the permissive flags rather than guess hard falses.
    ftype = (api.get("facility_profile") or {}).get("facility_type", "").lower()
    if "fish" in ftype:
        flags["fish_smoking"] = True
    if "cassava" in ftype:
        flags["gari_processing"] = True
    flags["drying_step"] = True  # most processing has a drying/dewatering step
    # Hard-filter the library to processing measures so farm practices never surface here.
    return {"system": "processing", "flags": flags}


def build_recommendations(payload: dict, request_json: Optional[dict], *,
                          is_processing: bool = False,
                          region_code: Optional[str] = None) -> dict:
    """Run the deterministic pipeline for one saved assessment and return the API dict."""
    api = _api_request(request_json)
    context = _processing_context(api) if is_processing else _farm_context(api)
    rec = recommend(
        payload,
        pricebook=_pricebook(),
        region_code=region_code,
        reviewed_only=_REVIEWED_ONLY,
        commercial=_COMMERCIAL,
        context=context,
    )
    return recommendation_to_dict(
        rec,
        assessment_id=payload.get("id"),
        generated_at=datetime.now(timezone.utc).isoformat(),
        is_processing=is_processing,
    )


def guidance_for_chat(payload: dict, *, limit: int = 4) -> list[str]:
    """Short, cited guidance lines for the chat RAG seam. Assessment-driven (not
    query-driven), so it's stable across a conversation's turns and doesn't break the
    prompt cache. Returns [] on any failure - chat must never break because the
    recommender did."""
    try:
        is_proc = "breakdown_by_product" in payload
        rec = recommend(payload, pricebook=_pricebook(), reviewed_only=_REVIEWED_ONLY,
                        commercial=_COMMERCIAL,
                        context=(_processing_context({}) if is_proc else None))
        return guidance_snippets(rec, limit=limit)
    except Exception:
        return []
