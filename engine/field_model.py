#!/usr/bin/env python3
"""
field_model.py: expert-level adjustments to the on-farm field emissions, driven by the
real farm inputs, applied on top of the Rust LCI kernel's output.

  1. Regional / climate N2O. The kernel now receives the region's IPCC 2019 parameters as
     `field_parameters` (engine/field_params.py) and applies them to every pathway (EF1
     synthetic and "other N", FracGASF, FracLEACH, EF4, EF5). When an assessment reaches
     here WITHOUT field_parameters (legacy callers), the kernel used the aggregated 0.01 and
     we fall back to the old first-order correction: scale the synthetic-N N2O by
     (region EF1 / 0.01), and residue/organic N2O by (EF1 other / 0.01).

  2. Legume intercrop credit. When a crop is intercropped with (or rotated after) a legume
     PARTNER, biological fixation supplies part of the system's N, so less synthetic N is
     needed for the same output. We credit a modest reduction in the SYNTHETIC-fertiliser
     N2O only. Consistency with IPCC 2019 (no double counting):
       * BNF is not an N input for direct N2O (IPCC 2019 Vol 4 Ch 11 footnote 1); a legume
         crop's own N2O comes only from its residue N (Table 11.1A rows), computed in the
         kernel for that crop. A legume never self-credits.
       * The credit is not applied to residue, organic-fertiliser, compost, burning,
         land-use-change or combustion N2O: it represents avoided synthetic N only.
     This is a documented screening value choice, not a measured value.

  3. Compost / manure organic N (IPCC 2019 Tier 1 F_ON) at the EF1 for other N inputs,
     FracGASM and the region's FracLEACH/EF4/EF5.

  4. Perennials (engine/perennials.py): establishment amortisation, permanent-crop land
     occupation. Direct land-use change (engine/land_use_change.py) when declared.

  5. Direct combustion flows of LPG/kerosene/firewood/charcoal (engine/fuels.py), passed
     in on the assessment as `direct_combustion_lci` by engine/service.py.
"""
from __future__ import annotations

try:
    from . import field_params as _fp
    from . import perennials as _per
    from . import land_use_change as _luc
except ImportError:
    import field_params as _fp
    import perennials as _per
    import land_use_change as _luc

RUST_EF1 = 0.01                       # the kernel's default EF1 (aggregated IPCC 2019)
LEGUMES = {"cowpea", "groundnut", "peanut", "soybean", "soya", "bean", "pea",
           "lentil", "chickpea", "pigeon pea", "mucuna", "lablab"}
# Fraction of the synthetic-N-driven N2O offset by a legume intercrop partner (screening
# assumption; legume fixation substitutes for part of the synthetic N requirement).
LEGUME_N2O_CREDIT = 0.20

# Flow origins (set by rust_kernel.extract_onfarm_lci) that the legume credit and the legacy
# synthetic-EF1 scaling apply to. Untagged N2O is treated as synthetic (legacy behaviour).
SYNTHETIC_ORIGINS = (None, "synthetic_fertiliser")
OTHER_N_ORIGINS = ("crop_residues", "organic_fertiliser")

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


def _params(assessment: dict, region) -> dict:
    """Field parameters in force: the ones injected for the kernel, else region-derived."""
    fp = assessment.get("field_parameters")
    if isinstance(fp, dict) and fp:
        return {**_fp.AGGREGATED, **fp}
    params, _ = _fp.field_parameters(region, assessment)
    return params


def _compost_n2o(assessment: dict, region) -> tuple[float, str | None]:
    """Direct + indirect field N2O (kg) from applied compost/manure organic N, per IPCC
    2019 Tier 1 (EF1 for other N inputs, FracGASM, FracLEACH, EF4, EF5). Returns
    (n2o_kg, note). Zero if no rate is given."""
    sm = ((assessment.get("management_practices") or {}).get("soil_management")) or {}
    rate_t_ha = sm.get("compost_application_rate")
    if not rate_t_ha or not sm.get("uses_compost"):
        return 0.0, None
    total_area = sum((f.get("area_allocated") or 0) for f in (assessment.get("foods") or []))
    if total_area <= 0:
        return 0.0, None
    source = sm.get("compost_source") or ""
    n_frac = COMPOST_N_FRACTION.get(source, DEFAULT_COMPOST_N)
    p = _params(assessment, region)
    # organic N applied (kg) = rate(t/ha) x 1000 x area(ha) x N-fraction
    f_on = rate_t_ha * 1000.0 * total_area * n_frac
    n2o = f_on * (p["ef1_other"] + p["frac_gasm"] * p["ef4"]
                  + p["frac_leach"] * p["ef5"]) * N2O_N_TO_N2O
    if n2o <= 0:
        return 0.0, None
    note = (f"compost/manure applied ({rate_t_ha:g} t/ha, {source or 'unspecified'}, "
            f"~{n_frac*100:.1f}% N): added {f_on:.0f} kg organic N -> {n2o:.1f} kg field N2O "
            f"(IPCC 2019 direct + indirect at EF1 other N {p['ef1_other']:g}, screening N content)")
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
            # legume neighbours/rotation only, excluding this crop's own name
            for name in partners + rotation:
                if name == own:
                    continue
                if any(leg in name for leg in LEGUMES):
                    return True
    return False


