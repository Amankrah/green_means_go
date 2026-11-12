#!/usr/bin/env python3
"""
perennials.py: perennial tree crops (cocoa, oil palm) in a single-year farm LCA.

A cocoa or oil palm stand yields nothing for its first years, then produces for two
decades. A one-year snapshot of a mature farm therefore misses the establishment phase.
Following PAS 2050-1:2012 (supplementary requirements for horticultural products, clause
on perennial crops) and the WFLDB methodological guidelines (Nemecek et al. 2019, perennial
crops), the burden of the non-productive establishment years is amortised over the
productive years of the plantation:

    establishment factor  =  (immature_years x input_share + productive_years) / productive_years

applied to the annual field emissions, purchased inputs and land occupation of a mature
year. Without primary data on establishment-year inputs we take input_share = 1 (the
establishment years use the same inputs and land as a mature year): a conservative
screening assumption, flagged in the notes and overridable per crop with
`foods[].establishment = {"immature_years": .., "productive_years": .., "input_share": ..}`.

Land occupation is reported as "Occupation, permanent crop" (not annual crop).

Lifetimes (cited in PERENNIALS below):
  cocoa:    first pods in year 3 to 5, productive for about 20 more years; we use 3
            non-productive + 22 productive = 25 years. IITA crop profile 'Cocoa (Theobroma
            cacao)' (iita.org/cropsnew/cocoa) and ICCO cocoa growing guidance.
  oil palm: 25-year replanting cycle with a 3-year immature phase, as used by the RSPO
            PalmGHG calculator (Chase et al. 2012, RSPO PalmGHG beta 2) and Corley & Tinker
            (2016) The Oil Palm, 5th ed.
"""
from __future__ import annotations

PERENNIALS: dict[str, dict] = {
    "cocoa": {
        "tokens": ("cocoa", "cacao"),
        "immature_years": 3,
        "productive_years": 22,
        "lifetime_years": 25,
        "biomass_class": "Shaded Perennial",
        "source": "IITA crop profile 'Cocoa (Theobroma cacao)'; ICCO growing guidance: "
                  "pods from year 3 to 5, about 25 years economic life",
    },
    "oil palm": {
        "tokens": ("oil palm", "palm oil", "palm fruit", "fresh fruit bunch", "ffb"),
        "immature_years": 3,
        "productive_years": 22,
        "lifetime_years": 25,
        "biomass_class": "Oil palm",
        "source": "RSPO PalmGHG (Chase et al. 2012): 25-year cycle, 3-year immature phase; "
                  "Corley & Tinker (2016) The Oil Palm, 5th ed.",
    },
}

# Rust land-occupation substance key -> permanent-crop key (flowmap.ONFARM_FLOWS)
LAND_OCC_ANNUAL = "land_occ"
LAND_OCC_PERMANENT = "land_occ_perm"


def perennial_for(crop_name) -> dict | None:
    n = str(crop_name or "").lower()
    if not n:
        return None
    for key, p in PERENNIALS.items():
        if any(t in n for t in p["tokens"]):
            return {"crop": key, **p}
    # bare "palm" (e.g. "Palm", "Palm kernels") is oil palm in a West African farm context
    if n.strip() in ("palm", "palms") or n.startswith("palm "):
        return {"crop": "oil palm", **PERENNIALS["oil palm"]}
    return None


def establishment_factor(food: dict) -> tuple[float, dict | None, str | None]:
    """(factor, perennial spec, note) for one food. factor = 1 for annual crops."""
    p = perennial_for(food.get("name"))
    if p is None:
        return 1.0, None, None
    est = food.get("establishment") or {}
    immature = float(est.get("immature_years", p["immature_years"]))
    productive = float(est.get("productive_years", p["productive_years"]))
    share = float(est.get("input_share", 1.0))
    if productive <= 0:
        return 1.0, p, None
    factor = (immature * share + productive) / productive
    note = (f"{p['crop']} treated as a perennial: {immature:g} establishment years amortised "
            f"over {productive:g} productive years (factor {factor:.3f}; establishment-year "
            f"input share {share:g}, screening assumption; {p['source']}; PAS 2050-1:2012)")
    return factor, p, note


def single_perennial(assessment: dict) -> tuple[float, dict | None, str | None]:
    """Establishment factor for a single-crop product system. Multi-crop assessments are
    split per crop by engine/service.py before reaching here; if several foods remain
    (no areas), perennial amortisation is skipped with a note."""
    foods = assessment.get("foods") or []
    if len(foods) != 1:
        if any(perennial_for(f.get("name")) for f in foods):
            return 1.0, None, ("perennial establishment not amortised: several crops share "
                               "one product system without crop areas")
        return 1.0, None, None
    return establishment_factor(foods[0])


def scale_purchased_inputs(inputs: list[dict], assessment: dict) -> tuple[list[dict], list[str]]:
    """Scale purchased-input amounts of a perennial product system by its establishment
    factor (establishment-year inputs amortised over the productive years)."""
    factor, p, note = single_perennial(assessment)
    if p is None or factor == 1.0:
        return inputs, ([note] if note else [])
    out = []
    for i in inputs:
        j = dict(i)
        try:
            j["amount"] = float(i["amount"]) * factor
        except (KeyError, TypeError, ValueError):
            pass
        j["establishment_factor"] = factor
        out.append(j)
    return out, [f"purchased inputs scaled by the {p['crop']} establishment factor {factor:.3f}"]


def apply_to_field_flows(flows: list[dict], assessment: dict) -> tuple[list[dict], list[str]]:
    """Scale on-farm flows by the establishment factor and report land as permanent crop."""
    factor, p, note = single_perennial(assessment)
    notes = [note] if note else []
    if p is None:
        return flows, notes
    out = []
    for f in flows:
        g = dict(f)
        g["quantity"] = (g.get("quantity") or 0.0) * factor
        if g.get("substance") == LAND_OCC_ANNUAL:
            g["substance"] = LAND_OCC_PERMANENT
        out.append(g)
    notes.append(f"{p['crop']} land occupation reported as 'Occupation, permanent crop'")
    return out, notes
