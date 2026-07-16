#!/usr/bin/env python3
"""
field_model.py — expert-level adjustments to the on-farm field emissions, driven by the
real farm inputs, applied on top of the Rust LCI kernel's base output.

The Rust kernel computes direct field N2O with a single hardcoded IPCC EF1 of 0.01 and no
awareness of climate or cropping system. This layer corrects and enriches that, staying in
the Python "characterisation/adjustment" half of the architecture (no Rust rebuild):

  1. Regional / climate N2O. IPCC 2019 disaggregates the direct N2O emission factor by
     climate: wet climates release proportionally more (EF1 ~0.016) than dry ones
     (EF1 ~0.005). We scale the kernel's N2O by (region EF1 / 0.01) so the number reflects
     where the farm actually is. This is a first-order regionalisation: it scales the
     kernel's total N2O (direct plus the smaller indirect terms) by the direct-EF ratio.

  2. Legume N-fixation from intercropping. When a crop is intercropped with a legume
     partner (cowpea, groundnut, soybean, bean, pea), biological fixation supplies part of
     the system's nitrogen, so less synthetic fertiliser is needed for the same output. We
     credit a modest reduction in the synthetic-N-driven N2O to reflect that substitution.
     This is a documented screening assumption, flagged as a value choice, not a measured
     value.

Both adjustments only touch the N2O flow and always record what they did in the notes.
"""
from __future__ import annotations

RUST_EF1 = 0.01                       # the EF1 the Rust kernel hardcodes
LEGUMES = {"cowpea", "groundnut", "peanut", "soybean", "soya", "bean", "pea",
           "lentil", "chickpea", "pigeon pea", "mucuna", "lablab"}
# Fraction of the synthetic-N-driven N2O offset by a legume intercrop partner (screening
# assumption; legume fixation substitutes for part of the synthetic N requirement).
LEGUME_N2O_CREDIT = 0.20


def _has_legume_partner(assessment: dict) -> bool:
    """True if a crop has a legume *partner* (intercrop) or a legume in its *rotation* that
    supplies biological nitrogen and lowers this crop's synthetic-N need. Deliberately does
    NOT count the crop's own legume identity: a legume grown for itself still receives the
    synthetic N the farmer applied, so it must not self-credit (would over-apply)."""
    for f in assessment.get("foods") or []:
        own = str(f.get("name", "")).lower()
        pattern = (f.get("cropping_pattern") or "").lower()
        partners = [str(p).lower() for p in (f.get("intercropping_partners") or [])]
        rotation = [str(p).lower() for p in (f.get("rotation_sequence") or [])]
        if "intercrop" in pattern or partners:
            # legume neighbours/rotation only — exclude this crop's own name
            for name in partners + rotation:
                if name == own:
                    continue
                if any(leg in name for leg in LEGUMES):
                    return True
    return False


def adjust_field_emissions(on_farm_lci: list[dict], assessment: dict, region) -> tuple[list[dict], list[str]]:
    """Return (adjusted_flows, notes). Scales the N2O flow for regional climate and for a
    legume intercrop credit. Non-N2O flows pass through untouched."""
    notes: list[str] = []
    ef1 = getattr(region, "ipcc_n2o_ef1", None)
    factor = 1.0

    if ef1 and ef1 != RUST_EF1:
        factor *= ef1 / RUST_EF1
        notes.append(
            f"field N2O scaled to the region's IPCC EF1 ({ef1} kg N2O-N/kg N, "
            f"{getattr(region, 'climate_zone', 'regional')} climate) from the kernel default {RUST_EF1}")

    if _has_legume_partner(assessment):
        factor *= (1.0 - LEGUME_N2O_CREDIT)
        notes.append(
            f"legume intercrop present: field N2O reduced by {int(LEGUME_N2O_CREDIT*100)}% "
            "for biological nitrogen fixation substituting synthetic fertiliser (screening assumption)")

    if factor == 1.0:
        return on_farm_lci, notes

    adjusted = []
    for f in on_farm_lci:
        if f.get("substance") == "N2O":
            g = dict(f)
            g["quantity"] = (g.get("quantity") or 0.0) * factor
            adjusted.append(g)
        else:
            adjusted.append(f)
    return adjusted, notes
