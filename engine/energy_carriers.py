#!/usr/bin/env python3
"""
energy_carriers.py: one table for every energy carrier a farm or a processing facility can
declare, so the farm wizard (fuel_consumption, energy_sources, equipment) and the processing
request (electricity supply, fuel_streams) turn into the SAME inventory flows.

Each carrier knows:
  * its natural unit (what users enter: L of diesel, kg of firewood, m3 of biogas, kWh),
  * how to express an amount in the unit of the representative background dataset when that
    unit differs (lower heating values and densities, each with a source string),
  * the representative dataset name to steer the matcher (`match_as`) per use context.

Unit policy (interface with WS1 engine/units.py): every emitted input carries the TRUE unit
of its `amount`. Where the representative dataset is per MJ we express the amount in MJ via
the cited LHV (MJ is a true unit of the fuel quantity) and also carry `native_amount` /
`native_unit` / `lhv_mj_per_unit` so a unit layer can re-derive or audit the conversion.
We never send an amount in one unit against a dataset in another without saying so.
"""
from __future__ import annotations

try:
    from . import units as _units
except ImportError:  # script use
    import units as _units  # type: ignore

# ---- physical properties ---------------------------------------------------------------
# Lower heating values, IPCC 2006 Vol. 2 Ch. 1 Table 1.2 default net calorific values
# (TJ/Gg == MJ/kg). Litre values = NCV x the density in engine/units.FUELS, so the farm,
# the unit layer and the petrol L->kg conversion share one number (the old 38.7 MJ/L diesel
# implied 0.90 kg/L and overstated diesel energy by ~7%).
_DIESEL_L = _units.FUELS["diesel"]["lhv"] * _units.FUELS["diesel"]["density"]      # 35.99
_PETROL_L = _units.FUELS["petrol"]["lhv"] * _units.FUELS["petrol"]["density"]      # 32.83
LHV = {
    # carrier: {unit: (MJ per unit, source)}
    "diesel": {"L": (_DIESEL_L, "IPCC 2006 Vol.2 Ch.1 Table 1.2 gas/diesel oil NCV 43.0 TJ/Gg x "
                                "0.837 kg/L (FAO EX-ACT v9.4.2 'IPCC' sheet density) = 36.0 MJ/L"),
               "kg": (43.0, "IPCC 2006 Vol.2 Ch.1 Table 1.2, gas/diesel oil NCV 43.0 TJ/Gg")},
    "petrol": {"L": (_PETROL_L, "IPCC 2006 Vol.2 Ch.1 Table 1.2 motor gasoline NCV 44.3 TJ/Gg x "
                                "0.741 kg/L (FAO EX-ACT v9.4.2 'IPCC' sheet density) = 32.8 MJ/L"),
               "kg": (44.3, "IPCC 2006 Vol.2 Ch.1 Table 1.2, motor gasoline NCV 44.3 TJ/Gg")},
    "kerosene": {"L": (35.0, "IPCC 2006 Vol.2 Ch.1 Table 1.2, other kerosene NCV 43.8 TJ/Gg x 0.80 kg/L"),
                 "kg": (43.8, "IPCC 2006 Vol.2 Ch.1 Table 1.2, other kerosene NCV 43.8 TJ/Gg")},
    # FAME: the IPCC 'biodiesels' default (27 TJ/Gg, range 13.6-54) is far below FAME's
    # physical LHV, so the Renewable Energy Directive values are used for both units.
    "biodiesel": {"L": (33.0, "Directive (EU) 2018/2001 (RED II) Annex III, biodiesel (FAME) "
                              "33 MJ/L"),
                  "kg": (37.0, "Directive (EU) 2018/2001 (RED II) Annex III, biodiesel (FAME) "
                               "37 MJ/kg")},
    "lpg": {"kg": (47.3, "IPCC 2006 Vol.2 Ch.1 Table 1.2, LPG NCV 47.3 TJ/Gg"),
            "L": (47.3 * 0.54, "IPCC 2006 NCV 47.3 MJ/kg x 0.54 kg/L (commercial propane/butane, "
                               "EN 589 density range 0.50 to 0.58 kg/L)")},
    "natural_gas": {"m3": (48.0 * 0.714, "IPCC 2006 Vol.2 Ch.1 Table 1.2 natural gas NCV 48.0 TJ/Gg "
                                         "x 0.714 kg/m3 (methane, 15 C)")},
    "firewood": {"kg": (15.6, "IPCC 2006 Vol.2 Ch.1 Table 1.2, wood/wood waste NCV 15.6 TJ/Gg")},
    "charcoal": {"kg": (29.5, "IPCC 2006 Vol.2 Ch.1 Table 1.2, charcoal NCV 29.5 TJ/Gg")},
    "biomass_residue": {"kg": (11.6, "IPCC 2006 Vol.2 Ch.1 Table 1.2, other primary solid biomass "
                                     "NCV 11.6 TJ/Gg (palm fibre, palm kernel shell, husks)")},
    "biogas": {"m3": (21.5, "60% CH4 biogas: 0.60 x 35.8 MJ/m3 CH4 LHV (IPCC 2006 Vol.2 Table 1.2 "
                            "methane-rich other biogas; 50.4 MJ/kg x 0.714 kg/m3)")},
}

