#!/usr/bin/env python3
"""
flowkey.py — canonical flow signature for nomenclature bridging (DATABASE_PLAN.md §C).

The same elementary flow appears under DIFFERENT UIDs across (and even within)
databases — e.g. "Phosphorus, emission to water" exists as several flow objects,
and an LCIA method's characterization factors are keyed to only some of those
UIDs. Matching CFs to inventory flows by raw UID therefore silently drops real
impacts (validated: Agribalyse freshwater eutrophication came out 75% low).

The fix is the Federal LCA Commons / FEDEFL model: identify a flow by
(Flowable, Context) instead of an opaque UID. Here:

    flow_key = "<substance>|<compartment>"
      substance   = normalised CAS if present, else normalised name
      compartment = coarse context (emission/water, emission/soil, resource/ground …)

Compartment is part of the key on purpose: Phosphorus→water has CF 1.0 while
Phosphorus→soil has 0.05, so a name/CAS-only match would be wrong.

Used at ingestion (store every flow's key) and at characterization (match a CF to
an inventory flow by key when the exact UID differs). UID matching stays primary,
so databases whose CFs already line up by UID (ecoinvent) are unaffected.
"""
from __future__ import annotations

import re
from typing import Optional

_WS = re.compile(r"\s+")


def norm_cas(cas: Optional[str]) -> Optional[str]:
    """Normalise a CAS number: strip, drop leading zeros of the first group.
    '007723-14-0' -> '7723-14-0'.  Returns None if empty/not CAS-like."""
    if not cas:
        return None
    cas = cas.strip()
    if not cas or cas in ("0", "-"):
        return None
    parts = cas.split("-")
    if parts and parts[0].isdigit():
        parts[0] = str(int(parts[0]))  # 007723 -> 7723
    return "-".join(parts)


def norm_name(name: Optional[str]) -> str:
    if not name:
        return ""
    return _WS.sub(" ", name.strip().lower())


def norm_compartment(category: Optional[str]) -> str:
    """Map an openLCA category path to a coarse, nomenclature-independent context.

    Keeps the distinctions that change CFs (air/water/soil, resource medium) and
    discards sub-sub-compartments and list-specific wording.
    """
    if not category:
        return ""
    c = category.lower()
    for medium in ("air", "water", "soil"):
        if f"emission to {medium}" in c or f"emissions to {medium}" in c or f"/{medium}" in c and "resource" not in c:
            return f"emission/{medium}"
    if "resource" in c or "raw" in c:
        for sub in ("in water", "in ground", "in air", "biotic", "land"):
            if sub in c:
                return "resource/" + sub.replace(" ", "")
        return "resource"
    # fallback: the second path segment (after "Elementary flows")
    parts = [p.strip().lower() for p in category.split("/") if p.strip()]
    if len(parts) >= 2:
        return parts[1]
    return parts[0] if parts else ""


def sub_compartment(category: Optional[str]) -> str:
    """Canonical emission sub-compartment. Ecotoxicity/PM CFs differ by sub-compartment
    (soil/agricultural 20828 vs soil/forestry 16250), so the key must carry it — but
    inventory and CF lists spell it differently (river vs surface water, plural
    'Emissions', 'long-term' suffixes). Normalise to a small canonical set so they
    align. Returns '' for resources / when no medium is found."""
    if not category:
        return ""
    c = category.lower().replace(", long-term", "").replace(" long-term", "").replace(",long-term", "")
    if "resource" in c or "raw" in c:
        return ""
    if "to water" in c or ("/water" in c and "resource" not in c):
        if "ground" in c:
            return "ground"
        if "ocean" in c or "sea" in c or "salt" in c:
            return "ocean"
        if "surface" in c or "river" in c or "lake" in c:
            return "surface"
        return "unspecified"
    if "to air" in c or "/air" in c:
        if "high population" in c or "urban" in c:
            return "high-pop"
        if "low population" in c or "rural" in c or "non-urban" in c:
            return "low-pop"
        if "stratosphere" in c:
            return "stratosphere"
        return "unspecified"
    if "to soil" in c or "/soil" in c:
        if "agri" in c:
            return "agricultural"
        if "forest" in c:
            return "forestry"
        if "industrial" in c:
            return "industrial"
        return "unspecified"
    return ""


