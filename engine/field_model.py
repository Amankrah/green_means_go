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

  2. Legume intercrop / rotation: DISCLOSURE ONLY, no N2O credit. IPCC 2019 Vol 4 Ch 11
     Eq 11.1 counts the N actually applied (F_SN, F_ON); any synthetic N a legume partner
     saves is already absent from the declared fertiliser rate, so a credit would double
     count it (and would not reduce the fertiliser production burden either). BNF is not an
     N input for direct N2O (Ch 11 footnote 1); a legume's own N2O comes from its residue N
     (Table 11.1A), computed in the kernel.

  3. Compost / manure organic N (IPCC 2019 Tier 1 F_ON) per crop receiving it
     (soil_management.compost_crop_ids, [] = all): direct N2O at EF1 for other N inputs,
     NH3 = F_ON x FracGASM x 17/14, NO3 = F_ON x FracLEACH x 62/14, and indirect N2O from the
     same FracGASM / FracLEACH (EF4, EF5), all at the region's (climate-adjusted) values.
     Manure entered both as an organic fertiliser row and as compost is counted once.

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

# Flow origins (set by rust_kernel.extract_onfarm_lci) that the legacy synthetic-EF1
# scaling applies to. Untagged N2O is treated as synthetic (legacy behaviour).
SYNTHETIC_ORIGINS = (None, "synthetic_fertiliser")
OTHER_N_ORIGINS = ("crop_residues", "organic_fertiliser")

# ---- Compost / manure organic-N -> field N2O (IPCC 2019 Vol.4 Ch.11) --------------------
# Total-N content of the organic amendment, as a fraction of the fresh applied mass, by
# source: AHDB (2017) Nutrient Management Guide (RB209) Section 2, Table 2.2 (cattle FYM
# 6.0 kg N/t fresh) and Table 2.17 (green compost 7.5, green/food compost 11 kg N/t fresh).
# UK analyses: no West African compost/manure N table has been found (IPCC 2019 Vol 4 Ch 10
# gives N excretion, not applied product N), so every result note says so and flows carry
# origin "compost" for the pedigree uncertainty (engine/uncertainty.py). RB209 has no
# farm-made or mixed compost class: those take the higher compost value (green/food).
# Application rate arrives in tonnes/ha/year.
COMPOST_N_SOURCE = ("AHDB RB209 (2017) Tables 2.2 / 2.17 typical UK values, not a regional "
                    "compost/manure analysis")
COMPOST_N_FRACTION = {
    "Animal manure": 0.006,
    "Farm-made compost": 0.011,
    "Purchased compost": 0.011,
    "Green waste/crop residues": 0.0075,
    "Mixed sources": 0.011,
}
DEFAULT_COMPOST_N = 0.011
N2O_N_TO_N2O = 44.0 / 28.0
NH3_N_TO_NH3 = 17.0 / 14.0            # molar mass NH3 / N
NO3_N_TO_NO3 = 62.0 / 14.0            # molar mass NO3 / N
# Soil NOx = 0.21 x N2O (ecoinvent v3 agricultural methodology, Nemecek & Schnetzer 2011;
# same rule as the Rust kernel for fertiliser/residue N2O).
NOX_PER_N2O = 0.21
ORGANIC_FERT_WORDS = ("organic", "manure", "compost", "poultry", "dung", "slurry")


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


def _compost_crops(assessment: dict, sm: dict) -> list[dict]:
    """Foods receiving compost: soil_management.compost_crop_ids, [] = all crops."""
    foods = assessment.get("foods") or []
    ids = [str(i) for i in (sm.get("compost_crop_ids") or [])]
    return [f for f in foods if not ids or str(f.get("id")) in ids]


def _organic_rows_for(assessment: dict, food: dict) -> list[str]:
    """Types of active organic fertiliser rows (kernel-modelled F_ON) applied to `food`."""
    fert = ((assessment.get("management_practices") or {}).get("fertilization")) or {}
    rows = fert.get("fertilizer_applications") if isinstance(fert, dict) else fert
    out = []
    for app in rows or []:
        if not isinstance(app, dict):
            continue
        t = str(app.get("fertilizer_type") or "").lower()
        if not any(w in t for w in ORGANIC_FERT_WORDS):
            continue
        if (app.get("application_rate") or 0) <= 0 or app.get("applications_per_season") == 0:
            continue
        ids = [str(i) for i in (app.get("crop_ids") or [])]
        if not ids or str(food.get("id")) in ids:
            out.append(str(app.get("fertilizer_type")))
    return out


def _is_duplicate_organic(source: str, row_types: list[str]) -> bool:
    """Manure declared as compost AND as an organic fertiliser row, or compost declared as
    both: the same material entered twice."""
    if not row_types:
        return False
    src = source.lower()
    if "manure" in src:
        return True
    return any("compost" in t.lower() for t in row_types)


