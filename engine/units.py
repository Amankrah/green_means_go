#!/usr/bin/env python3
"""
units.py: cited unit conversion for purchased-input amounts.

Every purchased input is solved against a background dataset whose reference flow has a
unit (`ref_unit`: kg, MJ, kWh, m3, t*km, ...). The amount handed to the solver MUST be in
that unit. `to_ref_unit()` converts it or raises `UnitMismatchError`; a mismatch never
passes through silently (the kerosene case used to send MJ against a per-kg dataset, a
~40x error).

Conversions:
  * within a unit family (mass, energy, volume, transport, area-time): exact SI factors;
  * energy <-> mass: the fuel's net calorific value (LHV);
  * volume <-> mass: the fuel's density;
  both looked up by substance (FUELS below, cited per row).

Sources:
  IPCC 2006 Guidelines Vol 2 (Energy) Ch 1 Table 1.2: default net calorific values (TJ/Gg =
      MJ/kg): gas/diesel oil 43.0, motor gasoline 44.3, other kerosene 43.8, LPG 47.3,
      natural gas 48.0, wood/wood waste 15.6, charcoal 29.5, biodiesels 27.0.
  Densities (kg/L): diesel 0.837, gasoline 0.741, LPG 0.533 as tabulated with the IPCC
      factors in FAO EX-ACT v9.4.2 ('IPCC' sheet, fuel table rows 1727-1735); kerosene
      0.80 and biodiesel 0.88 are typical product densities (UK DESNZ GHG Conversion
      Factors, fuel properties); water 1.0 kg/L.
"""
from __future__ import annotations

SRC_NCV = "IPCC 2006 Vol 2 Ch 1 Table 1.2 (default NCV)"
SRC_DENS = "FAO EX-ACT v9.4.2 'IPCC' sheet fuel densities"
SRC_DENS_DESNZ = "UK DESNZ GHG Conversion Factors, fuel properties (typical density)"

# substance -> {lhv MJ/kg, density kg/L, sources}
FUELS: dict[str, dict] = {
    "diesel":      {"lhv": 43.0, "density": 0.837, "src": f"{SRC_NCV}; {SRC_DENS}"},
    "petrol":      {"lhv": 44.3, "density": 0.741, "src": f"{SRC_NCV}; {SRC_DENS}"},
    "kerosene":    {"lhv": 43.8, "density": 0.80, "src": f"{SRC_NCV}; {SRC_DENS_DESNZ}"},
    "lpg":         {"lhv": 47.3, "density": 0.533, "src": f"{SRC_NCV}; {SRC_DENS}"},
    "natural gas": {"lhv": 48.0, "density": None, "src": SRC_NCV},
    "firewood":    {"lhv": 15.6, "density": None, "src": SRC_NCV},
    "charcoal":    {"lhv": 29.5, "density": None, "src": SRC_NCV},
    "biodiesel":   {"lhv": 27.0, "density": 0.88, "src": f"{SRC_NCV}; {SRC_DENS_DESNZ}"},
    "water":       {"lhv": None, "density": 1.0, "src": "water density 1 kg/L"},
}

# word in an input name -> FUELS key (first match wins; order matters)
_SUBSTANCE_WORDS = (
    ("biodiesel", "biodiesel"),
    ("liquefied petroleum", "lpg"), ("lpg", "lpg"), ("butane", "lpg"), ("propane", "lpg"),
    ("kerosene", "kerosene"), ("paraffin", "kerosene"),
    ("charcoal", "charcoal"),
    ("firewood", "firewood"), ("fuelwood", "firewood"), ("fuel wood", "firewood"),
    ("wood", "firewood"), ("cleft timber", "firewood"),
    ("diesel", "diesel"), ("gas oil", "diesel"), ("gasoil", "diesel"),
    ("petrol", "petrol"), ("gasoline", "petrol"),
    ("natural gas", "natural gas"),
    ("water", "water"),
)

