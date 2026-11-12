#!/usr/bin/env python3
"""
field_params.py: region/climate IPCC 2019 soil-N parameters for the Rust LCI kernel.

The Rust kernel used to hardcode the aggregated IPCC defaults (EF1 0.010, FracGASF 0.11,
FracLEACH 0.24, EF4 0.010, EF5 0.011) and Python scaled the total N2O by the region EF1
ratio afterwards. That cannot express a dry climate (FracLEACH = 0) or the separate EF1 for
"other N inputs" (residues, organic N). Now the region's parameters go INTO the kernel as
`field_parameters`, so every pathway (direct, volatilisation, leaching, nitrate) uses the
right value end to end.

Region fields are read with getattr so this works before and after the registry gains
explicit fields (WS3b adds frac_gasf, frac_gasm, frac_leach, ef4, ef5). When a field is
absent the IPCC 2019 Refinement default for the region's climate class is used and the
derivation is recorded in the notes.

Sources (IPCC 2019 Refinement to the 2006 Guidelines, Vol 4, Ch 11):
  Table 11.1 (updated): EF1 aggregated 0.010; synthetic fertiliser in wet climates 0.016;
      other N inputs (organic, residues, F_SOM) in wet climates 0.006; all N inputs in dry
      climates 0.005.
  Table 11.3 (updated): EF4 aggregated 0.010, wet 0.014, dry 0.005; EF5 0.011;
      FracGASF 0.11; FracGASM 0.21; FracLEACH-(H) 0.24, zero in dry climates.
  Section 11.2.2.3 text (p 11.25): "for wet climates or in dry climate regions where
      irrigation (other than drip irrigation) is used, the default FracLEACH-(H) is 0.24.
      For dry climates, the default FracLEACH-(H) is zero."
"""
from __future__ import annotations

SRC_T11_1 = "IPCC 2019 Refinement Vol 4 Ch 11 Table 11.1 (updated)"
SRC_T11_3 = "IPCC 2019 Refinement Vol 4 Ch 11 Table 11.3 (updated)"

# Aggregated IPCC 2019 Tier 1 defaults (also the Rust FieldParameters::default()).
AGGREGATED = {
    "ef1_synthetic": 0.010,
    "ef1_other": 0.010,
    "frac_gasf": 0.11,
    "frac_gasm": 0.21,
    "frac_leach": 0.24,
    "ef4": 0.010,
    "ef5": 0.011,
}
# Climate-disaggregated defaults (Table 11.1 / 11.3).
WET = {"ef1_synthetic": 0.016, "ef1_other": 0.006, "ef4": 0.014, "frac_leach": 0.24}
DRY = {"ef1_synthetic": 0.005, "ef1_other": 0.005, "ef4": 0.005, "frac_leach": 0.0}


def climate_class(region) -> str:
    """'wet' | 'dry' | 'aggregated' from the region's EF1 and climate-zone label."""
    ef1 = getattr(region, "ipcc_n2o_ef1", None)
    zone = (getattr(region, "climate_zone", "") or "").lower()
    if ef1 is not None and ef1 >= 0.016:
        return "wet"
    if ef1 is not None and ef1 <= 0.005:
        return "dry"
    if "dry" in zone and "wet" not in zone and "moist" not in zone:
        return "dry"
    if ("wet" in zone or "moist" in zone or "humid" in zone) and "dry" not in zone:
        return "wet"
    return "aggregated"


def _irrigated_non_drip(assessment: dict) -> bool:
    wm = ((assessment.get("management_practices") or {}).get("water_management")) or {}
    system = str(wm.get("irrigation_system") or "").lower()
    if not system or "rainfed" in system or system.startswith("none"):
        return False
    return "drip" not in system


def field_parameters(region, assessment: dict | None = None) -> tuple[dict, list[str]]:
    """Return (params, notes). `params` is the JSON object the Rust kernel reads as
    `field_parameters` (keys of FieldParameters in african_lca_backend models.rs)."""
    assessment = assessment or {}
    cls = climate_class(region)
    base = dict(AGGREGATED)
    if cls == "wet":
        base.update(WET)
    elif cls == "dry":
        base.update(DRY)
    notes: list[str] = []

    ef1 = getattr(region, "ipcc_n2o_ef1", None)
    if ef1 is not None:
        base["ef1_synthetic"] = float(ef1)
    explicit_other = getattr(region, "ipcc_n2o_ef1_other", None)
    if explicit_other is not None:
        base["ef1_other"] = float(explicit_other)
    for key in ("frac_gasf", "frac_gasm", "frac_leach", "ef4", "ef5"):
        val = getattr(region, key, None)
        if val is not None:
            base[key] = float(val)

    # Literature-linked EF1 toggle (ipcc_ef1_scale) applies to both EF1 values.
    scale = assessment.get("ipcc_ef1_scale")
    try:
        scale = float(scale) if scale is not None else None
    except (TypeError, ValueError):
        scale = None
    if scale is not None and scale != 1.0:
        base["ef1_synthetic"] *= scale
        base["ef1_other"] *= scale
        notes.append(f"literature-linked EF1 scale {scale:g}x applied on region IPCC EF1 "
                     f"(synthetic {base['ef1_synthetic']:g}, other N inputs "
                     f"{base['ef1_other']:g} kg N2O-N/kg N)")

    if base["frac_leach"] == 0.0 and _irrigated_non_drip(assessment):
        base["frac_leach"] = 0.24
        notes.append("dry climate but irrigated (not drip): FracLEACH-(H) set to 0.24 "
                     "(IPCC 2019 Vol 4 Ch 11 p 11.25)")

    zone = getattr(region, "climate_zone", "regional")
    notes.append(
        f"field N2O uses IPCC 2019 {cls} parameters for {zone}: EF1 synthetic "
        f"{base['ef1_synthetic']:g}, EF1 other N {base['ef1_other']:g}, FracGASF "
        f"{base['frac_gasf']:g}, FracGASM {base['frac_gasm']:g}, FracLEACH "
        f"{base['frac_leach']:g}, EF4 {base['ef4']:g}, EF5 {base['ef5']:g} "
        f"({SRC_T11_1}; {SRC_T11_3})")
    return base, notes


def prepare_kernel_assessment(assessment: dict, region) -> tuple[dict, list[str]]:
    """Return a copy of `assessment` with `field_parameters` and per-food residue
    `frac_renew` (perennials) injected for the Rust kernel, plus notes. Idempotent: an
    assessment that already carries field_parameters is left as is."""
    try:
        from .perennials import perennial_for
    except ImportError:
        from perennials import perennial_for
    out = dict(assessment)
    notes: list[str] = []
    if "field_parameters" not in out:
        params, notes = field_parameters(region, assessment)
        out["field_parameters"] = params
    foods = []
    for f in out.get("foods") or []:
        p = perennial_for(f.get("name"))
        if p is not None:
            f = dict(f)
            rm = dict(f.get("residue_management") or {})
            rm.setdefault("frac_renew", 1.0 / p["lifetime_years"])
            f["residue_management"] = rm
        foods.append(f)
    if foods:
        out["foods"] = foods
    return out, notes