# Small diesel genset specific fuel consumption, used only when a facility meters its
# generator in kWh instead of litres.
GENSET_L_PER_KWH = 0.30
GENSET_L_PER_KWH_SOURCE = ("typical small (20 to 200 kVA) diesel genset at part load, 0.27 to 0.33 "
                           "L/kWh (IRENA 2015, Off-grid renewable energy systems: status and "
                           "methodological issues, diesel benchmark); verify against the unit's data")

# ---- representative datasets ------------------------------------------------------------
# context: "farm" (field machinery, pumps), "facility" (stationary engines, boilers),
# "genset" (electricity generator), "heat" (stoves, dryers, boilers).
DATASETS = {
    "diesel": {"farm": ("diesel, burned in agricultural machinery", "MJ"),
               "facility": ("diesel, burned in building machine", "MJ"),
               "genset": ("market for diesel, burned in diesel-electric generating set, 18.5kW", "MJ"),
               "heat": ("diesel, burned in building machine", "MJ")},
    # WFLDB (AGRIBALYSE) per-kg combustion dataset: the matcher lands on it for this text,
    # and it includes combustion, so petrol is sent in kg (L x 0.772 kg/L, ratio of the
    # IPCC-based LHVs above).
    "petrol": {"*": ("petrol, unleaded, burned in machinery", "kg")},
    # No kerosene combustion dataset in the store; the supply dataset is per kg. Combustion
    # CO2/CH4/N2O of kerosene is WS1's fuel-combustion path (IPCC 2006 Vol.2 Table 2.5).
    "kerosene": {"*": ("market for kerosene", "kg")},
    "biodiesel": {"*": ("diesel, burned in agricultural machinery", "MJ")},
    "lpg": {"*": ("propane, burned in building machine", "MJ")},
    "natural_gas": {"*": ("heat production, natural gas, at industrial furnace >100kW", "MJ")},
    # Fuel energy is fed as heat energy: conservative by 1/furnace efficiency.
    "firewood": {"*": ("heat production, hardwood chips from forest, at furnace 50kW | heat, central or small-scale, other than natural gas | Cutoff, U", "MJ")},
    # Same combustion proxy, but mill residues are a by-product of the same facility, so the
    # wood supply chain in the proxy overstates them slightly (conservative, noted).
    "biomass_residue": {"*": ("heat production, hardwood chips from forest, at furnace 50kW | heat, central or small-scale, other than natural gas | Cutoff, U", "MJ")},
    # Charcoal production (kiln emissions dominate). Stove combustion CH4/N2O: WS1 path.
    "charcoal": {"*": ("market for charcoal", "kg")},
    "biogas": {"*": ("anaerobic digestion of manure | biogas | Cutoff, U", "m3")},
    "grid": {"*": ("electricity low voltage", "kWh")},
    "solar": {"*": ("electricity production, photovoltaic, 3kWp flat-roof installation, multi-Si | electricity, low voltage | Cutoff, U", "kWh")},
    "hydro": {"*": ("electricity production, hydro, run-of-river | electricity, high voltage | Cutoff, U", "kWh")},
    "wind": {"*": ("electricity production, wind, 1-3MW turbine, onshore | electricity, high voltage | Cutoff, U", "kWh")},
}

