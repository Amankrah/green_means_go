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

# ---- Compost / manure organic-N -> field N2O (IPCC 2019 Vol.4 Ch.11) --------------------
# Representative total-N content of the organic amendment, as a fraction of the fresh
# applied mass, by source (screening defaults; real values vary widely with moisture and
# feedstock). Application rate arrives in tonnes/ha/year.
COMPOST_N_FRACTION = {
    "Animal manure": 0.005,
    "Farm-made compost": 0.012,
    "Purchased compost": 0.012,
    "Green waste/crop residues": 0.008,
    "Mixed sources": 0.010,
}
DEFAULT_COMPOST_N = 0.010
# IPCC 2019 indirect-N2O parameters for applied organic N.
FRAC_GASM = 0.21     # fraction of organic N volatilised as NH3/NOx
EF4 = 0.010          # N2O from atmospheric N deposition
FRAC_LEACH = 0.24    # fraction of N leached/run off (non-arid climates)
EF5 = 0.011          # N2O from leaching/runoff
N2O_N_TO_N2O = 44.0 / 28.0


def _effective_ef1(assessment: dict, region) -> float:
    base = getattr(region, "ipcc_n2o_ef1", RUST_EF1) or RUST_EF1
    scale = assessment.get("ipcc_ef1_scale")
    if scale is None:
        return base
    try:
        return base * float(scale)
    except (TypeError, ValueError):
        return base


def _compost_n2o(assessment: dict, region) -> tuple[float, str | None]:
    """Direct + indirect field N2O (kg) from applied compost/manure organic N, per IPCC
    2019 Tier 1. Returns (n2o_kg, note). Zero if no rate is given."""
    sm = ((assessment.get("management_practices") or {}).get("soil_management")) or {}
    rate_t_ha = sm.get("compost_application_rate")
    if not rate_t_ha or not sm.get("uses_compost"):
        return 0.0, None
    total_area = sum((f.get("area_allocated") or 0) for f in (assessment.get("foods") or []))
    if total_area <= 0:
        return 0.0, None
    source = sm.get("compost_source") or ""
    n_frac = COMPOST_N_FRACTION.get(source, DEFAULT_COMPOST_N)
    ef1 = _effective_ef1(assessment, region)
    # organic N applied (kg) = rate(t/ha) × 1000 × area(ha) × N-fraction
    f_on = rate_t_ha * 1000.0 * total_area * n_frac
    n2o = f_on * (ef1 + FRAC_GASM * EF4 + FRAC_LEACH * EF5) * N2O_N_TO_N2O
    if n2o <= 0:
        return 0.0, None
    note = (f"compost/manure applied ({rate_t_ha:g} t/ha, {source or 'unspecified'}, "
            f"~{n_frac*100:.1f}% N): added {f_on:.0f} kg organic N -> {n2o:.1f} kg field N2O "
            "(IPCC 2019 direct + indirect, screening N content)")
    return n2o, note


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
    base_ef1 = getattr(region, "ipcc_n2o_ef1", None) or RUST_EF1
    scale = assessment.get("ipcc_ef1_scale")
    if scale is not None:
        try:
            scale = float(scale)
        except (TypeError, ValueError):
            scale = None
    ef1 = _effective_ef1(assessment, region)
    factor = 1.0

    if ef1 and ef1 != RUST_EF1:
        factor *= ef1 / RUST_EF1
        if scale is not None and scale != 1.0:
            notes.append(
                f"literature-linked EF1 scale {scale:g}× applied on region IPCC EF1 "
                f"({base_ef1} -> {ef1:g} kg N2O-N/kg N)"
            )
        else:
            notes.append(
                f"field N2O scaled to the region's IPCC EF1 ({ef1} kg N2O-N/kg N, "
                f"{getattr(region, 'climate_zone', 'regional')} climate) from the kernel default {RUST_EF1}")

    if _has_legume_partner(assessment):
        factor *= (1.0 - LEGUME_N2O_CREDIT)
        notes.append(
            f"legume intercrop present: field N2O reduced by {int(LEGUME_N2O_CREDIT*100)}% "
            "for biological nitrogen fixation substituting synthetic fertiliser (screening assumption)")

    # Scale the synthetic-N N2O (region climate + legume credit)
    if factor == 1.0:
        adjusted = list(on_farm_lci)
    else:
        adjusted = []
        for f in on_farm_lci:
            if f.get("substance") == "N2O":
                g = dict(f)
                g["quantity"] = (g.get("quantity") or 0.0) * factor
                adjusted.append(g)
            else:
                adjusted.append(f)

    # Add compost/manure organic-N N2O (at the region EF1, not legume-credited — it is a
    # separate organic input, not a synthetic-N substitution).
    compost_n2o, compost_note = _compost_n2o(assessment, region)
    if compost_n2o > 0:
        adjusted.append({"substance": "N2O", "quantity": compost_n2o, "unit": "kg"})
        if compost_note:
            notes.append(compost_note)

    return adjusted, notes
