#!/usr/bin/env python3
"""
process_inputs.py — auto-extract the purchased inputs (for the supply-chain solver) from a
submitted PROCESSING (facility) assessment, mirroring inputs.py on the farm side.

A processor has no field emissions; its footprint is purchased utilities and materials:
  Electricity : facility monthly kWh x 12, else summed per-step kWh/tonne x output tonnes
  Fuel/heat   : facility monthly litres x 12 -> MJ (process ref unit is MJ)
  Water       : facility monthly m3 x 12 -> kg (market for tap water is per kg)
  Wastewater  : a fraction of water throughput -> m3 (treatment dataset)
  Packaging   : per product, weight/unit x (output kg / package size) -> kg of material
  Solid waste : kg/day x operational days -> kg (treatment dataset by disposal method)
  Transport   : inbound raw-material tonnes x distance -> tonne.km (freight dataset by mode)

Every input carries a `match_as` representative-dataset hint (like pesticides on the farm
side), so free-text matching lands on a sensible ecoinvent process and the actual matched
name is recorded for transparency.
"""
from __future__ import annotations

# Lower heating values (MJ per litre) for common facility fuels.
FUEL_MJ_PER_L = {"diesel": 38.7, "petrol": 34.2, "gasoline": 34.2, "kerosene": 37.0,
                 "lpg": 25.8, "biodiesel": 33.0}

# Packaging material -> representative ecoinvent dataset to match against.
PACKAGING_MATCH = {
    "PlasticBag": "market for polypropylene, granulate",
    "Polypropylene": "market for polypropylene, granulate",
    "PaperBag": "market for kraft paper",
    "Jute": "market for kraft paper",  # ecoinvent lacks jute; kraft paper is the closest fibre proxy
    "Cardboard": "market for corrugated board box",
    "Metal": "market for steel, low-alloyed",
    "Glass": "market for packaging glass, white",
    "Composite": "market for packaging film, low density polyethylene",
}

# Solid-waste disposal method -> representative treatment dataset.
WASTE_MATCH = {
    "Landfill": "treatment of municipal solid waste, sanitary landfill",
    "Incineration": "treatment of municipal solid waste, incineration",
    "Composting": "treatment of biowaste, industrial composting",
    "AnaerobicDigestion": "treatment of biowaste, anaerobic digestion",
    "Recycling": "treatment of waste paper, sorting",
    "Mixed": "treatment of municipal solid waste, sanitary landfill",
}

# Raw-material crop-keyword hints -> a farm-gate PRODUCTION dataset to match against. This
# steers free text like "Maize kernels" to "maize grain production" (the harvested crop),
# not "maize seed production" (seed for sowing) or a consumer-stage Ciqual product. Keyed by
# a substring found in the declared material name; first match wins.
RAW_MATERIAL_HINTS = {
    "maize": "maize grain production", "corn": "maize grain production",
    "wheat": "wheat grain production", "rice": "rice production", "paddy": "rice production",
    "soy": "soybean production", "sorghum": "sorghum grain production", "millet": "millet production",
    "potato": "potato production", "cassava": "cassava production", "manioc": "cassava production",
    "yam": "yam production", "plantain": "banana production", "banana": "banana production",
    "cocoa": "cocoa bean production", "coffee": "coffee green bean production",
    "groundnut": "groundnut production", "peanut": "groundnut production",
    "palm": "palm fruit bunch production", "sugarcane": "sugarcane production",
    "sunflower": "sunflower production", "rape": "rape seed production", "canola": "rape seed production",
    "barley": "barley grain production", "oat": "oat grain production", "tomato": "tomato production",
    "cabbage": "white cabbage production", "onion": "onion production", "carrot": "carrot production",
    "fava": "fava bean production", "pea": "protein pea production", "bean": "fava bean production",
}


def _raw_material_match(name: str) -> str:
    """Best farm-gate production dataset hint for a declared raw material name."""
    low = (name or "").lower()
    for key, target in RAW_MATERIAL_HINTS.items():
        if key in low:
            return target
    return f"{name} production"