NATURAL_UNIT = {
    "diesel": "L", "petrol": "L", "kerosene": "L", "biodiesel": "L", "lpg": "L",
    "natural_gas": "m3", "firewood": "kg", "charcoal": "kg", "biomass_residue": "kg",
    "biogas": "m3", "grid": "kWh", "solar": "kWh", "hydro": "kWh", "wind": "kWh",
}

# Input `kind` per carrier. Only grid electricity is "electricity" (grid_calibration.py acts
# on that kind); on-site renewables must not be recalibrated to the national grid factor.
# Engine fuels are "fuel" (activity_defaults.py treats these as measured fuel); solid
# biomass / biogas used for heat are "heat_fuel" so they do not suppress the machinery-diesel
# default.
# Solid fuels stay kind "fuel" so WS1's engine.fuels.expand_fuel_inputs (which keys on
# kind fuel/energy and lpg/kerosene/firewood/charcoal in the name) can add their combustion.
KIND = {"grid": "electricity", "solar": "electricity_onsite", "hydro": "electricity_onsite",
        "wind": "electricity_onsite", "biomass_residue": "heat_fuel", "biogas": "heat_fuel"}

# Free-text -> carrier key. Order matters: more specific first.
_KEYWORDS = [
    ("palm kernel shell", "biomass_residue"), ("palm fibre", "biomass_residue"),
    ("palm fiber", "biomass_residue"), ("husk", "biomass_residue"), ("biomass", "biomass_residue"),
    # LPG before petrol: "Liquefied Petroleum Gas" contains "petrol".
    ("lpg", "lpg"), ("liquefied petroleum", "lpg"), ("propane", "lpg"), ("butane", "lpg"),
    ("biodiesel", "biodiesel"), ("diesel", "diesel"),
    ("petrol", "petrol"), ("gasoline", "petrol"),
    ("kerosene", "kerosene"), ("paraffin", "kerosene"),
    ("natural gas", "natural_gas"), ("naturalgas", "natural_gas"),
    ("firewood", "firewood"), ("fuelwood", "firewood"), ("wood", "firewood"),
    ("charcoal", "charcoal"),
    ("biogas", "biogas"),
    ("solar", "solar"), ("photovoltaic", "solar"),
    ("hydro", "hydro"), ("wind", "wind"),
    ("grid", "grid"), ("electric", "grid"),
]


def carrier_of(text: str | None) -> str | None:
    """Map a free-text fuel / energy type to a carrier key (None if unrecognised)."""
    low = (text or "").lower()
    for kw, key in _KEYWORDS:
        if kw in low:
            return key
    return None


# Units a fuel amount may be declared in (the request model admits only these).
FUEL_UNITS: tuple[str, ...] = ("L", "kg", "m3", "MJ")

_UNIT_ALIASES = {"l": "L", "litre": "L", "liter": "L", "litres": "L", "liters": "L",
                 "kg": "kg", "kilogram": "kg", "kilograms": "kg", "kgs": "kg",
                 "m3": "m3", "m^3": "m3", "m³": "m3", "cubic metre": "m3", "cubic meter": "m3",
                 "mj": "MJ", "kwh": "kWh"}


def normalise_fuel_unit(u: str | None) -> str | None:
    """Canonical fuel unit for free text ('litres' -> 'L'), or None when `u` is not a fuel
    unit this table knows. Used by the request model so an unknown unit is a 422 instead of
    an input the unit layer later excludes."""
    if not u:
        return None
    canon = _UNIT_ALIASES.get(u.strip().lower())
    return canon if canon in FUEL_UNITS else None


