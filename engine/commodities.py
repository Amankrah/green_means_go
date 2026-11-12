#!/usr/bin/env python3
"""
commodities.py: commodities the field-crop farm model must not run.

Honey / apiculture. The farm engine is a crop model (IPCC soil N2O from fertiliser and
residues, land occupation by crop area, fuel and irrigation). A beehive has none of these:
its inventory is hive materials (timber, wax foundation), supplementary sugar feeding,
smoker fuel, extraction energy, transport of hives and, depending on the allocation
choice, part of the forage land. Running honey as a field crop would produce a number with
no physical meaning. The store holds two WFLDB honey datasets (US large-scale, CH
small-scale), but there is no West African apiculture inventory to regionalise them with
(no data on hive type, yield per hive, feeding or migration for GH/NG/SN/BF), so an
apiculture foreground would not be defensible. Decision: the farm API rejects honey with
a clear 422 message; on the processing side, raw honey bought in as an ingredient is
modelled with the WFLDB small-scale honey dataset and flagged as a proxy.
"""
from __future__ import annotations

APICULTURE_WORDS = ("honey", "apicultur", "beekeep", "bee keep", "beehive", "bee hive",
                    "beeswax", "bees wax", "propolis", "royal jelly")

HONEY_PROXY_DATASET = "Honey, raw, small-scale production, unpackaged, at farm"


class UnsupportedCommodityError(ValueError):
    """The assessment declares a commodity the farm model cannot represent."""


def is_apiculture(name) -> bool:
    n = str(name or "").lower()
    return any(w in n for w in APICULTURE_WORDS)


def reject_unsupported_farm_commodities(assessment: dict) -> None:
    """Raise UnsupportedCommodityError if any declared food is honey/apiculture."""
    bad = [f.get("name") for f in (assessment.get("foods") or [])
           if is_apiculture(f.get("name")) or is_apiculture(f.get("crop_type"))
           or is_apiculture(f.get("category"))]
    if bad:
        raise UnsupportedCommodityError(
            f"Honey and other apiculture products ({', '.join(str(b) for b in bad)}) cannot "
            "be assessed with the farm (field crop) model: a beehive has no fertiliser, crop "
            "residues or cropped area, and no West African apiculture inventory is available "
            "yet. Remove the honey entry to assess the other crops, or assess honey "
            "processing with raw honey as a purchased raw material.")


def flag_processing_raw_materials(inputs: list[dict]) -> tuple[list[dict], list[str]]:
    """Steer raw-honey ingredients to the WFLDB honey dataset and flag the proxy."""
    out, notes = [], []
    for inp in inputs:
        if inp.get("kind") == "raw_material" and is_apiculture(inp.get("name")):
            inp = {**inp, "match_as": HONEY_PROXY_DATASET}
            notes.append(
                f"validation warning: raw material '{inp.get('name')}' (honey) modelled with "
                f"the WFLDB dataset '{HONEY_PROXY_DATASET}' (Switzerland): no West African "
                "apiculture inventory exists, treat this burden as an order-of-magnitude proxy")
        out.append(inp)
    return out, notes