# Transport mode -> representative freight dataset (ref unit tonne.km).
TRANSPORT_MATCH = {
    "Truck": "transport, freight, lorry",
    "Rail": "transport, freight train",
    "Ship": "transport, freight, sea, container ship",
    "Mixed": "transport, freight, lorry",
}


def _fuel_word(ft: str) -> tuple[str, float]:
    f = (ft or "").lower()
    for k, mj in FUEL_MJ_PER_L.items():
        if k in f:
            word = "diesel" if k == "diesel" else ("petrol" if k in ("petrol", "gasoline") else k)
            return word, mj
    return "diesel", FUEL_MJ_PER_L["diesel"]


def total_output_kg(request: dict) -> float:
    """Total processed output across all products, in kg (annual_production is in tonnes)."""
    return sum((p.get("annual_production") or 0) * 1000.0 for p in request.get("processed_products") or [])


def extract_processing_inputs(request: dict) -> tuple[list[dict], list[str], float]:
    """Return (purchased_inputs, notes, total_output_kg) for the supply-chain solver."""
    inputs, notes = [], []
    products = request.get("processed_products") or []
    ops = request.get("processing_operations") or {}
    total_kg = total_output_kg(request)
    output_t = total_kg / 1000.0

    # --- Raw materials: the crops/ingredients the facility buys and processes. This is the
    #     CRADLE part of cradle-to-gate and is usually the dominant burden, so it must be
    #     included (otherwise the result is only the processing delta). Amount = per-tonne
    #     input x product tonnes; the free-text name is matched to a background crop dataset. ---
    raw_totals: dict = {}
    for p in products:
        out_t = p.get("annual_production") or 0.0
        for ri in p.get("raw_material_inputs") or []:
            name = (ri.get("material_name") or "").strip()
            kg = (ri.get("quantity_per_tonne_output") or 0.0) * out_t  # (kg/tonne) x tonnes = kg
            if name and kg > 0:
                raw_totals[name] = raw_totals.get(name, 0.0) + kg
    for name, kg in raw_totals.items():
        # Steer the match to a farm-gate PRODUCTION dataset (grain, not seed or a
        # consumer-stage product) via a crop-keyword hint. Keep the declared name as the
        # display label so the report stays transparent.
        inputs.append({"name": name, "match_as": _raw_material_match(name),
                       "fallback": name, "amount": kg, "unit": "kg", "kind": "raw_material"})
    if not raw_totals:
        notes.append("no raw-material inputs were declared, so the cradle burden of the ingredients is not counted")

    # --- Electricity: prefer the facility's measured meter reading; else bottom-up from
    #     each product's per-step energy intensity. renewable_energy_percentage is treated
    #     as (near) burden-free at screening level and removed from the grid draw. ---
    em = ops.get("energy_management") or {}
    renew = min(max((em.get("renewable_energy_percentage") or 0.0) / 100.0, 0.0), 1.0)
    monthly_kwh = em.get("monthly_electricity_consumption")
    if monthly_kwh:
        annual_kwh = monthly_kwh * 12.0
        elec_basis = "facility meter"
    else:
        annual_kwh = sum(
            sum((s.get("energy_intensity") or 0.0) for s in (p.get("processing_steps") or []))
            * (p.get("annual_production") or 0.0)
            for p in products)
        elec_basis = "per-step energy intensity"
    grid_kwh = annual_kwh * (1.0 - renew)
    if grid_kwh > 0:
        inputs.append({"name": "electricity low voltage", "amount": grid_kwh, "unit": "kWh",
                       "kind": "electricity"})
        if renew > 0:
            notes.append(f"electricity from {elec_basis}; {renew*100:.0f}% renewable treated as "
                         "near-zero burden and excluded from the grid draw")
    else:
        notes.append("no electricity consumption found (neither a facility meter nor per-step intensity)")

    # --- Fuel / process heat ---
    monthly_fuel = em.get("monthly_fuel_consumption")
    if monthly_fuel:
        litres = monthly_fuel * 12.0
        word, mj_per_l = _fuel_word(em.get("fuel_type"))
        inputs.append({"name": f"{word} (facility fuel)",
                       "match_as": f"{word}, burned in building machine",
                       "fallback": f"{word}, burned in agricultural machinery",
                       "amount": litres * mj_per_l, "unit": "MJ", "kind": "fuel"})

    # --- Water: facility meter, else summed per-step usage (L/tonne). ---
    wm = ops.get("water_management") or {}
    monthly_m3 = wm.get("monthly_water_consumption")
    if monthly_m3:
        water_m3 = monthly_m3 * 12.0
    else:
        water_m3 = sum(
            sum((s.get("water_usage") or 0.0) for s in (p.get("processing_steps") or []))
            * (p.get("annual_production") or 0.0)
            for p in products) / 1000.0  # litres -> m3
    if water_m3 > 0:
        inputs.append({"name": "tap water", "match_as": "market for tap water",
                       "amount": water_m3 * 1000.0, "unit": "kg", "kind": "water"})
        # Wastewater: most process water leaves as effluent; treat ~80% (screening default).
        inputs.append({"name": "wastewater treatment",
                       "match_as": "treatment of wastewater, average",
                       "amount": water_m3 * 0.8, "unit": "m3", "kind": "wastewater"})

    # --- Packaging: material per product, scaled by number of packages. ---
    for p in products:
        pk = p.get("packaging") or {}
        out_kg = (p.get("annual_production") or 0.0) * 1000.0
        pack_size = pk.get("package_size") or 0.0
        wt = pk.get("packaging_weight_per_unit") or 0.0
        if out_kg > 0 and pack_size > 0 and wt > 0:
            units = out_kg / pack_size
            mat = pk.get("packaging_material") or "PlasticBag"
            inputs.append({"name": f"{mat} packaging", "match_as": PACKAGING_MATCH.get(mat, PACKAGING_MATCH["PlasticBag"]),
                           "amount": units * wt, "unit": "kg", "kind": "packaging"})

    # --- Solid-waste treatment ---
    wam = ops.get("waste_management") or {}
    kg_day = wam.get("solid_waste_generation")
    op_days = (request.get("facility_profile") or {}).get("operational_days_per_year") or 250
    if kg_day:
        method = wam.get("waste_disposal_method") or "Landfill"
        inputs.append({"name": f"solid waste, {method.lower()}",
                       "match_as": WASTE_MATCH.get(method, WASTE_MATCH["Landfill"]),
                       "amount": kg_day * op_days, "unit": "kg", "kind": "waste"})

    # --- Inbound transport of raw materials (tonne.km) ---
    rms = ops.get("raw_material_sourcing") or {}
    distance = rms.get("average_transport_distance") or 0.0
    raw_tonnes = sum(
        sum((ri.get("quantity_per_tonne_output") or 0.0) for ri in (p.get("raw_material_inputs") or []))
        * (p.get("annual_production") or 0.0) / 1000.0  # (kg/tonne x tonnes) -> kg; /1000 -> tonnes
        for p in products)
    if distance > 0 and raw_tonnes > 0:
        mode = rms.get("transport_mode") or "Truck"
        inputs.append({"name": f"inbound transport ({mode.lower()})",
                       "match_as": TRANSPORT_MATCH.get(mode, TRANSPORT_MATCH["Truck"]),
                       "amount": raw_tonnes * distance, "unit": "tkm", "kind": "transport"})

    if not inputs:
        notes.append("no purchased inputs extracted from the facility data")
    if output_t <= 0:
        notes.append("total processed output is zero; results cannot be expressed per kg")
    return inputs, notes, total_kg


if __name__ == "__main__":
    import json, sys
    req = json.load(open(sys.argv[1])) if len(sys.argv) > 1 else {}
    inp, notes, tkg = extract_processing_inputs(req)
    for i in inp:
        print(f"  {i['name']:<28} {i['amount']:>12.1f} {i['unit']:<4} ({i['kind']})  -> {i.get('match_as', i['name'])}")
    print("total output kg:", tkg, "| notes:", notes)
