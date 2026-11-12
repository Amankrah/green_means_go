#!/usr/bin/env python3
"""
inputs.py: auto-extract the purchased inputs (for the supply-chain solver) from a submitted
farm assessment, so the frontend doesn't pass them separately.

Every wizard field that physically implies a flow becomes one here (or an elementary flow in
engine/farm_flows.py):

  Fertiliser   : rate (kg/ha) x applications x area -> kg (AS and CAN steered to their own
                 ecoinvent datasets)
  Seed         : seed rate (kg/ha, user or FAO default by crop/category) x area -> kg
  Pesticides   : kg active ingredient -> AI production dataset (engine/pesticides.py)
  Fuels        : fuel_consumption (L/month x 12), per carrier (diesel, petrol, kerosene, LPG,
                 biodiesel) via engine/energy_carriers.py
  Energy       : energy_sources per type: grid kWh, diesel generator L, solar kWh (PV dataset,
                 capital goods included), biogas m3, firewood kg, charcoal kg
  Equipment    : hours x fuel_efficiency (or ASABE D497 average fuel use from the tractor
                 class) for any carrier NOT metered in fuel_consumption; manual / animal /
                 solar power -> no fuel; electric -> must be metered as electricity
  Irrigation   : pumping energy per m3 (ecoinvent irrigation dataset coefficients) when the
                 farm did not declare its pumping energy; the water itself is an elementary
                 withdrawal flow (engine/farm_flows.py)
  Compost      : purchased compost -> market for compost (farm-made / manure: burden-free
                 under cut-off; their N goes to field N2O, composting emissions to farm_flows)
  Logistics    : packaging of the harvest, transport of inputs to the farm, transport of the
                 harvest to the first point of sale (when a distance is given)
"""
from __future__ import annotations

try:
    from . import energy_carriers as ec
    from . import crop_defaults as cd
    from . import pesticides as pz
except ImportError:  # script use
    import energy_carriers as ec  # type: ignore
    import crop_defaults as cd  # type: ignore
    import pesticides as pz  # type: ignore

# Retained for callers that imported it (legacy litre LHVs; see energy_carriers.LHV).
FUEL_MJ_PER_L = {"diesel": 38.7, "petrol": 34.2, "gasoline": 34.2, "kerosene": 35.0, "biodiesel": 33.0}

# Fertiliser types that need a steer: ammonium sulfate and CAN are distinct products with
# their own ecoinvent datasets, and free-text matching would otherwise drift.
FERTILISER_MATCH = {
    "ammonium sulfate": "market for ammonium sulfate",
    "ammonium sulphate": "market for ammonium sulfate",
    "sulphate of ammonia": "market for ammonium sulfate",
    "calcium ammonium nitrate": "market for calcium ammonium nitrate",
    "(can)": "market for calcium ammonium nitrate",
}

# ---- equipment fuel estimate (only for carriers not metered in fuel_consumption) --------
# ASABE D497.7 (2011) average fuel use for a tractor over its annual use pattern:
#   diesel 0.223 L/h per kW of max PTO power; petrol (gasoline) 0.305 L/h per kW.
ASABE_L_PER_KWH = {"diesel": 0.223, "petrol": 0.305}
ASABE_SOURCE = ("ASABE D497.7 (2011) Agricultural Machinery Management Data, average fuel "
                "consumption: diesel 0.223, gasoline 0.305 L/h per kW max PTO power")
HP_TO_KW = 0.7457
# Rated power from the wizard's tractor class label (midpoint of the stated HP band;
# >100 HP taken as 130 HP).
TRACTOR_CLASS_HP = {"small tractor": 30.0, "medium tractor": 70.0, "large tractor": 130.0}

# ---- irrigation pumping energy per m3 (when the farm did not declare its pumping energy) --
# ecoinvent 3.11 "irrigation, <system>" (RoW) exchanges, MJ of pump operation per m3.
PUMP_MJ_PER_M3 = {
    "surface": {"diesel": 0.1113, "electric": 0.1948},
    "sprinkler": {"diesel": 0.3752, "electric": 0.6566},
    "drip": {"diesel": 0.3003, "electric": 0.5255},
}
PUMP_SOURCE = "ecoinvent 3.11 'irrigation, surface/sprinkler/drip' (RoW): water pump operation per m3"
# Full "name | product | system" strings: the short electric name matched grid electricity.
PUMP_DATASET = {"diesel": "market for water pump operation, diesel | water pump operation, diesel | Cutoff, U",
                "electric": "water pump operation, electric"}

