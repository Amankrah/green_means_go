#!/usr/bin/env python3
"""
fuels.py: combustion path for fuels that have no "burned in machinery" dataset in the store
(LPG, kerosene, firewood, charcoal).

Diesel and petrol match ecoinvent/AGRIBALYSE "..., burned in agricultural machinery"
datasets, which already contain the combustion emissions. LPG, kerosene, firewood and
charcoal do not: the store has their PRODUCTION (market) datasets only, and the old path
either collapsed them to diesel or matched kerosene to an aviation dataset with an MJ amount
against a per-kg reference (about 40x overstated). Here each such input is split into:

  1. supply chain: the fuel's production dataset (`match_as`), amount converted to kg with
     engine/units.py;
  2. direct combustion: CO2, CH4 and N2O per MJ burnt from IPCC 2006 Guidelines Vol 2 Ch 2
     Table 2.5 (default emission factors for stationary combustion in the residential and
     agriculture/forestry/fishing categories, kg/TJ). CO2 from biomass (firewood, charcoal)
     is biogenic and characterises to zero; its CH4 and N2O are counted (as non-fossil CH4,
     and N2O).

The combustion flows are returned as direct (on-site) emission flows keyed like the Rust
kernel output (flowmap.ONFARM_FLOWS) so they characterise through the same validated path.
"""
from __future__ import annotations

try:
    from . import units
except ImportError:
    import units

SRC_T2_5 = ("IPCC 2006 Vol 2 Ch 2 Table 2.5 (residential and agriculture/forestry/fishing "
            "stationary combustion, kg/TJ)")

# fuel -> production dataset + IPCC 2006 Vol 2 Table 2.5 factors (kg per TJ)
COMBUSTION: dict[str, dict] = {
    "lpg": {"production": "market for liquefied petroleum gas",
            "co2": 63100.0, "ch4": 5.0, "n2o": 0.1, "biogenic": False},
    "kerosene": {"production": "market for kerosene",
                 "co2": 71900.0, "ch4": 10.0, "n2o": 0.6, "biogenic": False},
    "firewood": {"production": "market for cleft timber, measured as dry mass",
                 "co2": 112000.0, "ch4": 300.0, "n2o": 4.0, "biogenic": True,
                 # cleft timber is per kg DRY mass; firewood is declared as fired. Screening
                 # assumption: air-dried firewood at 15% moisture (wet basis).
                 "dry_fraction": 0.85},
    "charcoal": {"production": "market for charcoal",
                 "co2": 112000.0, "ch4": 200.0, "n2o": 1.0, "biogenic": True},
}

_ENERGY_KINDS = (None, "", "fuel", "energy", "heat", "cooking fuel")


def _is_combustion_input(inp: dict) -> str | None:
    if inp.get("kind") not in _ENERGY_KINDS:
        return None
    sub = units.substance_of(inp)
    return sub if sub in COMBUSTION else None


def expand_fuel_inputs(inputs: list[dict]) -> tuple[list[dict], list[dict], list[str]]:
    """Return (inputs, direct_flows, notes). LPG/kerosene/firewood/charcoal inputs are
    redirected to their production dataset in kg; their combustion emissions are returned
    as direct flows. Other inputs pass through unchanged. An amount whose unit cannot be
    converted is excluded with a validation warning."""
    out: list[dict] = []
    flows: list[dict] = []
    notes: list[str] = []
    for inp in inputs:
        fuel = _is_combustion_input(inp)
        if fuel is None:
            out.append(inp)
            continue
        spec = COMBUSTION[fuel]
        try:
            kg = units.convert(float(inp["amount"]), inp.get("unit") or "kg", "kg", fuel)
        except (units.UnitMismatchError, KeyError, TypeError, ValueError) as e:
            notes.append(f"validation warning: fuel '{inp.get('name')}' amount "
                         f"{inp.get('amount')} {inp.get('unit')} cannot be converted to kg "
                         f"({e}); excluded")
            continue
        if kg <= 0:
            continue
        mj = kg * units.FUELS[fuel]["lhv"]
        tj = mj / 1e6
        # Biogenic CO2 is carbon-neutral by convention and is NOT emitted as a flow: in the
        # store "Carbon dioxide, non-fossil" has no CF of its own and the characterisation
        # bridge would give it the fossil CO2 factor (1.0). Its CH4 and N2O are counted.
        ch4_key = "CH4_bio" if spec["biogenic"] else "CH4"
        terms = [(ch4_key, spec["ch4"]), ("N2O", spec["n2o"])]
        if not spec["biogenic"]:
            terms.insert(0, ("CO2", spec["co2"]))
        for key, factor in terms:
            flows.append({"substance": key, "quantity": tj * factor, "unit": "kg",
                          "origin": f"combustion:{fuel}"})
        prod_kg = kg * spec.get("dry_fraction", 1.0)
        out.append({**inp, "match_as": spec["production"], "amount": prod_kg, "unit": "kg",
                    "kind": "fuel", "substance": fuel,
                    "declared_amount": inp.get("amount"), "declared_unit": inp.get("unit")})
        notes.append(
            f"'{inp.get('name')}': {inp.get('amount'):g} {inp.get('unit')} = {kg:.1f} kg = "
            f"{mj:.0f} MJ; production from '{spec['production']}'"
            + (f" ({prod_kg:.1f} kg dry mass, 15% moisture screening assumption)"
               if "dry_fraction" in spec else "")
            + f"; combustion CO2 {tj*spec['co2']:.1f} kg"
            + (" (biogenic, not counted)" if spec["biogenic"] else "")
            + f", CH4 {tj*spec['ch4']*1000:.1f} g, N2O {tj*spec['n2o']*1000:.2f} g "
            f"({SRC_T2_5}; LHV {units.FUELS[fuel]['lhv']} MJ/kg, {units.SRC_NCV})")
    return out, flows, notes