def _compost_n_flows(assessment: dict, region) -> tuple[list[dict], list[str]]:
    """Field flows from compost/manure organic N (IPCC 2019 Vol 4 Ch 11 Tier 1, F_ON):
    direct N2O (EF1 other N), NH3 (FracGASM), NO3 (FracLEACH) and indirect N2O (EF4, EF5),
    per crop receiving compost. Returns (flows, notes)."""
    sm = ((assessment.get("management_practices") or {}).get("soil_management")) or {}
    rate_t_ha = sm.get("compost_application_rate")
    if not rate_t_ha or rate_t_ha <= 0 or not sm.get("uses_compost"):
        return [], []
    source = sm.get("compost_source") or ""
    n_frac = COMPOST_N_FRACTION.get(source, DEFAULT_COMPOST_N)
    p = _params(assessment, region)
    notes: list[str] = []
    f_on = 0.0
    for food in _compost_crops(assessment, sm):
        area = float(food.get("area_allocated") or 0.0)
        if area <= 0:
            continue
        rows = _organic_rows_for(assessment, food)
        if _is_duplicate_organic(source, rows):
            notes.append(
                f"possible double entry for {food.get('name', 'crop')}: '{source}' compost and "
                f"organic fertiliser row(s) {rows} describe the same material; counted once, "
                "as the fertiliser row (its N2O/NH3/NO3 come from the field kernel)")
            continue
        # organic N applied (kg) = rate(t/ha/yr) x 1000 x area(ha) x N-fraction
        f_on += rate_t_ha * 1000.0 * area * n_frac
    if f_on <= 0:
        return [], notes
    direct = f_on * p["ef1_other"] * N2O_N_TO_N2O
    nh3_n = f_on * p["frac_gasm"]
    no3_n = f_on * p["frac_leach"]
    indirect = (nh3_n * p["ef4"] + no3_n * p["ef5"]) * N2O_N_TO_N2O
    n2o = direct + indirect
    flows = [{"substance": "N2O", "quantity": n2o, "unit": "kg", "origin": "compost"},
             {"substance": "NH3", "quantity": nh3_n * NH3_N_TO_NH3, "unit": "kg", "origin": "compost"},
             {"substance": "NOx", "quantity": n2o * NOX_PER_N2O, "unit": "kg", "origin": "compost"}]
    if no3_n > 0:
        flows.append({"substance": "NO3", "quantity": no3_n * NO3_N_TO_NO3, "unit": "kg",
                      "origin": "compost"})
    notes.append(
        f"compost/manure applied ({rate_t_ha:g} t/ha/yr, {source or 'unspecified'}, "
        f"~{n_frac*100:.1f}% N, {COMPOST_N_SOURCE}): {f_on:.0f} kg organic N -> "
        f"{n2o:.2f} kg N2O (direct EF1 other N {p['ef1_other']:g} + indirect EF4/EF5), "
        f"{nh3_n * NH3_N_TO_NH3:.1f} kg NH3 (FracGASM {p['frac_gasm']:g}, NH3+NOx booked as NH3), "
        f"{no3_n * NO3_N_TO_NO3:.1f} kg NO3 (FracLEACH {p['frac_leach']:g}); IPCC 2019 Vol 4 "
        f"Ch 11 Eq 11.1, 11.9, 11.10, Tables 11.1/11.3; {n2o * NOX_PER_N2O:.2f} kg NOx = 0.21 x N2O "
        "(Nemecek & Schnetzer 2011)")
    return flows, notes


def _compost_n2o(assessment: dict, region) -> tuple[float, str | None]:
    """Total compost/manure N2O (kg) and its note (kept for callers of the old API)."""
    flows, notes = _compost_n_flows(assessment, region)
    n2o = sum(f["quantity"] for f in flows if f["substance"] == "N2O")
    return n2o, (notes[-1] if notes and n2o > 0 else None)


def _legume_partners(food: dict) -> list[str]:
    """Legume intercrop partners / previous rotation crops of `food` (never itself)."""
    own = str(food.get("name", "")).lower()
    pattern = (food.get("cropping_pattern") or "").lower()
    partners = [str(p).lower() for p in (food.get("intercropping_partners") or [])]
    rotation = [str(p).lower() for p in (food.get("rotation_sequence") or [])]
    names = (partners + rotation) if ("intercrop" in pattern or partners) else rotation
    return [n for n in names if n != own and any(leg in n for leg in LEGUMES)]


def _has_legume_partner(assessment: dict) -> bool:
    """True if a crop has a legume intercrop partner or a legume in its rotation. Used for
    DISCLOSURE only: no N2O credit is applied (IPCC 2019 Eq 11.1 counts applied N)."""
    return any(_legume_partners(f) for f in assessment.get("foods") or [])


def legume_notes(assessment: dict) -> list[str]:
    notes = []
    for f in assessment.get("foods") or []:
        legs = _legume_partners(f)
        if legs:
            notes.append(
                f"{f.get('name', 'crop')}: legume intercrop/rotation ({', '.join(legs)}) recorded; "
                "no N2O credit applied: IPCC 2019 Vol 4 Ch 11 Eq 11.1 counts the N actually "
                "applied, so any fertiliser N the legume saves is already in the declared rate; "
                "legume residue N2O is computed from Table 11.1A residue N")
    return notes


def adjust_field_emissions(on_farm_lci: list[dict], assessment: dict, region) -> tuple[list[dict], list[str]]:
    """Return (adjusted_flows, notes). Applies the climate correction (legacy callers only),
    legume disclosure (no credit), compost/manure N2O + NH3 + NO3, perennial amortisation,
    declared dLUC and direct fuel-combustion flows. Field P, heavy-metal disclosure and SOC
    from management are added after the solve by engine/farm_flows.py (store-resolved
    compartments; SOC reported separately)."""
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

    notes += legume_notes(assessment)

    adjusted = []
    for f in on_farm_lci:
        if f.get("substance") != "N2O":
            adjusted.append(f)
            continue
        origin = f.get("origin")
        factor = 1.0
        if origin in SYNTHETIC_ORIGINS:
            factor = synthetic_factor
        elif origin in OTHER_N_ORIGINS:
            factor = other_factor
        if factor == 1.0:
            adjusted.append(f)
        else:
            g = dict(f)
            g["quantity"] = (g.get("quantity") or 0.0) * factor
            adjusted.append(g)

    # Compost/manure organic N: N2O, NH3, NO3 (flowmap keys shared with the kernel).
    compost_flows, compost_notes = _compost_n_flows(assessment, region)
    adjusted += compost_flows
    notes += compost_notes

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