# ---- logistics ------------------------------------------------------------------------
# Packaging of the harvest when the material is given without a mass: one 0.1 kg sack per
# 50 kg of produce = 2 kg per tonne (the processing request's packaging default, 0.1 kg per
# 50 kg package).
PACKAGING_DEFAULT_KG_PER_T = 2.0
FARM_PACKAGING_MATCH = {
    "polypropylene": "market for polypropylene, granulate | polypropylene, granulate | Cutoff, U", "pp": "market for polypropylene, granulate | polypropylene, granulate | Cutoff, U",
    "plastic": "market for polypropylene, granulate | polypropylene, granulate | Cutoff, U", "sack": "market for polypropylene, granulate | polypropylene, granulate | Cutoff, U",
    "jute": "market for kraft paper",     # ecoinvent lacks jute bags; kraft paper fibre proxy
    "paper": "market for kraft paper", "cardboard": "market for corrugated board box",
    "crate": "market for polyethylene, high density, granulate",
    "wood": "market for sawnwood, softwood, raw",
}
# Transport of purchased inputs from supplier to farm when the distance is blank.
INPUT_TRANSPORT_DEFAULT_KM = 230.0
INPUT_TRANSPORT_SOURCE = ("EC (2018) PEFCR Guidance v6.3, s.7.14 default supplier-to-factory "
                          "road transport, 230 km by lorry; applied as a default for farm inputs")
LORRY = "market for transport, freight, lorry, unspecified"
LCV = "market for transport, freight, light commercial vehicle, fleet average"
MARKET_TRANSPORT_MATCH = {
    "large truck": LORRY, "truck": LORRY, "lorry": LORRY,
    "pickup": LCV, "public transport": LCV, "motorcycle": LCV, "tricycle": LCV,
}
ZERO_EMISSION_MODES = ("foot", "head", "bicycle", "donkey", "animal")


def _fuel_word(ft: str) -> tuple[str, float]:
    """Legacy helper (kept for importers): fuel word and litre LHV."""
    key = ec.carrier_of(ft) or "diesel"
    if key not in ("diesel", "petrol", "kerosene", "biodiesel"):
        key = "diesel"
    return key, FUEL_MJ_PER_L[key]


def _classify(kind: str, text: str) -> dict | None:
    """engine.llm.classify (deterministic synonyms, committed cache, then the model unless
    GMG_LLM=0). Returns None on any failure: classification only ever renames an input,
    it never supplies a number, and it must not break an assessment."""
    try:
        try:
            from .llm import classify
        except ImportError:
            from llm import classify  # type: ignore
        return classify(kind, text or "")
    except Exception:
        return None


def carrier_or_classify(text: str | None, notes: list) -> str | None:
    """Fuel carrier for free text: keyword table first, then the controlled-vocabulary
    classifier (trade names such as AGO / PMS / DPK, French terms). A classified label that
    needs confirmation is used but reported so the user can correct it."""
    c = ec.carrier_of(text)
    if c or not text:
        return c
    r = _classify("fuel", text)
    label = (r or {}).get("label")
    c = ec.carrier_of(label) if label else None
    if c:
        msg = (f"fuel type '{text}' read as {label} ({r.get('source')}, confidence "
               f"{float(r.get('confidence') or 0):.2f})")
        if r.get("needs_confirmation"):
            msg += "; please confirm"
        notes.append(msg)
    return c


def _total_area(assessment: dict) -> float:
    return sum((f.get("area_allocated") or 0) for f in (assessment.get("foods") or []))


def _norm(s) -> str:
    return " ".join(str(s or "").lower().split())


