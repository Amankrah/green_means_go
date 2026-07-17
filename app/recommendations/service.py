"""
recommendations/service.py — bridge between a saved assessment and the deterministic
recommendation engine (engine/recommend).

It pulls the farm/facility context the *response* payload drops (farm size, production
system, practice flags) out of the archived *request*, runs the deterministic pipeline,
and serialises the result. No LLM here — every number is produced by engine/recommend and
is correct by construction. The chat layer explains this output; it never changes it.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional

from engine.recommend import recommend, recommendation_to_dict, guidance_snippets
from engine.recommend.prices import PriceBook

# The v1 measure library is unreviewed. Until an agronomist signs measures off, we still
# surface them (badged as draft) so the feature is usable — flip this to "1" once the
# reviewed_by gate is populated and only signed-off measures should reach users.
_REVIEWED_ONLY = os.getenv("RECOMMENDATIONS_REVIEWED_ONLY", "0") == "1"

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
    fields simply don't appear — the pipeline treats them as data gaps, not failures."""
    ctx: dict[str, Any] = {}
    fp = api.get("farm_profile") or {}
    if fp.get("total_farm_size") is not None:
        ctx["farm_size_ha"] = fp["total_farm_size"]

    # production practice axis (conventional/organic/agroforestry) comes off the foods,
    # NOT farm_profile.primary_farming_system (which is market orientation, a different
    # axis the matcher deliberately treats as off-vocabulary).
    for food in api.get("foods") or []:
        ps = food.get("production_system")
        if ps:
            ctx["system"] = ps
            break

    mp = api.get("management_practices") or {}
    flags: dict[str, bool] = {}
    fert = mp.get("fertilization") or {}
    if fert.get("uses_fertilizers") is not None:
        flags["uses_fertilizers"] = bool(fert["uses_fertilizers"])
    pest = mp.get("pest_management") or {}
    if pest.get("pesticides"):
        flags["uses_pesticides"] = True
    if pest.get("uses_ipm") is not None:
        flags["uses_ipm"] = bool(pest["uses_ipm"])
    water = mp.get("water_management") or {}
    irr = (water.get("irrigation_system") or "").lower()
    if irr and "none" not in irr and "rainfed" not in irr:
        # only assert irrigated_rice when a rice crop is present
        if any("rice" in (f.get("name", "").lower()) for f in (api.get("foods") or [])):
            flags["irrigated_rice"] = True
    ee = api.get("equipment_energy") or {}
    if ee.get("fuel_consumption") or ee.get("equipment"):
        flags["uses_machinery"] = True
    if flags:
        ctx["flags"] = flags
    return ctx


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
    return {"flags": flags}


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
        context=context,
    )
    return recommendation_to_dict(
        rec,
        assessment_id=payload.get("id"),
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def guidance_for_chat(payload: dict, *, limit: int = 4) -> list[str]:
    """Short, cited guidance lines for the chat RAG seam. Assessment-driven (not
    query-driven), so it's stable across a conversation's turns and doesn't break the
    prompt cache. Returns [] on any failure — chat must never break because the
    recommender did."""
    try:
        is_proc = "breakdown_by_product" in payload
        rec = recommend(payload, pricebook=_pricebook(), reviewed_only=_REVIEWED_ONLY,
                        context=(_processing_context({}) if is_proc else None))
        return guidance_snippets(rec, limit=limit)
    except Exception:
        return []