def fine_compartment(category: Optional[str]) -> str:
    """Medium + canonical sub-compartment, e.g. 'emission/soil/agricultural'."""
    med = norm_compartment(category)
    if med.startswith("emission/"):
        sub = sub_compartment(category)
        if sub:
            return f"{med}/{sub}"
    return med


def flow_key(cas: Optional[str], name: Optional[str], category: Optional[str]) -> str:
    """Canonical (substance, compartment) signature for a flow.

    Substance = normalised NAME (not CAS). Name is the right discriminator here:
    same-substance duplicates across nomenclatures share a name ("Phosphate" ==
    "Phosphate"), so they still bridge — while CFs that legitimately DIFFER by a
    name qualifier stay separate. CAS is too coarse for these: "Carbon dioxide,
    fossil" (climate CF 1.0) and "Carbon dioxide, non-fossil" (biogenic, CF 0)
    share one CAS + compartment, and "Water, river" vs the water-use CF's specific
    flow share CAS "Water" — CAS-keying wrongly merges them (over-counts climate and
    water); name-keying does not. `cas` is kept in the signature only to break ties
    between different substances that happen to share a name.
    """
    n = norm_name(name)
    return f"{n}|{fine_compartment(category)}"


def medium_of(key: Optional[str]) -> Optional[str]:
    """Coarsen a fine key to the medium level: 'x|emission/water/surface' ->
    'x|emission/water'. Lets the matcher fall back from sub-compartment (ecotox) to
    medium (eutrophication, whose CFs are coarse: P-to-any-water = 1.0)."""
    if not key or "|" not in key:
        return key
    sub, comp = key.split("|", 1)
    parts = comp.split("/")
    if len(parts) > 2:
        comp = "/".join(parts[:2])
    return f"{sub}|{comp}"


def cas_key(cas: Optional[str], category: Optional[str]) -> Optional[str]:
    """Secondary signature (CAS, compartment) for bridging same-substance flows whose
    NAMES differ across nomenclatures (e.g. 'BENFURACARB' vs 'Benfuracarb', 'Gas,
    natural' vs the CF flow's name). Used ONLY in substance-identity categories
    (ecotoxicity, human toxicity, resource use) — NOT climate or water, where CAS is
    too coarse (fossil vs biogenic CO2 share a CAS; AWARE water is flow-instance).
    Returns None when the flow has no CAS."""
    nc = norm_cas(cas)
    if not nc:
        return None
    return f"{nc}|{fine_compartment(category)}"


if __name__ == "__main__":
    # fine keys distinguish sub-compartments; medium_of coarsens for eutrophication
    surf = flow_key("7723-14-0", "Phosphorus", "Elementary flows/Emission to water/surface water")
    river = flow_key("7723-14-0", "Phosphorus", "Elementary flows/Emissions to water/river")
    ground = flow_key("7723-14-0", "Phosphorus", "Elementary flows/Emission to water/ground water, long-term")
    soil_ag = flow_key("7723-14-0", "Phosphorus", "Elementary flows/Emission to soil/agricultural")
    soil_fo = flow_key("7723-14-0", "Phosphorus", "Elementary flows/Emission to soil/forestry")
    print("surface water :", surf)
    print("river         :", river, "| river==surface:", river == surf)   # synonym → same
    print("ground water  :", ground, "| ≠ surface:", ground != surf)
    print("soil ag/fo    :", soil_ag, "|", soil_fo, "| differ:", soil_ag != soil_fo)
    print("medium_of(surf):", medium_of(surf), "== medium_of(ground):", medium_of(surf) == medium_of(ground))