def pumping_declared(assessment: dict) -> dict | None:
    """Does the farm already account for its irrigation pumping energy? Returns
    {"power": diesel|petrol|electric|solar|manual|None} when a water pump is listed or a fuel /
    energy line is used for irrigation or pumping; else None."""
    ee = assessment.get("equipment_energy") or {}
    for eq in ee.get("equipment") or []:
        if "pump" in _norm(eq.get("equipment_type")):
            ps = _norm(eq.get("power_source"))
            power = ("manual" if ("manual" in ps or "animal" in ps or "human" in ps)
                     else "solar" if "solar" in ps else "electric" if "electric" in ps
                     else ec.carrier_of(ps) or "diesel")
            return {"power": power}
    for row in (ee.get("fuel_consumption") or []) + (ee.get("energy_sources") or []):
        use = _norm(row.get("primary_use"))
        if "irrig" in use or "pump" in use:
            return {"power": None}
    return None


def is_municipal(source_text) -> bool:
    low = _norm(source_text)
    return "municipal" in low or "tap" in low or "piped" in low


def irrigation_water(assessment: dict) -> dict | None:
    """Irrigation water applied by the farm: {m3, water_source (list), system, estimated,
    source}. A measured volume wins; else the crop-water-need estimate summed over foods.
    Public so other layers (AWARE characterisation, reports) read the same number."""
    mp = assessment.get("management_practices") or {}
    wm = mp.get("water_management") or {}
    system = wm.get("irrigation_system")
    sys_key = cd.irrigation_system_key(system)
    sources = [s for s in (wm.get("water_source") or []) if "rain" not in _norm(s)]
    measured = wm.get("irrigation_water_m3")
    if measured is not None:
        if measured <= 0:
            return None
        return {"m3": float(measured), "water_source": sources, "system": sys_key or "surface",
                "estimated": False, "source": "farmer"}
    if not sys_key:
        return None
    total, srcs = 0.0, []
    for f in assessment.get("foods") or []:
        est = cd.irrigation_default_m3(f, system)
        if est:
            total += est["m3"]
            srcs.append(est["source"])
    if total <= 0:
        return None
    return {"m3": total, "water_source": sources, "system": sys_key, "estimated": True,
            "source": "; ".join(sorted(set(srcs)))}


def _fertiliser_inputs(assessment, total_area, inputs, notes):
    mp = assessment.get("management_practices") or {}
    fert = mp.get("fertilization")
    # Accept either the documented dict shape or a bare list of applications.
    if isinstance(fert, list):
        fert = {"uses_fertilizers": bool(fert), "fertilizer_applications": fert}
    elif not isinstance(fert, dict):
        if fert is not None:
            notes.append("fertilisation data in an unexpected format; skipped")
        fert = {}
    if not (fert.get("uses_fertilizers") or fert.get("fertilizer_applications")):
        return
    if not total_area:
        notes.append("fertiliser reported but no crop area: cannot scale fertiliser inputs")
    for app in fert.get("fertilizer_applications") or []:
        if not isinstance(app, dict):
            continue
        rate = app.get("application_rate") or 0
        n = app.get("applications_per_season") or 1
        kg = rate * n * total_area
        if kg <= 0:
            continue
        ftype = app.get("fertilizer_type", "fertiliser")
        npk = (app.get("npk_ratio") or "").strip()
        name = f"{ftype} {npk}".strip() + " fertiliser"
        row = {"name": name, "amount": kg, "unit": "kg", "kind": "fertiliser"}
        low = _norm(name)
        for kw, ds in FERTILISER_MATCH.items():
            if kw in low:
                row["match_as"] = ds
                break
        inputs.append(row)


def _seed_inputs(assessment, inputs, notes):
    for f in assessment.get("foods") or []:
        area = f.get("area_allocated") or 0
        if area <= 0:
            continue
        sd = cd.seed_default(f)
        if not sd:
            notes.append(f"seed: '{f.get('name')}' is vegetatively propagated / perennial or not "
                         "recognised; planting material not inventoried as seed")
            continue
        row = {"name": f"{f.get('name', 'crop')} seed", "match_as": sd["match_as"],
               "amount": sd["kg_per_ha"] * area, "unit": "kg", "kind": "seed"}
        if sd["estimated"]:
            row["estimated"] = True
            row["estimate_meta"] = {"basis": "default seed rate", "source": sd["source"],
                                    "kg_per_ha": sd["kg_per_ha"]}
        inputs.append(row)