# unit alias -> (family, factor to the family base unit)
# bases: mass kg, energy MJ, volume L, transport t*km, area-time m2*a, count item
_UNITS: dict[str, tuple[str, float]] = {
    "kg": ("mass", 1.0), "g": ("mass", 1e-3), "t": ("mass", 1000.0),
    "tonne": ("mass", 1000.0), "tonnes": ("mass", 1000.0), "ton": ("mass", 1000.0),
    "mj": ("energy", 1.0), "kj": ("energy", 1e-3), "gj": ("energy", 1000.0),
    "tj": ("energy", 1e6), "kwh": ("energy", 3.6), "mwh": ("energy", 3600.0),
    "l": ("volume", 1.0), "litre": ("volume", 1.0), "liter": ("volume", 1.0),
    "litres": ("volume", 1.0), "liters": ("volume", 1.0),
    "m3": ("volume", 1000.0), "m^3": ("volume", 1000.0),
    "t*km": ("transport", 1.0), "tkm": ("transport", 1.0), "t.km": ("transport", 1.0),
    "kg*km": ("transport", 1e-3),
    "m2*a": ("area_time", 1.0), "m2a": ("area_time", 1.0), "ha*a": ("area_time", 1e4),
    "item(s)": ("count", 1.0), "item": ("count", 1.0), "items": ("count", 1.0),
    "unit": ("count", 1.0), "p": ("count", 1.0),
}


class UnitMismatchError(ValueError):
    """The input amount's unit cannot be converted to the matched dataset's ref unit."""


def _norm(unit) -> str:
    return str(unit or "").strip().lower().replace(" ", "")


def substance_of(inp: dict) -> str | None:
    """Fuel/substance key for an input dict, from an explicit 'substance' or its names."""
    explicit = inp.get("substance")
    if explicit and str(explicit).lower() in FUELS:
        return str(explicit).lower()
    text = " ".join(str(inp.get(k) or "") for k in ("name", "match_as")).lower()
    for word, key in _SUBSTANCE_WORDS:
        if word in text:
            return key
    return None


def convert(amount: float, from_unit: str, to_unit: str, substance: str | None = None) -> float:
    """Convert `amount` from `from_unit` to `to_unit`. Raises UnitMismatchError if the units
    are unknown or the conversion needs a property (LHV, density) the substance lacks."""
    fu, tu = _norm(from_unit), _norm(to_unit)
    if fu == tu:
        return float(amount)
    if fu not in _UNITS or tu not in _UNITS:
        raise UnitMismatchError(f"unknown unit '{from_unit}' or '{to_unit}'")
    ffam, ff = _UNITS[fu]
    tfam, tf = _UNITS[tu]
    base = float(amount) * ff                      # in the from-family base unit
    if ffam == tfam:
        return base / tf
    props = FUELS.get(substance or "")
    if not props:
        raise UnitMismatchError(
            f"cannot convert {ffam} ('{from_unit}') to {tfam} ('{to_unit}') without a "
            f"known substance (got {substance!r})")
    # bring to mass (kg), then to the target family
    if ffam == "mass":
        kg = base
    elif ffam == "energy" and props.get("lhv"):
        kg = base / props["lhv"]
    elif ffam == "volume" and props.get("density"):
        kg = base * props["density"]
    else:
        raise UnitMismatchError(f"no {ffam}->mass property for '{substance}'")
    if tfam == "mass":
        return kg / tf
    if tfam == "energy" and props.get("lhv"):
        return kg * props["lhv"] / tf
    if tfam == "volume" and props.get("density"):
        return kg / props["density"] / tf
    raise UnitMismatchError(f"no mass->{tfam} property for '{substance}'")


def to_ref_unit(inp: dict, ref_unit: str | None) -> tuple[float, str | None]:
    """Amount of purchased input `inp` ({name, amount, unit, ...}) expressed in the matched
    dataset's `ref_unit`. Returns (amount, note); note is None when no conversion was needed.
    Raises UnitMismatchError when the units cannot be reconciled."""
    amount = float(inp["amount"])
    unit = inp.get("unit")
    if not unit or not ref_unit:
        note = None
        if not unit and ref_unit:
            note = (f"'{inp.get('name')}' has no unit; amount taken as the matched dataset's "
                    f"reference unit '{ref_unit}'")
        return amount, note
    if _norm(unit) == _norm(ref_unit):
        return amount, None
    sub = substance_of(inp)
    try:
        out = convert(amount, unit, ref_unit, sub)
    except UnitMismatchError as e:
        raise UnitMismatchError(
            f"unit mismatch for '{inp.get('name')}': amount in '{unit}' but the matched "
            f"dataset is per '{ref_unit}' and no conversion exists ({e}); input excluded") from e
    src = FUELS.get(sub or "", {}).get("src", "SI factors")
    fam_change = _UNITS[_norm(unit)][0] != _UNITS[_norm(ref_unit)][0]
    note = (f"'{inp.get('name')}': {amount:g} {unit} converted to {out:g} {ref_unit}"
            + (f" ({sub}; {src})" if fam_change else ""))
    return out, note
