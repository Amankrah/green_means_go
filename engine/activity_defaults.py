#!/usr/bin/env python3
"""
Farm activity defaults, per region: provenanced diesel/electricity (and yield guides)
when the Equipment & Energy step has no measured fuel or grid use.

The LLM never produces these numbers. Lookup is deterministic from wizard fields
already collected (production_system, irrigation_system, mechanization, equipment).

Which table applies is decided by the REGION, generically:
  1. getattr(region, "activity_defaults_file", None) (Region field added by the regions
     workstream; a file name under engine/recommend/reference/ or a repo-relative path);
  2. else the built-in fallback map below (GH -> Ghana table, NG -> Nigeria table);
  3. else engine/recommend/reference/<country>_farm_activity_defaults.json if present.
A region with no table gets NO injected defaults (never Ghana's) and a flag note.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

_DIESEL_MJ_PER_L = 38.7  # keep in sync with engine/inputs.FUEL_MJ_PER_L["diesel"]

_REF_DIR = Path(__file__).resolve().parent / "recommend" / "reference"
_REPO = Path(__file__).resolve().parent.parent
_REF = _REF_DIR / "ghana_farm_activity_defaults.json"

# Fallback until every Region carries activity_defaults_file.
_FALLBACK_FILES = {
    "GH": "ghana_farm_activity_defaults.json",
    "NG": "nigeria_farm_activity_defaults.json",
}

_MECH_ALIASES = {
    "fully manual": "fully_manual",
    "fully_manual": "fully_manual",
    "manual": "fully_manual",
    "none": "fully_manual",
    "partially mechanized": "partially_mechanized",
    "partially_mechanized": "partially_mechanized",
    "partial": "partially_mechanized",
    "fully mechanized": "fully_mechanized",
    "fully_mechanized": "fully_mechanized",
    "mechanized": "fully_mechanized",
}

_BUCKET_HINTS = ("bucket", "manual irrigation", "none (rainfed)", "none")
_PUMP_HINTS = ("flood", "furrow", "sprinkler", "drip", "pump")


@lru_cache(maxsize=16)
def _load(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _table() -> dict[str, Any]:
    """The Ghana table (kept for regional_benchmark and backward compatibility)."""
    return _load(str(_REF))


def is_ghana(assessment: dict) -> bool:
    c = (assessment.get("country") or "").strip().lower()
    r = (assessment.get("region") or "").strip().upper()
    return c in ("ghana", "gh") or r == "GH"


def region_of(assessment: dict):
    """Resolve the assessment's Region from `region` (code) or `country`; None if unknown."""
    try:
        from .regions import get_region
    except ImportError:
        from regions import get_region  # type: ignore
    for key in (assessment.get("region"), assessment.get("country")):
        if key:
            try:
                return get_region(str(key))
            except KeyError:
                continue
    return None


def table_path_for(region) -> Optional[Path]:
    """Path of the activity-defaults table for `region`, or None if it has none."""
    if region is None:
        return None
    cands = []
    f = getattr(region, "activity_defaults_file", None)
    if f:
        cands += [Path(f), _REPO / f, _REF_DIR / f]
    fb = _FALLBACK_FILES.get(getattr(region, "code", ""))
    if fb:
        cands.append(_REF_DIR / fb)
    name = (getattr(region, "name", "") or "").strip().lower().replace(" ", "_")
    if name:
        cands.append(_REF_DIR / f"{name}_farm_activity_defaults.json")
    for c in cands:
        if c.is_file():
            return c
    return None


def table_for(region) -> Optional[dict[str, Any]]:
    p = table_path_for(region)
    return _load(str(p)) if p else None