def _energy_inputs(assessment, inputs, notes):
    ee = assessment.get("equipment_energy") or {}
    metered: dict[str, list] = {}       # carrier -> [(primary_use, monthly)]
    for fu in ee.get("fuel_consumption") or []:
        monthly = fu.get("monthly_consumption") or 0
        if monthly <= 0:
            continue
        carrier = carrier_or_classify(fu.get("fuel_type"), notes)
        if not carrier:
            notes.append(f"fuel type '{fu.get('fuel_type')}' not recognised; modelled as diesel")
            carrier = "diesel"
        inp, note = ec.carrier_input(carrier, monthly * 12, fu.get("unit") or "L", context="farm",
                                     name="diesel, burned in agricultural machinery"
                                     if carrier == "diesel" else None)
        if inp:
            inputs.append(inp)
            metered.setdefault(carrier, []).append((_norm(fu.get("primary_use")), monthly))
        if note:
            notes.append(note)

    for en in ee.get("energy_sources") or []:
        et = _norm(en.get("energy_type"))
        monthly = en.get("monthly_consumption") or 0
        if monthly <= 0:
            continue
        annual = monthly * 12
        if "generator" in et:
            # Diesel generator, in litres of diesel. The same stream is often also entered
            # under fuel_consumption: same carrier + same use + same amount counts once.
            use = _norm(en.get("primary_use"))
            if any(u == use and abs(m - monthly) < 1e-9 for u, m in metered.get("diesel", [])):
                notes.append(f"diesel generator '{en.get('primary_use')}' is the same stream as a "
                             "fuel_consumption entry; counted once")
                continue
            inp, note = ec.carrier_input("diesel", annual, en.get("unit") or "L", context="genset",
                                         name="diesel, burned in generator (farm)")
        elif "solar" in et:
            inp, note = ec.carrier_input("solar", annual, en.get("unit") or "kWh",
                                         name="solar PV electricity (on-farm)")
        elif "grid" in et or "electric" in et:
            inp, note = ec.carrier_input("grid", annual, en.get("unit") or "kWh",
                                         name="electricity low voltage")
        else:
            carrier = ec.carrier_of(et)
            if not carrier:
                notes.append(f"energy source '{en.get('energy_type')}' not recognised; not counted")
                continue
            inp, note = ec.carrier_input(carrier, annual, en.get("unit"), context="heat",
                                         name=f"{carrier.replace('_', ' ')} (on-farm)")
        if inp:
            inputs.append(inp)
            metered.setdefault(inp.get("fuel"), []).append((_norm(en.get("primary_use")), monthly))
        if note:
            notes.append(note)

    # Equipment: estimate fuel only for carriers that were NOT metered above, so a measured
    # total is never double counted.
    for eq in ee.get("equipment") or []:
        ps = _norm(eq.get("power_source"))
        hrs = eq.get("hours_per_year") or 0
        etype = _norm(eq.get("equipment_type"))
        if hrs <= 0:
            continue
        if any(w in ps for w in ("manual", "human", "animal")):
            continue          # human / animal labour: outside the system boundary (no fuel)
        if "solar" in ps:
            continue          # solar-powered equipment: no operational fuel
        if "electric" in ps:
            if "grid" not in metered:
                notes.append(f"electric equipment '{eq.get('equipment_type')}': enter its electricity "
                             "under energy sources (kWh); not estimated")
            continue
        carrier = ec.carrier_of(ps) or "diesel"
        if carrier in metered:
            continue
        eff = eq.get("fuel_efficiency")
        basis = None
        if not eff:
            hp = next((v for k, v in TRACTOR_CLASS_HP.items() if k in etype), None)
            l_per_kwh = ASABE_L_PER_KWH.get(carrier)
            if hp and l_per_kwh:
                eff = l_per_kwh * hp * HP_TO_KW
                basis = f"{ASABE_SOURCE}; {hp:g} HP class midpoint"
            else:
                notes.append(f"equipment '{eq.get('equipment_type')}' ({ps or 'unknown power'}) has no "
                             "fuel use per hour and no metered fuel; enter litres per hour")
                continue
        inp, note = ec.carrier_input(carrier, eff * hrs, "L", context="farm",
                                     name="diesel, burned in agricultural machinery"
                                     if carrier == "diesel" else None,
                                     estimated=basis is not None, basis=basis)
        if inp:
            inp["source_equipment"] = eq.get("equipment_type")
            inputs.append(inp)
        if note:
            notes.append(note)