def adjust_field_emissions(on_farm_lci: list[dict], assessment: dict, region) -> tuple[list[dict], list[str]]:
    """Return (adjusted_flows, notes). Applies the climate correction (legacy callers only),
    the legume intercrop credit on synthetic-fertiliser N2O, compost N2O, perennial
    amortisation, declared dLUC and direct fuel-combustion flows."""
    notes: list[str] = []
    kernel_has_params = isinstance(assessment.get("field_parameters"), dict)

    synthetic_factor = 1.0
    other_factor = 1.0
    if not kernel_has_params:
        base_ef1 = getattr(region, "ipcc_n2o_ef1", None) or RUST_EF1
        scale = assessment.get("ipcc_ef1_scale")
        if scale is not None:
            try:
                scale = float(scale)
            except (TypeError, ValueError):
                scale = None
        ef1 = _effective_ef1(assessment, region)
        if ef1 and ef1 != RUST_EF1:
            synthetic_factor *= ef1 / RUST_EF1
            if scale is not None and scale != 1.0:
                notes.append(
                    f"literature-linked EF1 scale {scale:g}x applied on region IPCC EF1 "
                    f"({base_ef1} -> {ef1:g} kg N2O-N/kg N)"
                )
            else:
                notes.append(
                    f"field N2O scaled to the region's IPCC EF1 ({ef1} kg N2O-N/kg N, "
                    f"{getattr(region, 'climate_zone', 'regional')} climate) from the kernel default {RUST_EF1}")
        p = _params(assessment, region)
        if p["ef1_other"] != RUST_EF1:
            other_factor = p["ef1_other"] / RUST_EF1

    credit = 1.0
    if _has_legume_partner(assessment):
        credit = 1.0 - LEGUME_N2O_CREDIT
        notes.append(
            f"legume intercrop present: synthetic-fertiliser field N2O reduced by "
            f"{int(LEGUME_N2O_CREDIT*100)}% for biological nitrogen fixation substituting "
            "synthetic fertiliser (screening assumption; residue N2O is not credited)")

    adjusted = []
    for f in on_farm_lci:
        if f.get("substance") != "N2O":
            adjusted.append(f)
            continue
        origin = f.get("origin")
        factor = 1.0
        if origin in SYNTHETIC_ORIGINS:
            factor = synthetic_factor * credit
        elif origin in OTHER_N_ORIGINS:
            factor = other_factor
        if factor == 1.0:
            adjusted.append(f)
        else:
            g = dict(f)
            g["quantity"] = (g.get("quantity") or 0.0) * factor
            adjusted.append(g)

    # Compost/manure organic-N N2O (not legume-credited: separate organic input).
    compost_n2o, compost_note = _compost_n2o(assessment, region)
    if compost_n2o > 0:
        adjusted.append({"substance": "N2O", "quantity": compost_n2o, "unit": "kg",
                         "origin": "compost"})
        if compost_note:
            notes.append(compost_note)

    # Direct combustion of LPG / kerosene / firewood / charcoal (engine/fuels.py). Added
    # before the perennial scaling so it is amortised like the fuel's production burden.
    for f in assessment.get("direct_combustion_lci") or []:
        adjusted.append(dict(f))

    # Perennial establishment amortisation + permanent-crop land occupation (scales the
    # annual on-farm flows of a mature year, before adding the already-annualised dLUC).
    adjusted, per_notes = _per.apply_to_field_flows(adjusted, assessment)
    notes += per_notes

    # Direct land-use change (only when declared within 20 years).
    p = _params(assessment, region)
    luc_flows, luc_notes = _luc.dluc_flows(assessment, region, p["ef1_other"],
                                           p["frac_leach"], p["ef5"])
    adjusted += luc_flows
    notes += luc_notes

    return adjusted, notes
