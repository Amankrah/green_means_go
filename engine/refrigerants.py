#!/usr/bin/env python3
"""
refrigerants.py : on-site refrigerant (F-gas) leakage as a climate contribution.

Refrigerant leakage is treated the standard way (IPCC / GHG Protocol): leaked mass x
GWP100 = kg CO2-eq. The ecoinvent method pack in the store does not carry climate CFs on
the F-gas elementary flows for every method (queried 2026-11-25: no "Climate change" CF on
HFC-134a / HFC-125 / HFC-143a / HFC-32 under "EF v3.1" or "ReCiPe 2016 v1.03, midpoint (H)"),
so the GWP is applied here, but on the SAME basis as the selected LCIA method so that the
on-site term is characterised consistently with the background:

  * EF 3.1 / IPCC 2021 / default: IPCC AR6 GWP100 (Forster et al. 2021, AR6 WG1 Ch 7
    Table 7.15 / 7.SM.7), as reproduced in data/IPCC GWP/Global-Warming-Potential-Values
    (August 2024).pdf (GHG Protocol v2.0, AR6 column).
  * ReCiPe 2016 (H): ReCiPe 2016 v1.1 Hierarchist GWP100 (IPCC AR5 incl. climate-carbon
    feedback), read from data/ReCipe2016/ReCiPe2016_CFs_v1.1_20180117.xlsx, sheet
    "Global Warming", column "Hierarchist".

Blends are the mass-fraction-weighted mean of their component GWPs (ASHRAE Standard 34
compositions); the arithmetic is written out next to each blend and recomputed in
engine/test_refrigerants.py so every number is auditable.
"""
from __future__ import annotations

# ---- pure gases ------------------------------------------------------------------------
# AR6 GWP100. Source: data/IPCC GWP/Global-Warming-Potential-Values (August 2024).pdf,
# AR6 column (HFC-32 771, HFC-125 3,740, HFC-143a 5,810, HFC-152a 164, HCFC-22 1,960,
# HFO-1234yf 0.501, HFO-1234ze(E) 1.37, CO2 1). HFC-134a: AR6 WG1 Table 7.15 lists 1526;
# the GHG Protocol PDF rounds it to 1,530 (3 significant figures). 1526 is kept (the
# unrounded AR6 value). R-290 propane 0.02: AR6 WG1 Table 7.SM.7 (not in the on-disk PDF).
# R-717 ammonia and R-600a isobutane: not GHGs in the AR6 tables (no GWP100 listed) -> 0.
_AR6_PURE = {
    "R-134a": 1526.0,
    "R-125": 3740.0,
    "R-143a": 5810.0,
    "R-32": 771.0,
    "R-152a": 164.0,
    "R-22": 1960.0,
    "R-717": 0.0,
    "R-744": 1.0,
    "R-290": 0.02,
    "R-600a": 0.0,
    "R-1234yf": 0.501,
    "R-1234ze": 1.37,     # (E)-isomer, the commercial refrigerant
}

# ReCiPe 2016 v1.1 Hierarchist GWP100 (ReCiPe2016_CFs_v1.1_20180117.xlsx, "Global Warming",
# rows HCFC-22 2106, HFC-32 817, HFC-125 3691, HFC-134a 1549, HFC-143a 5508, HFC-152a 167,
# HFC-1234yf 0, (E)-HFC-1234ze 1, Carbon dioxide 1). Propane/ammonia/isobutane are not
# GHGs in ReCiPe's climate table -> 0.
_RECIPE_PURE = {
    "R-134a": 1549.0,
    "R-125": 3691.0,
    "R-143a": 5508.0,
    "R-32": 817.0,
    "R-152a": 167.0,
    "R-22": 2106.0,
    "R-717": 0.0,
    "R-744": 1.0,
    "R-290": 0.0,
    "R-600a": 0.0,
    "R-1234yf": 0.0,
    "R-1234ze": 1.0,
}

