#!/usr/bin/env python3
"""
water_scarcity.py: regionalised AWARE water-scarcity characterisation of FOREGROUND
(on-farm) consumptive water use.

Problem it fixes
----------------
The Rust kernel emits irrigation water as `water` / resource, which flowmap.py books on
the store flow "Water, Resource/in water". No served method has a CF for that flow (the
ecoinvent 3.11 method pack characterises water CONSUMPTION through "Water" emitted to air,
i.e. evaporation), so irrigation water characterised to exactly zero, and
`regions.aware_country` was never read.

Design (one validated path, no double counting)
-----------------------------------------------
* Consumptive foreground water (m3) is booked on a REGIONALISED elementary flow
  "Water, consumptive use, agri, <Country> (AWARE)" added to the store by
  ingestion/gmg_reference.py. That flow carries every CF of the ecoinvent base flow
  "Water / Emission to air / unspecified" in every method, except EF v3.x "Water use",
  where the GLO default (42.95 = AWARE 'World, UNKNOWN') is replaced by the country AWARE
  CF (agri for irrigation). So:
    - EF 3.1 "Water use" (m3 world-eq deprived) = background AWARE (ecoinvent, GLO CFs on
      evaporation flows) + foreground AWARE with the country CF;
    - ReCiPe 2016 "Water use" (m3 consumed, CF 1.0 for all consumption, Huijbregts et al.
      2017) = background consumption + foreground consumption;
    - endpoints, method switches and the Monte Carlo pick it up automatically because the
      change is in the inventory, not in a post-hoc impact number.
* Background water stays characterised by the method pack (GLO CFs). We do NOT re-
  regionalise background flows: ecoinvent water flows are not located, and AWARE guidance
  (Boulay et al. 2018, Sec. 4) recommends the unknown-location default for them.
* Double counting is avoided at two points:
    1. If the user supplied measured purchased irrigation water (inputs with unit m3 and a
       `water_source`, or kind water / irrigation_water), the Rust per-hectare irrigation
       ESTIMATE is not also counted; the measured amount supersedes it.
    2. A purchased irrigation-water input that was matched to a background dataset keeps
       that dataset's pumping energy and infrastructure, but its "Water" emission-to-air
       (evaporation) flows are removed from the supply chain, because the foreground already
       books that same water as consumed on the farm.
* Consumptive fraction: ISO 14046:2014, 3.2.1 defines consumption as water removed from
  the drainage basin (evaporation, incorporation, transfer). The part of applied
  irrigation water that is not taken up by crop evapotranspiration returns to the same
  basin as runoff or deep percolation and is not deprivation. The consumed share of the
  WITHDRAWAL is therefore taken as the field application efficiency of the irrigation
  method (FAO: Brouwer C, Prins K, Heibloem M (1989) Irrigation Water Management:
  Irrigation Scheduling, Training Manual No. 4, Annex I, "Field application efficiency":
  surface irrigation (border, furrow, basin) 60%, sprinkler 75%, drip 90%). Flooded rice
  and unknown / manual systems take the surface value. An input's own
  `consumptive_fraction` overrides the default.

Also exposes aware_indicator(), the separate "Water scarcity (AWARE)" midpoint the adapter
reports for every method (EF 3.1 "Water use" characterisation of the merged inventory).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_REF = Path(__file__).resolve().parent / "lcia_reference" / "aware_country_cfs.json"

AWARE_METHOD = "EF v3.1"          # the served method whose "Water use" is AWARE-based
WORLD = "World"
# Consumed share of irrigation WITHDRAWAL = field application efficiency, FAO Training
# Manual No. 4 (Brouwer et al. 1989), Annex I: surface 0.60, sprinkler 0.75, drip 0.90.
APPLICATION_EFFICIENCY = {"drip": 0.90, "sprinkler": 0.75, "surface": 0.60}
_SOURCE_FAO = "FAO Irrigation Water Management Training Manual No. 4 (Brouwer et al. 1989), Annex I"


def consumptive_fraction(system: str | None) -> tuple[float, str]:
    """(fraction of withdrawal consumed, system class) for an irrigation-system text."""
    t = (system or "").lower()
    if "drip" in t or "micro" in t or "trickle" in t:
        return APPLICATION_EFFICIENCY["drip"], "drip"
    if "sprinkler" in t or "pivot" in t:
        return APPLICATION_EFFICIENCY["sprinkler"], "sprinkler"
    return APPLICATION_EFFICIENCY["surface"], "surface"   # flood, furrow, basin, bucket, unknown


@lru_cache(maxsize=1)
def _table() -> dict:
    with open(_REF, encoding="utf-8") as fh:
        return json.load(fh)


def country_key(region) -> str:
    """AWARE country key for a Region (Region.aware_country), else World."""
    key = (getattr(region, "aware_country", None) or "").strip()
    return key or WORLD


def aware_cf(region, use: str = "agri") -> tuple[float, str]:
    """(CF in m3 world-eq deprived per m3, country actually used). Falls back to the AWARE
    world aggregate for that use when the country is unknown."""
    t = _table()
    key = country_key(region)
    row = t["countries"].get(key) or t["all_countries"].get(key)
    if row and row.get(use) is not None:
        return float(row[use]), key
    return float(t["world"][use]), WORLD


# ------------------------------------------------------------------ store helpers
def regional_flow_uid(q, country: str, use: str = "agri") -> str | None:
    """UID of the regionalised water flow for (country, use) in the store, or None if
    ingestion/gmg_reference.py has not been run on this store."""
    try:
        r = q.conn.execute(
            "SELECT flow_uid FROM gmg_regionalised_flows WHERE kind='water' AND country=? AND use_type=?",
            (country, use)).fetchone()
    except Exception:
        return None
    return r[0] if r else None


def _is_purchased_water(inp: dict) -> bool:
    unit = str(inp.get("unit") or "").strip().lower().replace("³", "3")
    kind = str(inp.get("kind") or "").lower()
    return unit == "m3" and ("water_source" in inp or kind in ("water", "irrigation_water", "irrigation"))


def foreground_consumption(on_farm_lci: list[dict], purchased_inputs: list[dict]) -> tuple[float, list[str]]:
    """Consumptive foreground water (m3) and human-readable basis notes. Withdrawal x
    consumed share (application efficiency by system, or the input's consumptive_fraction)."""
    notes: list[str] = []
    measured = [i for i in purchased_inputs if _is_purchased_water(i)]
    if measured:
        total = 0.0
        for i in measured:
            if i.get("consumptive_fraction") is not None:
                frac, basis = float(i["consumptive_fraction"]), "user-supplied"
            else:
                frac, cls = consumptive_fraction(i.get("irrigation_system") or i.get("water_source"))
                basis = f"{cls} application efficiency, {_SOURCE_FAO}"
            total += float(i.get("amount") or 0.0) * frac
            notes.append(f"irrigation water '{i.get('name')}': {float(i.get('amount') or 0):.0f} m3 withdrawn x "
                         f"{frac:.2f} consumed ({basis})")
        est = sum(float(f.get("quantity") or 0.0) for f in on_farm_lci if f.get("substance") == "water")
        if est:
            notes.append(f"irrigation water: measured purchased water supersedes the kernel estimate "
                         f"({est:.0f} m3 withdrawn); estimate not counted (no double counting)")
        return total, notes
    total = 0.0
    for f in on_farm_lci:
        if f.get("substance") != "water":
            continue
        q = float(f.get("quantity") or 0.0)
        if f.get("consumptive_fraction") is not None:
            frac, basis = float(f["consumptive_fraction"]), "user-supplied"
        else:
            frac, cls = consumptive_fraction(f.get("source"))
            basis = f"{cls} application efficiency, {_SOURCE_FAO}"
        total += q * frac
        if q:
            notes.append(f"irrigation water: {q:.0f} m3 withdrawn x {frac:.2f} consumed ({basis}); "
                         "the non-consumed share returns to the basin and is not deprivation")
    return total, notes


def _evaporation_uids(q, uids) -> set:
    """Of `uids`, the 'Water' emission-to-air flows (what the method pack characterises as
    consumption)."""
    uids = list(uids)
    out = set()
    for i in range(0, len(uids), 500):
        chunk = uids[i:i + 500]
        for r in q.conn.execute(
            f"SELECT uid FROM flows WHERE uid IN ({','.join('?' * len(chunk))}) AND name='Water' "
            "AND category LIKE '%Emission to air%'", chunk):
            out.add(r[0])
    return out


def apply(q, region, on_farm_lci: list[dict], purchased_inputs: list[dict],
          onfarm: dict, supply: dict, res, method: str) -> dict | None:
    """Book consumptive foreground water on the regionalised AWARE flow (edits `onfarm`)
    and strip background evaporation of purchased irrigation water (edits `supply` and the
    per-source records on `res`). Never raises."""
    try:
        m3, notes = foreground_consumption(on_farm_lci, purchased_inputs)
        res.notes.extend(notes)
        # 2) de-duplicate purchased irrigation water evaporation in the supply chain
        for inp in purchased_inputs:
            if not _is_purchased_water(inp):
                continue
            src = (getattr(res, "contribution_flows_by_source", {}) or {}).get(inp.get("name"))
            if not src:
                continue
            evap = _evaporation_uids(q, src.keys())
            if not evap:
                continue
            for uid in evap:
                amt = src[uid]["amount"]
                if uid in supply:
                    supply[uid]["amount"] -= amt
                del src[uid]
            res.contribution_by_source[inp["name"]] = q.characterize_flows(src, method)
            res.notes.append(f"'{inp['name']}': background evaporation removed; this water is "
                             "counted once, as on-farm consumption with the regional AWARE factor")
        if m3 <= 0:
            return None
        cf, used = aware_cf(region, "agri")
        uid = regional_flow_uid(q, used, "agri")
        if not uid:
            res.notes.append("AWARE regional water flows not in the store (run "
                             "`python -m ingestion.gmg_reference ingest`); irrigation water not "
                             "characterised for water scarcity")
            return None
        name = f"Water, consumptive use, agri, {used} (AWARE)"
        rec = onfarm.get(uid)
        if rec:
            rec["amount"] += m3
        else:
            onfarm[uid] = {"name": name, "unit": "m3", "amount": m3}
        flag = "" if used == country_key(region) else " (country not in AWARE table: world default)"
        res.notes.append(
            f"irrigation water {m3:.0f} m3 consumed, characterised with AWARE agri CF {cf:.2f} "
            f"m3 world-eq/m3 for {used}{flag} = {m3 * cf:.0f} m3 world-eq deprived "
            "(Boulay et al. 2018)")
        return {"m3": m3, "cf": cf, "country": used, "flow_uid": uid}
    except Exception as e:   # a water-scarcity failure must not break an assessment
        try:
            res.notes.append(f"water scarcity step skipped: {e}")
        except Exception:
            pass
        return None


def aware_indicator(engine, inventory: dict) -> dict | None:
    """'Water scarcity (AWARE)' for ANY served method: EF 3.1 'Water use' of the merged
    inventory (ecoinvent AWARE CFs for background, regional AWARE for the foreground).
    Returns {"value", "unit"} or None.

    Computed as sum(amount x CF) over the EF 3.1 'Water use' CFs matched by flow UID, which
    is exactly what query._characterize does for water categories (they are never bridged by
    name/CAS/FEDEFL), but without characterising every other EF category."""
    try:
        cfs = _water_use_cfs(engine.q)
        if not cfs:
            return None
        total = sum((r.get("amount") or 0.0) * cfs[uid] for uid, r in (inventory or {}).items() if uid in cfs)
        return {"value": total, "unit": "m3 world-eq deprived"}
    except Exception:
        return None


_WU_CACHE: dict = {}


def _water_use_cfs(q) -> dict:
    key = id(q)
    if key not in _WU_CACHE:
        m = q.find_method(AWARE_METHOD)
        cfs = {}
        if m and m.get("name") == AWARE_METHOD:
            for r in q.conn.execute(
                "SELECT cf.flow_uid, cf.factor FROM characterization_factors cf JOIN impact_categories ic "
                "ON ic.uid=cf.category_uid WHERE ic.method_uid=? AND ic.name='Water use'", (m["uid"],)):
                cfs[r[0]] = r[1]
        _WU_CACHE[key] = cfs
    return _WU_CACHE[key]
