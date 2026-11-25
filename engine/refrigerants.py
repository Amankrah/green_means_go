#!/usr/bin/env python3
"""
refrigerants.py : on-site refrigerant (F-gas) leakage as a climate contribution.

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

# The designations the API accepts (app/processing/models.py validates against this list).
KNOWN_REFRIGERANTS: tuple[str, ...] = tuple(REFRIGERANT_GWP100)


def _key(name: str) -> str:
    """Normalise a designation for lookup: case, spaces and hyphens are ignored, so
    'r134a', 'R 134a' and 'R-134a' are the same gas."""
    return (name or "").strip().upper().replace(" ", "").replace("-", "")


_LOOKUP = {_key(k): v for k, v in REFRIGERANT_GWP100.items()}
_CANONICAL = {_key(k): k for k in REFRIGERANT_GWP100}


def canonical_name(gas: str | None) -> str | None:
    """The table's spelling of `gas`, or None when it is not a known refrigerant."""
    if not gas:
        return None
    return _CANONICAL.get(_key(gas))


def refrigerant_co2e(gas: str | None, leaked_kg: float) -> tuple[float, str]:
    """Return (kg CO2-eq, note) for `leaked_kg` of refrigerant `gas` via AR6 GWP100.

    Raises ValueError for an unknown gas with a positive leak. There is no default GWP: the
    request model only admits designations from KNOWN_REFRIGERANTS, so this is a defensive
    check for direct engine callers, not a path a user can reach."""
    if not leaked_kg or leaked_kg <= 0:
        return 0.0, ""
    gwp = _LOOKUP.get(_key(gas))
    if gwp is None:
        raise ValueError(
            f"refrigerant '{gas}' is not a known designation; no GWP is assumed. Use one of: "
            + ", ".join(KNOWN_REFRIGERANTS))
    return leaked_kg * gwp, f"refrigerant {gas} leakage at AR6 GWP100 = {gwp:.0f} kg CO2-eq per kg"