# ---- blends: mass fractions (ASHRAE Standard 34 / ANSI-ASHRAE 34-2022 designations) -----
BLEND_COMPOSITION: dict[str, dict[str, float]] = {
    "R-404A": {"R-125": 0.44, "R-143a": 0.52, "R-134a": 0.04},
    "R-507A": {"R-125": 0.50, "R-143a": 0.50},
    "R-410A": {"R-32": 0.50, "R-125": 0.50},
    "R-407C": {"R-32": 0.23, "R-125": 0.25, "R-134a": 0.52},
    "R-448A": {"R-32": 0.26, "R-125": 0.26, "R-1234yf": 0.20, "R-134a": 0.21, "R-1234ze": 0.07},
    "R-449A": {"R-32": 0.243, "R-125": 0.247, "R-1234yf": 0.253, "R-134a": 0.257},
    "R-513A": {"R-1234yf": 0.56, "R-134a": 0.44},
}
# AR6 worked values (component GWP x mass fraction):
#   R-404A = 0.44*3740 + 0.52*5810 + 0.04*1526                     = 4727.8
#   R-507A = 0.50*3740 + 0.50*5810                                  = 4775.0
#   R-410A = 0.50*771  + 0.50*3740                                  = 2255.5
#   R-407C = 0.23*771  + 0.25*3740 + 0.52*1526                      = 1905.9
#   R-448A = 0.26*771  + 0.26*3740 + 0.20*0.501 + 0.21*1526 + 0.07*1.37 = 1493.4
#   R-449A = 0.243*771 + 0.247*3740 + 0.253*0.501 + 0.257*1526      = 1503.4
#   R-513A = 0.56*0.501 + 0.44*1526                                 = 671.7
# (The previous table had R-404A 3728, R-507A 3985, R-448A 1387, R-449A 1397, R-513A 631,
# none of which reproduce from the AR6 component values.)


def _blend_gwp(blend: str, pure: dict[str, float]) -> float:
    return sum(frac * pure[comp] for comp, frac in BLEND_COMPOSITION[blend].items())


def _table(pure: dict[str, float]) -> dict[str, float]:
    out = dict(pure)
    for b in BLEND_COMPOSITION:
        out[b] = round(_blend_gwp(b, pure), 1)
    return out


AR6_GWP100 = _table(_AR6_PURE)
RECIPE_H_GWP100 = _table(_RECIPE_PURE)

# Aliases (designation synonyms) -> canonical designation.
_ALIASES = {
    "HFC-134a": "R-134a", "HFC-125": "R-125", "HFC-143a": "R-143a", "HFC-32": "R-32",
    "HFC-152a": "R-152a", "HCFC-22": "R-22", "Ammonia": "R-717", "NH3": "R-717",
    "CO2": "R-744", "Propane": "R-290", "Isobutane": "R-600a",
}

# Back-compat: AR6 table including aliases (some callers import REFRIGERANT_GWP100).
REFRIGERANT_GWP100 = {**AR6_GWP100, **{a: AR6_GWP100[c] for a, c in _ALIASES.items()}}

# The designations the API accepts (app/processing/models.py validates against this list).
KNOWN_REFRIGERANTS: tuple[str, ...] = tuple(REFRIGERANT_GWP100)


def _key(name: str) -> str:
    """Normalise a designation for lookup: case, spaces and hyphens are ignored, so
    'r134a', 'R 134a' and 'R-134a' are the same gas."""
    return (name or "").strip().upper().replace(" ", "").replace("-", "")


_CANONICAL = {_key(k): k for k in REFRIGERANT_GWP100}
_TO_DESIGNATION = {**{_key(k): k for k in AR6_GWP100}, **{_key(a): c for a, c in _ALIASES.items()}}


def canonical_name(gas: str | None) -> str | None:
    """The table's spelling of `gas`, or None when it is not a known refrigerant."""
    if not gas:
        return None
    return _CANONICAL.get(_key(gas))


def gwp_basis_for(method: str | None) -> str:
    """'recipe_h' for ReCiPe 2016 methods, else 'ar6' (EF 3.1, IPCC 2021, unspecified)."""
    return "recipe_h" if method and "recipe" in method.lower() else "ar6"


def gwp100(gas: str | None, method: str | None = None) -> float | None:
    """GWP100 of `gas` on the basis matching `method` (None when the gas is unknown)."""
    desig = _TO_DESIGNATION.get(_key(gas or ""))
    if desig is None:
        return None
    table = RECIPE_H_GWP100 if gwp_basis_for(method) == "recipe_h" else AR6_GWP100
    return table[desig]