def _irrigation_inputs(assessment, inputs, notes):
    w = irrigation_water(assessment)
    if not w:
        return
    tag = "estimated" if w["estimated"] else "measured"
    # Irrigation from a municipal supply is a purchased product (tap water); natural sources
    # are elementary withdrawals added by engine/farm_flows.py.
    muni = [s for s in w["water_source"] if is_municipal(s)]
    if muni:
        m3 = w["m3"] * len(muni) / len(w["water_source"])
        inputs.append({"name": "irrigation water (municipal supply)", "match_as": "market for tap water",
                       "amount": m3 * 1000.0, "unit": "kg", "kind": "water", "water_source": muni,
                       "irrigation_m3": m3})
    if pumping_declared(assessment):
        notes.append(f"irrigation water {w['m3']:.0f} m3 ({tag}); pumping energy taken from the "
                     "farm's own fuel / energy / equipment data")
        return
    for power, mj_per_m3 in PUMP_MJ_PER_M3[w["system"]].items():
        inputs.append({"name": f"irrigation pumping ({power})", "match_as": PUMP_DATASET[power],
                       "amount": w["m3"] * mj_per_m3, "unit": "MJ", "kind": "irrigation_energy",
                       "estimated": True,
                       "estimate_meta": {"basis": f"{PUMP_SOURCE}, {w['system']}: {mj_per_m3} MJ/m3",
                                         "m3": w["m3"]},
                       "water_source": w["water_source"], "irrigation_m3": w["m3"]})
    notes.append(f"irrigation water {w['m3']:.0f} m3 ({tag}); no pumping energy declared, so the "
                 "ecoinvent irrigation pumping energy per m3 is used")


def _compost_inputs(assessment, total_area, inputs, notes):
    mp = assessment.get("management_practices") or {}
    sm = mp.get("soil_management") or {}
    if not sm.get("uses_compost"):
        return
    src = _norm(sm.get("compost_source"))
    rate_t_ha = sm.get("compost_application_rate")
    if "purchas" in src:
        if rate_t_ha and total_area:
            inputs.append({"name": "compost", "match_as": "market for compost",
                           "amount": rate_t_ha * 1000.0 * total_area, "unit": "kg", "kind": "compost"})
        else:
            notes.append("purchased compost reported but no application rate given; its production "
                         "burden is not quantified")
    elif src:
        notes.append(f"compost source '{sm.get('compost_source')}': on-farm material, no supply-chain "
                     "burden (cut-off); its N drives field N2O")


def _logistics_inputs(assessment, inputs, notes):
    lg = assessment.get("logistics") or {}
    foods = assessment.get("foods") or []
    harvest_t = sum((f.get("quantity_kg") or 0) for f in foods) / 1000.0

    mat = _norm(lg.get("packaging_material"))
    if mat and "none" not in mat and harvest_t > 0:
        kg_t = lg.get("packaging_kg_per_tonne")
        est = kg_t is None
        if est:
            kg_t = PACKAGING_DEFAULT_KG_PER_T
        ds = next((v for k, v in FARM_PACKAGING_MATCH.items() if k in mat),
                  "market for polypropylene, granulate | polypropylene, granulate | Cutoff, U")
        row = {"name": f"{lg.get('packaging_material')} packaging (harvest)", "match_as": ds,
               "amount": kg_t * harvest_t, "unit": "kg", "kind": "packaging"}
        if est:
            row["estimated"] = True
            row["estimate_meta"] = {"basis": "0.1 kg sack per 50 kg produce (2 kg/t)"}
        inputs.append(row)

    # Inbound transport of purchased material inputs (mass-based, kg -> t).
    mass_kinds = ("fertiliser", "pesticide", "seed", "compost")
    t_inputs = sum(i["amount"] for i in inputs
                   if i.get("kind") in mass_kinds and i.get("unit") == "kg") / 1000.0
    if t_inputs > 0:
        km = lg.get("input_transport_km")
        est = km is None
        if est:
            km = INPUT_TRANSPORT_DEFAULT_KM
        if km > 0:
            row = {"name": "transport of inputs to farm", "match_as": LORRY,
                   "amount": t_inputs * km, "unit": "tkm", "kind": "transport"}
            if est:
                row["estimated"] = True
                row["estimate_meta"] = {"basis": INPUT_TRANSPORT_SOURCE, "km": km}
            inputs.append(row)

    km_mkt = lg.get("distance_to_market_km")
    if km_mkt and km_mkt > 0 and harvest_t > 0:
        mode = _norm(lg.get("market_transport_mode"))
        if any(z in mode for z in ZERO_EMISSION_MODES):
            notes.append("harvest carried to market on foot / bicycle / animal: no transport emissions")
        else:
            ds = next((v for k, v in MARKET_TRANSPORT_MATCH.items() if k in mode), LORRY)
            inputs.append({"name": "transport of harvest to first point of sale", "match_as": ds,
                           "amount": harvest_t * km_mkt, "unit": "tkm", "kind": "transport"})
            notes.append("system boundary extended to the first point of sale (transport to market "
                         "declared)")


