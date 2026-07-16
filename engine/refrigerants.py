#!/usr/bin/env python3
"""
refrigerants.py — on-site refrigerant (F-gas) leakage as a climate contribution.

Refrigerant leakage is treated the standard way (IPCC / GHG Protocol): leaked mass x
GWP100 = kg CO2-eq. We do this method-agnostically with AR6 GWP100 values rather than
through the LCIA characterization tables, because the method characterization factors are
keyed to specific ecoinvent flow UIDs that do not all align across ReCiPe and EF for the
F-gases, which would make the same leak count differently by region. Refrigerant impact is
overwhelmingly climate, so a single, standard GWP per gas is the defensible screening choice.

Source: IPCC AR6 (2021), 100-year GWP. Blends are the mass-weighted mean of their
component HFCs (shown so the number is auditable).
"""
from __future__ import annotations

# Pure gases, AR6 GWP100.
_PURE = {
    "HFC-134a": 1526.0, "R-134a": 1526.0,
    "HFC-125": 3740.0, "R-125": 3740.0,
    "HFC-143a": 5810.0, "R-143a": 5810.0,
    "HFC-32": 771.0, "R-32": 771.0,
    "HFC-152a": 164.0, "R-152a": 164.0,
    "HCFC-22": 1960.0, "R-22": 1960.0,
    "R-717": 0.0, "Ammonia": 0.0, "NH3": 0.0,      # natural, ~zero GWP
    "R-744": 1.0, "CO2": 1.0,                        # carbon dioxide
    "R-290": 0.02, "Propane": 0.02,                  # natural, ~zero GWP
    "R-600a": 0.0, "Isobutane": 0.0,                 # natural, ~zero GWP
    "R-1234yf": 0.5, "R-1234ze": 1.4,                # HFOs, very low GWP
}

# Common blends, AR6 mass-weighted GWP100 (rounded).
_BLENDS = {
    "R-404A": 3728.0,   # 44% R-125, 4% R-134a, 52% R-143a
    "R-410A": 2256.0,   # 50% R-32, 50% R-125
    "R-407C": 1906.0,   # 23% R-32, 25% R-125, 52% R-134a
    "R-507A": 3985.0,   # 50% R-125, 50% R-143a
    "R-448A": 1387.0, "R-449A": 1397.0, "R-513A": 631.0,
}

REFRIGERANT_GWP100 = {**_PURE, **_BLENDS}

DEFAULT_GWP = 1500.0  # unknown gas: a mid-range HFC value, flagged in the note


def _key(name: str) -> str:
    return (name or "").strip().upper().replace(" ", "")


_LOOKUP = {_key(k): v for k, v in REFRIGERANT_GWP100.items()}


def refrigerant_co2e(gas: str, leaked_kg: float) -> tuple[float, str]:
    """Return (kg CO2-eq, note) for `leaked_kg` of refrigerant `gas` via AR6 GWP100."""
    if not leaked_kg or leaked_kg <= 0:
        return 0.0, ""
    gwp = _LOOKUP.get(_key(gas))
    if gwp is None:
        return leaked_kg * DEFAULT_GWP, (
            f"refrigerant '{gas}' not recognised; used a default GWP100 of {DEFAULT_GWP:.0f} "
            "(AR6). Provide a standard designation (e.g. R-134a, R-404A, Ammonia) to refine it.")
    return leaked_kg * gwp, f"refrigerant {gas} leakage at AR6 GWP100 = {gwp:.0f} kg CO2-eq per kg"