def _norm_unit(u: str | None) -> str | None:
    if not u:
        return None
    return _UNIT_ALIASES.get(u.strip().lower(), u)


def dataset_for(carrier: str, context: str = "*") -> tuple[str, str]:
    d = DATASETS[carrier]
    return d.get(context) or d.get("*") or next(iter(d.values()))


# carrier -> engine/units.FUELS substance key (for the strict convertibility check)
_UNITS_SUBSTANCE = {"diesel": "diesel", "petrol": "petrol", "kerosene": "kerosene", "lpg": "lpg",
                    "natural_gas": "natural gas", "firewood": "firewood", "charcoal": "charcoal",
                    "biodiesel": "biodiesel"}


def carrier_input(carrier: str, amount: float, unit: str | None, *, context: str = "*",
                  name: str | None = None, kind: str | None = None, estimated: bool = False,
                  basis: str | None = None, strict: bool = False) -> tuple[dict | None, str | None]:
    """Build one purchased-input dict for `amount` of `carrier` in `unit` (natural unit when
    None). Returns (input or None, note or None).

    strict=True raises ValueError when the amount's unit can never be expressed in the
    representative dataset's unit (grid electricity in L, firewood in L): the API maps it to
    a 422 instead of the input being silently excluded at solve time."""
    if amount is None or amount <= 0:
        return None, None
    unit = _norm_unit(unit) or NATURAL_UNIT[carrier]
    match_as, ds_unit = dataset_for(carrier, context)
    out_amount, out_unit, lhv = amount, unit, None
    note = None
    if ds_unit != unit:
        if ds_unit == "MJ" and unit in LHV.get(carrier, {}):
            lhv, _src = LHV[carrier][unit]
            out_amount, out_unit = amount * lhv, "MJ"
        elif ds_unit == "kg" and unit == "L" and carrier in ("kerosene", "petrol"):
            # density = litre LHV / mass LHV (kerosene 0.80, petrol 0.741 kg/L, engine/units.FUELS)
            dens = LHV[carrier]["L"][0] / LHV[carrier]["kg"][0]
            out_amount, out_unit = amount * dens, "kg"
        elif ds_unit == "kg" and unit == "MJ" and "kg" in LHV.get(carrier, {}):
            out_amount, out_unit = amount / LHV[carrier]["kg"][0], "kg"
        else:
            sub = _UNITS_SUBSTANCE.get(carrier)
            try:
                _units.convert(1.0, unit, ds_unit, sub)
            except _units.UnitMismatchError as e:
                if strict:
                    raise ValueError(
                        f"{carrier.replace('_', ' ')} amount entered in '{unit}' cannot be expressed "
                        f"in its dataset's unit '{ds_unit}' ({e}); enter it in "
                        f"{NATURAL_UNIT[carrier]}") from e
            # Carry the true unit; the unit layer (engine/units.py) converts or rejects it.
            note = (f"{carrier} amount kept in {unit}; representative dataset is per {ds_unit} "
                    "(unit conversion left to the unit layer)")
    if not name:
        name = carrier.replace("_", " ") + (f" ({context})" if context != "*" else "")
    if kind is None:
        kind = KIND.get(carrier, "fuel")
    inp = {"name": name, "match_as": match_as, "amount": out_amount, "unit": out_unit,
           "kind": kind, "fuel": carrier, "native_amount": amount, "native_unit": unit}
    if lhv:
        inp["lhv_mj_per_unit"] = lhv
    if estimated:
        inp["estimated"] = True
        if basis:
            inp["estimate_meta"] = {"basis": basis}
    return inp, note


def lhv_source(carrier: str, unit: str) -> str | None:
    v = LHV.get(carrier, {}).get(_norm_unit(unit) or "")
    return v[1] if v else None