def extract_purchased_inputs(assessment: dict) -> tuple[list[dict], list[str]]:
    """Return (purchased_inputs, notes) for the supply-chain solver."""
    inputs, notes = [], []
    total_area = _total_area(assessment)

    _fertiliser_inputs(assessment, total_area, inputs, notes)
    _energy_inputs(assessment, inputs, notes)
    _irrigation_inputs(assessment, inputs, notes)

    # Activity defaults when fuel/electricity were not measured (region tables).
    try:
        from .activity_defaults import apply_activity_defaults
    except ImportError:
        from activity_defaults import apply_activity_defaults  # type: ignore
    inputs = apply_activity_defaults(assessment, inputs, notes)

    rows, pnotes = pz.applications(assessment, total_area)
    inputs += pz.purchased_inputs(rows)
    notes += pnotes

    _seed_inputs(assessment, inputs, notes)
    _compost_inputs(assessment, total_area, inputs, notes)
    _logistics_inputs(assessment, inputs, notes)

    if not inputs:
        notes.append("no purchased inputs extracted (no fertiliser/fuel/electricity data)")
    return inputs, notes


def total_production_kg(assessment: dict) -> float:
    return sum((f.get("quantity_kg") or 0) for f in assessment.get("foods") or [])


def report_only_metadata(assessment: dict) -> dict:
    """Wizard fields kept as metadata: echoed verbatim in the ISO report (goal & scope).
    They do not change the numbers."""
    mp = assessment.get("management_practices") or {}
    pm = mp.get("pest_management") or {}
    ee = assessment.get("equipment_energy") or {}
    pests = pm.get("pesticides") or pm.get("pesticides_used") or []
    return {
        "note": "Reported for context; these fields do not change the numbers.",
        "pest_management": {
            "management_approach": pm.get("management_approach"),
            "uses_ipm": pm.get("uses_ipm"),
            "pest_monitoring_frequency": pm.get("pest_monitoring_frequency"),
            "target_pests": sorted({t for p in pests if isinstance(p, dict)
                                    for t in (p.get("target_pests") or [])}),
        },
        "water_conservation_practices": (mp.get("water_management") or {}).get("water_conservation_practices"),
        "equipment_age_years": {e.get("equipment_type"): e.get("age")
                                for e in (ee.get("equipment") or []) if isinstance(e, dict)},
    }


if __name__ == "__main__":
    demo = {"foods": [{"name": "Maize", "category": "Cereals", "quantity_kg": 9500, "area_allocated": 5.0},
                      {"name": "Tomato", "category": "Vegetables", "quantity_kg": 31500, "area_allocated": 3.5}],
            "management_practices": {"fertilization": {"uses_fertilizers": True,
                "fertilizer_applications": [
                    {"fertilizer_type": "NPK", "npk_ratio": "15-15-15", "application_rate": 250, "applications_per_season": 1},
                    {"fertilizer_type": "Urea", "npk_ratio": "46-0-0", "application_rate": 100, "applications_per_season": 2}]}},
            "equipment_energy": {"fuel_consumption": [{"fuel_type": "Diesel", "monthly_consumption": 150}],
                                 "energy_sources": [{"energy_type": "Grid Electricity", "monthly_consumption": 85}]}}
    inp, notes = extract_purchased_inputs(demo)
    for i in inp:
        print(f"  {i['name']:<42} {i['amount']:>10.1f} {i['unit']}  ({i['kind']})")
    print("total production kg:", total_production_kg(demo), "| notes:", notes)