def _norm_mech(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    return _MECH_ALIASES.get(str(raw).strip().lower())


def _irrigation_system(assessment: dict) -> str:
    mp = assessment.get("management_practices") or {}
    wm = mp.get("water_management") or {}
    return str(wm.get("irrigation_system") or wm.get("irrigationSystem") or "").strip()


def _is_irrigated(assessment: dict) -> bool:
    foods = assessment.get("foods") or []
    for f in foods:
        ps = str(f.get("production_system") or "").lower()
        if "irrigat" in ps:
            return True
    irr = _irrigation_system(assessment).lower()
    if not irr:
        return False
    if "rainfed" in irr or irr in ("none", "none (rainfed)"):
        return False
    return True


def _irrigation_mode(assessment: dict) -> str:
    """manual_bucket vs pumped — only meaningful when irrigated."""
    irr = _irrigation_system(assessment).lower()
    if any(h in irr for h in _BUCKET_HINTS) and not any(h in irr for h in _PUMP_HINTS):
        if "bucket" in irr or "manual" in irr:
            return "manual_bucket"
    if any(h in irr for h in _PUMP_HINTS):
        return "pumped"
    # Irrigated production_system without a system detail: assume pumped SSI (Ghana modal).
    return "pumped"


def _mechanization(assessment: dict) -> str:
    ee = assessment.get("equipment_energy") or {}
    # Explicit harvest mechanization if present (camel or snake).
    for key in ("harvesting_methods", "harvestingMethods"):
        hm = ee.get(key) or assessment.get(key) or {}
        if isinstance(hm, dict):
            m = _norm_mech(hm.get("mechanization_level") or hm.get("mechanizationLevel"))
            if m:
                return m
    foods = assessment.get("foods") or []
    for f in foods:
        for key in ("harvesting_methods", "harvestingMethods"):
            hm = f.get(key) or {}
            if isinstance(hm, dict):
                m = _norm_mech(hm.get("mechanization_level") or hm.get("mechanizationLevel"))
                if m:
                    return m
    # Infer from declared equipment list (no measured fuel yet).
    equipment = ee.get("equipment") or []
    if equipment:
        powered = [
            eq for eq in equipment
            if (eq.get("hours_per_year") or eq.get("hoursPerYear") or 0) > 0
            or (eq.get("fuel_efficiency") or eq.get("fuelEfficiency"))
        ]
        if len(powered) >= 2:
            return "fully_mechanized"
        return "partially_mechanized"
    return "fully_manual"


def _lookup_row(mechanization: str, irrigated: bool, irrigation_mode: str,
                table: Optional[dict] = None) -> dict[str, Any]:
    rows = (table if table is not None else _table()).get("rows") or []
    candidates = [
        r for r in rows
        if r.get("mechanization") == mechanization and bool(r.get("irrigated")) == irrigated
    ]
    if not candidates:
        # Safe fallback: rainfed manual zeros
        for r in rows:
            if r.get("id") == "rainfed_manual":
                return r
        return {"diesel_l_per_ha": 0, "electricity_kwh_per_ha": 0, "id": "fallback_zero"}
    if irrigated and mechanization == "fully_manual":
        for r in candidates:
            if r.get("irrigation_mode") == irrigation_mode:
                return r
        # Prefer pumped if mode ambiguous among manual irrigated rows
        for r in candidates:
            if r.get("irrigation_mode") == "pumped":
                return r
    return candidates[0]


def resolve_energy_defaults(assessment: dict) -> Optional[dict[str, Any]]:
    """Return a resolved defaults dict, or None if the assessment's region has no table."""
    region = region_of(assessment)
    path = table_path_for(region)
    if path is None:
        return None
    table = _load(str(path))
    mech = _mechanization(assessment)
    irrigated = _is_irrigated(assessment)
    mode = _irrigation_mode(assessment) if irrigated else "none"
    row = _lookup_row(mech, irrigated, mode, table)
    prov = dict(row.get("provenance") or {})
    return {
        "region": getattr(region, "code", None),
        "table_id": table.get("id"),
        "table_file": path.name,
        "inherited_from_ghana": prov.get("inherited_from_ghana") or [],
        "row_id": row.get("id"),
        "mechanization": mech,
        "irrigated": irrigated,
        "irrigation_mode": mode,
        "diesel_l_per_ha": float(row.get("diesel_l_per_ha") or 0),
        "electricity_kwh_per_ha": float(row.get("electricity_kwh_per_ha") or 0),
        "yield_guides_kg_per_ha": row.get("yield_guides_kg_per_ha") or {},
        "uncertainty_factor": float(table.get("uncertainty_factor") or 2.0),
        "provenance": row.get("provenance") or {},
    }


def has_measured_fuel(assessment: dict, existing_inputs: list[dict]) -> bool:
    if any(i.get("kind") == "fuel" and not i.get("estimated") for i in existing_inputs):
        return True
    ee = assessment.get("equipment_energy") or {}
    for fu in ee.get("fuel_consumption") or []:
        if (fu.get("monthly_consumption") or 0) > 0:
            return True
    for eq in ee.get("equipment") or []:
        eff = eq.get("fuel_efficiency") or eq.get("fuelEfficiency")
        hrs = eq.get("hours_per_year") or eq.get("hoursPerYear")
        if eff and hrs and float(eff) * float(hrs) > 0:
            return True
    return False


def has_measured_electricity(assessment: dict, existing_inputs: list[dict]) -> bool:
    if any(i.get("kind") == "electricity" and not i.get("estimated") for i in existing_inputs):
        return True
    ee = assessment.get("equipment_energy") or {}
    for en in ee.get("energy_sources") or []:
        et = (en.get("energy_type") or en.get("energyType") or "").lower()
        if ("electric" in et or "grid" in et) and (en.get("monthly_consumption") or en.get("monthlyConsumption") or 0) > 0:
            return True
    return False


def apply_activity_defaults(
    assessment: dict,
    inputs: list[dict],
    notes: list[str],
) -> list[dict]:
    """Append estimated fuel/electricity purchased inputs when measured data is absent."""
    resolved = resolve_energy_defaults(assessment)
    if not resolved:
        region = region_of(assessment)
        if region is not None and (not has_measured_fuel(assessment, inputs)
                                   or not has_measured_electricity(assessment, inputs)):
            notes.append(
                f"activity defaults unavailable for {region.name}: no regional activity-defaults "
                "table, so no fuel/electricity estimates were injected for unmeasured energy "
                "(Ghana values are never borrowed); energy may be understated (flag)")
        return inputs

    foods = assessment.get("foods") or []
    area = sum((f.get("area_allocated") or 0) for f in foods)
    if area <= 0:
        return inputs

    need_fuel = not has_measured_fuel(assessment, inputs)
    need_elec = not has_measured_electricity(assessment, inputs)
    if not need_fuel and not need_elec:
        return inputs

    diesel_l = resolved["diesel_l_per_ha"] * area if need_fuel else 0.0
    elec_kwh = resolved["electricity_kwh_per_ha"] * area if need_elec else 0.0
    uf = resolved["uncertainty_factor"]
    injected_nonzero = False

    if need_fuel and diesel_l > 0:
        mj = diesel_l * _DIESEL_MJ_PER_L
        inputs.append({
            "name": "diesel, burned in agricultural machinery",
            "amount": mj,
            "unit": "MJ",
            "kind": "fuel",
            "estimated": True,
            "estimate_meta": {
                "activity": "diesel_l",
                "amount_activity": diesel_l,
                "unit_activity": "L/yr",
                "per_ha": resolved["diesel_l_per_ha"],
                "row_id": resolved["row_id"],
                "uncertainty_factor": uf,
            },
        })
        injected_nonzero = True
        notes.append(
            f"estimated diesel {diesel_l:.0f} L/yr "
            f"({resolved['diesel_l_per_ha']:.0f} L/ha × {area:.2f} ha; "
            f"row {resolved['row_id']}; uncertainty ×{uf:.0f})"
        )
    elif need_fuel and diesel_l == 0:
        notes.append(
            f"activity default: 0 L diesel/yr for {resolved['mechanization']} / "
            f"{'irrigated' if resolved['irrigated'] else 'rainfed'} "
            f"(row {resolved['row_id']}; no flat 80 L/ha fallback)"
        )

    if need_elec and elec_kwh > 0:
        inputs.append({
            "name": "electricity low voltage",
            "amount": elec_kwh,
            "unit": "kWh",
            "kind": "electricity",
            "estimated": True,
            "estimate_meta": {
                "activity": "electricity_kwh",
                "amount_activity": elec_kwh,
                "unit_activity": "kWh/yr",
                "per_ha": resolved["electricity_kwh_per_ha"],
                "row_id": resolved["row_id"],
                "uncertainty_factor": uf,
            },
        })
        injected_nonzero = True
        notes.append(
            f"estimated grid electricity {elec_kwh:.0f} kWh/yr "
            f"({resolved['electricity_kwh_per_ha']:.0f} kWh/ha × {area:.2f} ha; "
            f"row {resolved['row_id']}; uncertainty ×{uf:.0f})"
        )
    elif need_elec and elec_kwh == 0:
        notes.append(
            f"activity default: 0 kWh grid/yr for {resolved['mechanization']} / "
            f"{'irrigated' if resolved['irrigated'] else 'rainfed'} "
            f"(row {resolved['row_id']}; no flat 200 kWh/ha fallback)"
        )

    # Flag for ISO/DQ + gather_farm_records when we replaced the old flat energy
    # fallback (both sides unmeasured) or injected a non-zero estimate.
    if injected_nonzero or (need_fuel and need_elec):
        notes.append(
            f"used activity defaults ({resolved['table_id']}: {resolved['row_id']}; "
            f"{resolved['mechanization']}; "
            f"{'irrigated' if resolved['irrigated'] else 'rainfed'}; "
            f"uncertainty ×{uf:.0f})"
        )
        if resolved.get("inherited_from_ghana") and resolved.get("region") != "GH":
            notes.append(
                f"activity default row {resolved['row_id']} for {resolved['region']} carries values "
                f"inherited from the Ghana table ({', '.join(resolved['inherited_from_ghana'])}); "
                "flagged for data-quality review")

    return inputs