def refrigerant_co2e(gas: str | None, leaked_kg: float, method: str | None = None) -> tuple[float, str]:
    """Return (kg CO2-eq, note) for `leaked_kg` of refrigerant `gas`.

    The GWP basis follows `method` (ReCiPe 2016 -> ReCiPe Hierarchist GWP100; anything else
    -> IPCC AR6 GWP100), so the on-site term is characterised like the background. Raises
    ValueError for an unknown gas with a positive leak: there is no default GWP."""
    if not leaked_kg or leaked_kg <= 0:
        return 0.0, ""
    gwp = gwp100(gas, method)
    if gwp is None:
        raise ValueError(
            f"refrigerant '{gas}' is not a known designation; no GWP is assumed. Use one of: "
            + ", ".join(KNOWN_REFRIGERANTS))
    basis = ("ReCiPe 2016 v1.1 Hierarchist GWP100" if gwp_basis_for(method) == "recipe_h"
             else "IPCC AR6 GWP100")
    return leaked_kg * gwp, f"refrigerant {gas} leakage at {basis} = {gwp:g} kg CO2-eq per kg"


# ---- default annual leakage from charge (cold storage) ---------------------------------
# IPCC 2006 Guidelines, Vol 3 (IPPU), Ch 7, Table 7.9 "Estimates for charge, lifetime and
# emission factors for refrigeration and air-conditioning systems": operating emission
# factor (% of initial charge per year) for "Industrial refrigeration including food
# processing and cold storage" = 7-25 %. IPCC gives a range, not a point default; the
# central value used here is the arithmetic midpoint (16 %/yr), a practitioner choice that
# is disclosed in the note, with the 7 % and 25 % bounds reported for sensitivity.
COLD_STORAGE_LEAK_RATE_RANGE = (0.07, 0.25)
COLD_STORAGE_LEAK_RATE = sum(COLD_STORAGE_LEAK_RATE_RANGE) / 2.0
LEAK_RATE_SOURCE = ("IPCC 2006 Guidelines Vol 3 Ch 7 Table 7.9, operating emission factor for "
                    "industrial refrigeration incl. food processing and cold storage, 7-25 % of "
                    "charge per year (midpoint 16 % used)")


def annual_leakage_from_charge(charge_kg: float | None,
                               leak_rate: float | None = None) -> tuple[float, dict]:
    """Annual refrigerant leakage (kg/yr) = charge x operating emission factor.

    Returns (kg_per_year, info) where info carries the rate used, its IPCC range and the
    source string; (0.0, {}) when no positive charge is given."""
    try:
        charge = float(charge_kg or 0.0)
    except (TypeError, ValueError):
        charge = 0.0
    if charge <= 0:
        return 0.0, {}
    rate = COLD_STORAGE_LEAK_RATE if leak_rate is None else float(leak_rate)
    lo, hi = COLD_STORAGE_LEAK_RATE_RANGE
    return charge * rate, {
        "charge_kg": charge, "leak_rate": rate,
        "leak_rate_range": [lo, hi],
        "kg_per_year_range": [charge * lo, charge * hi],
        "source": LEAK_RATE_SOURCE,
    }


def storage_leakage_co2e(storage: dict | None, method: str | None = None) -> tuple[float, str, dict]:
    """Cold-storage refrigerant leakage for the CONTRACT §1 `equipment_energy.storage` block.

    Books leakage only when facilities include "Cold Storage" AND both refrigerant and
    charge are given. Returns (kg CO2-eq per year, note, info)."""
    st = storage or {}
    facilities = [str(f).lower() for f in (st.get("facilities") or [])]
    if not any("cold" in f for f in facilities):
        return 0.0, "", {}
    gas = st.get("refrigerant")
    kg, info = annual_leakage_from_charge(st.get("refrigerant_charge_kg"))
    if not gas or not kg:
        return 0.0, ("cold storage declared without refrigerant type and charge: refrigerant "
                     "leakage not modelled"), {}
    co2e, note = refrigerant_co2e(gas, kg, method)
    info = {**info, "refrigerant": gas, "kg_co2e": co2e}
    return co2e, (f"cold-storage refrigerant leakage {kg:.3g} kg/yr ({info['charge_kg']:g} kg charge x "
                  f"{info['leak_rate']*100:.0f} %/yr; {LEAK_RATE_SOURCE}); {note}"), info
