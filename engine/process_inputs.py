#!/usr/bin/env python3
"""
process_inputs.py — auto-extract the purchased inputs (for the supply-chain solver) from a
submitted PROCESSING (facility) assessment, mirroring inputs.py on the farm side.

A processor has no field emissions; its footprint is purchased utilities and materials:
  Raw material: declared kg per tonne output, else the cited default conversion ratio for
                the product / facility type (engine/conversion_ratios.py) plus storage loss
  Electricity : facility monthly kWh x 12, else summed per-step kWh/tonne x output tonnes;
                renewable share = on-site PV, the rest by primary_energy_source (grid,
                diesel genset, hydro, wind, solar)
  Fuel/heat   : every fuel stream (several allowed) via engine/energy_carriers.py
  Water       : municipal -> tap water (kg); borehole / well / river / dam -> elementary
                withdrawal (applied by process_service); chemical / RO treatment -> treated
                water datasets
  Wastewater  : 80% of water throughput -> treatment dataset, or none (flagged) if untreated
  Packaging   : per product, weight/unit x (output kg / package size) -> kg of material
  Solid waste : kg/day x operational days, minus by-products used (cut-off), split into
                organic / inorganic fractions with method-specific treatment datasets
  Transport   : inbound raw-material tonnes x distance (declared, else from the local
                sourcing share) -> tonne.km (freight dataset by mode)

Every input carries a `match_as` representative-dataset hint (like pesticides on the farm
side), so free-text matching lands on a sensible ecoinvent process and the actual matched
name is recorded for transparency.
"""
from __future__ import annotations

try:
    from . import energy_carriers as ec
    from .conversion_ratios import default_raw_input
except ImportError:  # script use
    import energy_carriers as ec  # type: ignore
    from conversion_ratios import default_raw_input  # type: ignore

# Lower heating values (MJ per litre) for common facility fuels.
FUEL_MJ_PER_L = {"diesel": 38.7, "petrol": 34.2, "gasoline": 34.2, "kerosene": 37.0,
                 "lpg": 25.8, "biodiesel": 33.0}

# Packaging material -> representative ecoinvent dataset to match against.
PACKAGING_MATCH = {
    "PlasticBag": "market for polypropylene, granulate | polypropylene, granulate | Cutoff, U",
    "Polypropylene": "market for polypropylene, granulate | polypropylene, granulate | Cutoff, U",
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

# Already-refined / intermediate ingredients -> processed-product datasets. Checked BEFORE
# farm-gate crop hints so "wheat flour" / "palm oil" do not collapse to grain / fruit bunch
# and understate milling or refining. Longer / more specific keys are preferred.
REFINED_MATERIAL_HINTS = {
    "wheat flour": "wheat flour",
    "maize flour": "maize flour",
    "corn flour": "maize flour",
    "soy flour": "soybean flour",
    "flour": "wheat flour",
    "wheat starch": "wheat starch production",
    "maize starch": "maize starch production",
    "corn starch": "maize starch production",
    "potato starch": "potato starch production",
    "starch": "maize starch production",
    "palm oil": "palm oil",
    "soybean oil": "soybean oil",
    "soya oil": "soybean oil",
    "soy oil": "soybean oil",
    "rape oil": "rape oil",
    "rapeseed oil": "rape oil",
    "canola oil": "rape oil",
    "sunflower oil": "sunflower oil",
    "groundnut oil": "peanut oil, at oil mill",
    "peanut oil": "peanut oil, at oil mill",
    "arachis oil": "peanut oil, at oil mill",
    "peanut butter": "peanut butter or peanut paste, recipe, at plant",
    "groundnut paste": "peanut butter or peanut paste, recipe, at plant",
    "cottonseed oil": "cottonseed oil, crude, cottonseed oil mill operation",
    "cotton seed oil": "cottonseed oil, crude, cottonseed oil mill operation",
    "cotton lint": "fibre production, cotton, ginning | fibre, cotton",
    "cotton fibre": "fibre production, cotton, ginning | fibre, cotton",
    "vegetable oil": "rape oil",
    "cocoa butter": "cocoa butter",
    "chocolate": "dark chocolate production",
    "butter": "butter production, from cow milk",
    "cheese": "cheese production",
    "glucose": "glucose production",
    "sugar": "sugar production, from sugarcane",
    "molasses": "molasses",
    "soybean meal": "soybean meal",
    "soy meal": "soybean meal",
    "breadcrumbs": "breadcrumbs production",
    "margarine": "margarine production",
}

# Raw-material crop-keyword hints -> a farm-gate PRODUCTION dataset to match against. This
# steers free text like "Maize kernels" to "maize grain production" (the harvested crop),
# not "maize seed production" (seed for sowing) or a consumer-stage Ciqual product. Keyed by
# a WHOLE WORD (or phrase) of the declared material name, plural-insensitive; the longest
# key wins after refined hints. Targets name datasets that exist in the canonical store
# (ecoinvent 3.11 / Agribalyse 3.2); notes on coverage:
#   groundnut/peanut: no "groundnut" dataset; ecoinvent "peanut production" (RoW, IN, CN, AR)
#   eggplant/aubergine/brinjal/garden egg: "aubergine production, open field" (RoW, IN)
#   cucumber: only "cucumber production, in heated greenhouse" (GLO); flagged as a proxy
#     for open-field cucumber by the identity gate's reviewers, not by this table
#   chilli / hot pepper / bare "pepper" (West African usage): "chilli production" (RoW, IN)
#   bell / sweet pepper: "bell pepper production, open field" (RoW, IN)
#   FFB / fresh fruit bunches: "palm fruit bunch production" (RoW, ID, MY, CO)
#   honey: WFLDB "Honey, raw, small-scale production, unpackaged, at farm {CH}" (smallholder
#     West African beekeeping is small-scale) or the large-scale {US} dataset
#   millet: "millet production" (RoW, IN); sorghum: grain sorghum is only in Agribalyse
#     ("Sorghum grain ... at farm gate" FR/US); sweet sorghum is a different crop
#   sesame: "sesame seed production" (RoW, IN); seed cotton: "seed-cotton production,
#     conventional" (RoW, BD, IN); cottonseed is a ginning co-product
#   onion, sugarcane, orange, lemon, mandarin, grape, apple, pear: ecoinvent "<crop>
#     production" datasets; ZA has orange, mandarin, apple and pear
#   cassava, yam, plantain: no farm-gate dataset in the store (Agribalyse has FR consumer
#     products only); the hint is kept so the gate searches by crop identity and flags
#     the fallback when nothing passes.
RAW_MATERIAL_HINTS = {
    "maize": "maize grain production", "corn": "maize grain production",
    "wheat": "wheat grain production", "rice": "rice production", "paddy": "rice production",
    "soy": "soybean production", "soybean": "soybean production", "soya": "soybean production",
    "sorghum": "sorghum grain, at farm gate", "guinea corn": "sorghum grain, at farm gate",
    "millet": "millet production", "pearl millet": "millet production",
    "potato": "potato production", "cassava": "cassava production", "manioc": "cassava production",
    "yam": "yam production", "plantain": "banana production", "banana": "banana production",
    "cocoa": "cocoa bean production", "coffee": "coffee green bean production",
    "groundnut": "peanut production", "ground nut": "peanut production",
    "peanut": "peanut production",
    "palm": "palm fruit bunch production", "oil palm": "palm fruit bunch production",
    "ffb": "palm fruit bunch production", "fresh fruit bunch": "palm fruit bunch production",
    "palm fruit": "palm fruit bunch production",
    "sugarcane": "sugarcane production", "sugar cane": "sugarcane production",
    "sunflower": "sunflower production", "rape": "rape seed production", "canola": "rape seed production",
    "barley": "barley grain production", "oat": "oat grain production", "tomato": "tomato production",
    "cabbage": "white cabbage production", "onion": "onion production", "carrot": "carrot production",
    "fava": "fava bean production", "pea": "protein pea production", "bean": "fava bean production",
    "eggplant": "aubergine production, open field", "aubergine": "aubergine production, open field",
    "brinjal": "aubergine production, open field", "garden egg": "aubergine production, open field",
    "cucumber": "cucumber production",
    "chilli": "chilli production", "chili": "chilli production", "hot pepper": "chilli production",
    "pepper": "chilli production", "scotch bonnet": "chilli production",
    "bell pepper": "bell pepper production, open field",
    "sweet pepper": "bell pepper production, open field",
    "honey": "Honey, raw, small-scale production, unpackaged, at farm",
    "honeycomb": "Honey, raw, small-scale production, unpackaged, at farm",
    "sesame": "sesame seed production", "benniseed": "sesame seed production",
    "cotton": "seed-cotton production, conventional",
    "seed cotton": "seed-cotton production, conventional",
    "cottonseed": "cottonseed, from cotton ginning",
    "orange": "orange production, fresh grade", "citrus": "orange production, fresh grade",
    "lemon": "lemon production", "mandarin": "mandarin production",
    "tangerine": "mandarin production", "grapefruit": "grapefruit, at farm gate",
    "grape": "grape production", "apple": "apple production", "pear": "pear production",
    "pineapple": "pineapple production",
}


def _hint_key_re(key: str):
    import re
    words = re.findall(r"[a-z0-9]+", key.lower())
    return re.compile(r"(?<![a-z0-9])" + r"[\s\-_]+".join(map(re.escape, words))
                      + r"(?:s|es)?(?![a-z0-9])")


def _raw_material_match(name: str) -> tuple[str, bool]:
    """Return (match hint, is_refined). Refined intermediates win over farm-gate crop keywords.
    Keys match whole words (plural-insensitive), longest key first, so "Peanuts" is not
    "pea", "Grapes" is not "rape", and "Pineapple" is not "apple"."""
    low = (name or "").lower()
    raw_key, raw_span = None, None
    for key in sorted(RAW_MATERIAL_HINTS, key=len, reverse=True):
        m = _hint_key_re(key).search(low)
        if m:
            raw_key, raw_span = key, m.span()
            break
    for key in sorted(REFINED_MATERIAL_HINTS, key=len, reverse=True):
        m = _hint_key_re(key).search(low)
        # a refined word inside a longer crop phrase is the crop ("sugar" in "sugar cane")
        if m and not (raw_span and raw_span[0] <= m.start() and m.end() <= raw_span[1]
                      and (raw_span[1] - raw_span[0]) > (m.end() - m.start())):
            return REFINED_MATERIAL_HINTS[key], True
    if raw_key:
        return RAW_MATERIAL_HINTS[raw_key], False
    # No hint key: let the controlled-vocabulary classifier map local or trade names
    # ("garden egg", "arachide") onto a hint key. Only a confident label is used; anything
    # else falls through to the raw name, and the matcher's identity gate flags it.
    label = _classify_raw_material(name)
    if label and label.lower() != low:
        hint, refined = _raw_material_match(label)
        if hint != f"{label} production":      # the label hit a real hint key
            return hint, refined
    return f"{name} production", False


def _classify_raw_material(name: str) -> str | None:
    try:
        try:
            from .llm import classify
        except ImportError:
            from llm import classify  # type: ignore
        r = classify("raw_material", name or "")
    except Exception:
        return None
    if r and r.get("label") and not r.get("needs_confirmation"):
        return r["label"]
    return None


# Transport mode -> representative freight dataset (ref unit tonne.km).
TRANSPORT_MATCH = {
    "Truck": "transport, freight, lorry",
    "Rail": "transport, freight train",
    "Ship": "transport, freight, sea, container ship",
    "Mixed": "transport, freight, lorry",
}

# Default inbound distance when average_transport_distance is blank: a weighted mean of a
# local and a non-local leg, weighted by local_sourcing_percentage.
LOCAL_KM = 50.0
LOCAL_KM_SOURCE = "GMG screening assumption: local supply within the district, 50 km (the former model default)"
NONLOCAL_KM = 230.0
NONLOCAL_KM_SOURCE = ("EC (2018) PEFCR Guidance v6.3, s.7.14 default supplier-to-factory road "
                      "transport, 230 km by lorry")

# Discharged share of process water (rest is in product, evaporated or reused). Screening
# default retained from the previous engine version.
WASTEWATER_SHARE = 0.8
WASTEWATER_DATASET = "treatment of wastewater, average, wastewater treatment"

# On-site treatment of intake water -> treated-water dataset (it includes its own sourcing,
# so no separate withdrawal is added for that water).
WATER_TREATMENT_MATCH = {
    "ChemicalTreatment": "market for water, decarbonised",
    "ReverseOsmosis": "market for water, deionised",
    "Comprehensive": "market for water, deionised",
}

# Organic / inorganic split of solid waste per disposal method:
# method -> (organic-fraction dataset, inorganic-fraction dataset)
WASTE_SPLIT_MATCH = {
    "Landfill": ("treatment of municipal solid waste, sanitary landfill",
                 "treatment of inert waste, sanitary landfill"),
    "Incineration": ("treatment of biowaste, municipal incineration",
                     "treatment of municipal solid waste, municipal incineration"),
    "Composting": ("treatment of biowaste, industrial composting",
                   "treatment of inert waste, sanitary landfill"),
    "AnaerobicDigestion": ("treatment of biowaste by anaerobic digestion",
                           "treatment of inert waste, sanitary landfill"),
    # recyclables leave burden-free under cut-off (no treatment dataset)
    "Recycling": ("treatment of biowaste, industrial composting", None),
    "Mixed": ("treatment of municipal solid waste, sanitary landfill",
              "treatment of municipal solid waste, sanitary landfill"),
}

# Electricity supply (primary_energy_source) -> carrier in engine/energy_carriers.py.
ELECTRICITY_CARRIER = {
    "GridElectricity": "grid", "Mixed": "grid", "Biomass": "grid", "LPG": "grid",
    "NaturalGas": "grid", "SolarPower": "solar", "HydroElectricity": "hydro",
    "WindPower": "wind", "DieselGenerator": "genset",
}

# Water sources that are natural withdrawals (elementary flows) rather than a purchase.
_NATURAL_WATER = {"borehole": "Water, well, in ground", "well": "Water, well, in ground",
                  "groundwater": "Water, well, in ground", "river": "Water, river",
                  "stream": "Water, river", "dam": "Water, lake", "reservoir": "Water, lake",
                  "lake": "Water, lake"}


def _fuel_word(ft: str) -> tuple[str, float]:
    """Legacy helper (kept for importers): fuel word and litre LHV."""
    key = ec.carrier_of(ft) or "diesel"
    if key not in FUEL_MJ_PER_L:
        key = "diesel"
    return key, FUEL_MJ_PER_L[key]


def total_output_kg(request: dict) -> float:
    """Total processed output across all products, in kg (annual_production is in tonnes)."""
    return sum((p.get("annual_production") or 0) * 1000.0 for p in request.get("processed_products") or [])


def _water_m3(request: dict) -> float:
    ops = request.get("processing_operations") or {}
    wm = ops.get("water_management") or {}
    monthly_m3 = wm.get("monthly_water_consumption")
    if monthly_m3:
        return monthly_m3 * 12.0
    return sum(
        sum((s.get("water_usage") or 0.0) for s in (p.get("processing_steps") or []))
        * (p.get("annual_production") or 0.0)
        for p in request.get("processed_products") or []) / 1000.0  # litres -> m3


def _water_split(request: dict) -> tuple[float, list[tuple[str, float]], str | None]:
    """(m3 bought as tap / treated water, [(withdrawal flow name, m3)], treatment dataset)."""
    ops = request.get("processing_operations") or {}
    wm = ops.get("water_management") or {}
    m3 = _water_m3(request)
    if m3 <= 0:
        return 0.0, [], None
    treat_ds = WATER_TREATMENT_MATCH.get(wm.get("water_treatment") or "")
    if treat_ds:
        return m3, [], treat_ds
    sources = [s for s in (wm.get("water_source") or []) if "rain" not in str(s).lower()]
    if not sources:
        return m3, [], None          # unspecified source: assume a public supply
    share = m3 / len(sources)
    bought, withdrawn = 0.0, []
    for s in sources:
        low = str(s).lower()
        flow = next((v for k, v in _NATURAL_WATER.items() if k in low), None)
        if flow:
            withdrawn.append((flow, share))
        else:
            bought += share          # municipal / tanker / unknown supplier
    return bought, withdrawn, None


def processing_water_withdrawals(request: dict) -> list[tuple[str, float]]:
    """Elementary water withdrawals (flow name, m3) for self-supplied water (borehole, well,
    river, dam). Applied by engine/process_service.py after the solve."""
    return _water_split(request)[1]


def _raw_material_rows(request: dict, notes: list) -> dict:
    products = request.get("processed_products") or []
    ops = request.get("processing_operations") or {}
    fp = request.get("facility_profile") or {}
    rms = ops.get("raw_material_sourcing") or {}
    loss_pct = ((rms.get("storage_practices") or {}).get("storage_loss_percentage"))
    loss = min(max((loss_pct if loss_pct is not None else 5.0) / 100.0, 0.0), 0.5)
    rows: dict = {}
    for p in products:
        out_t = p.get("annual_production") or 0.0
        declared = [ri for ri in (p.get("raw_material_inputs") or [])
                    if (ri.get("material_name") or "").strip() and (ri.get("quantity_per_tonne_output") or 0) > 0]
        for ri in declared:
            name = ri["material_name"].strip()
            kg = ri["quantity_per_tonne_output"] * out_t  # (kg/tonne) x tonnes = kg
            r = rows.setdefault(name, {"kg": 0.0, "estimated": False})
            r["kg"] += kg
        if declared or out_t <= 0:
            continue
        d = default_raw_input(p, fp.get("facility_type"))
        if not d:
            notes.append(f"product '{p.get('name')}': no raw-material input and no default conversion "
                         "ratio for its type, so the cradle burden of its ingredients is not counted")
            continue
        # A default ratio is a lossless mass balance; storage loss raises the purchase.
        kg = d["kg_per_tonne"] / (1.0 - loss) * out_t
        r = rows.setdefault(d["material_name"], {"kg": 0.0, "estimated": True})
        r["kg"] += kg
        r["estimated"] = True
        r["meta"] = {"basis": f"default conversion ratio {d['extraction_rate']:g} "
                              f"({d['product_type_used']}) with {loss * 100:g}% storage loss",
                     "source": d["source"]}
        notes.append(f"product '{p.get('name')}': raw material defaulted to {d['kg_per_tonne']:.0f} kg "
                     f"'{d['material_name']}' per tonne (extraction {d['extraction_rate']:g}; "
                     f"{d['source']}) plus {loss * 100:g}% storage loss. Co-products: {d['coproducts']}")
    return rows


def extract_processing_inputs(request: dict) -> tuple[list[dict], list[str], float]:
    """Return (purchased_inputs, notes, total_output_kg) for the supply-chain solver."""
    inputs, notes = [], []
    products = request.get("processed_products") or []
    ops = request.get("processing_operations") or {}
    fp = request.get("facility_profile") or {}
    total_kg = total_output_kg(request)
    output_t = total_kg / 1000.0

    # --- Raw materials: the CRADLE part of cradle-to-gate, usually the dominant burden.
    #     Declared per-tonne inputs, else the cited default conversion ratio for the product.
    raw_rows = _raw_material_rows(request, notes)
    for name, r in raw_rows.items():
        hint, is_refined = _raw_material_match(name)
        row = {"name": name, "match_as": hint, "amount": r["kg"], "unit": "kg",
               "kind": "raw_material", "refined": is_refined}
        if r.get("estimated"):
            row["estimated"] = True
            row["estimate_meta"] = r.get("meta")
        inputs.append(row)
        if is_refined:
            notes.append(f"raw material '{name}' treated as an already-processed ingredient "
                         f"(matched toward '{hint}', not farm-gate crop)")
    if not raw_rows:
        notes.append("no raw-material inputs were declared, so the cradle burden of the ingredients is not counted")

    # --- Electricity: facility meter, else per-step intensity. The renewable share is on-site
    #     PV (ecoinvent PV dataset, capital goods included); the rest follows the declared
    #     primary supply (grid, genset, hydro, wind, solar).
    em = ops.get("energy_management") or {}
    renew = min(max((em.get("renewable_energy_percentage") or 0.0) / 100.0, 0.0), 1.0)
    monthly_kwh = em.get("monthly_electricity_consumption")
    if monthly_kwh:
        annual_kwh, elec_basis = monthly_kwh * 12.0, "facility meter"
    else:
        annual_kwh = sum(
            sum((s.get("energy_intensity") or 0.0) for s in (p.get("processing_steps") or []))
            * (p.get("annual_production") or 0.0) for p in products)
        elec_basis = "per-step energy intensity"
    if annual_kwh > 0:
        if renew > 0:
            inp, _ = ec.carrier_input("solar", annual_kwh * renew, "kWh", name="solar PV electricity (on-site)")
            inputs.append(inp)
            notes.append(f"electricity from {elec_basis}; {renew * 100:.0f}% on-site solar PV")
        rest = annual_kwh * (1.0 - renew)
        supply = ELECTRICITY_CARRIER.get(em.get("primary_energy_source") or "GridElectricity", "grid")
        if rest > 0:
            if supply == "genset":
                litres = rest * ec.GENSET_L_PER_KWH
                inp, _ = ec.carrier_input("diesel", litres, "L", context="genset",
                                          name="diesel generator electricity (on-site)",
                                          estimated=True, basis=ec.GENSET_L_PER_KWH_SOURCE)
                notes.append(f"{rest:.0f} kWh from an on-site diesel generator -> {litres:.0f} L diesel "
                             f"({ec.GENSET_L_PER_KWH} L/kWh)")
            else:
                inp, _ = ec.carrier_input(supply, rest, "kWh",
                                          name="electricity low voltage" if supply == "grid" else None)
            inputs.append(inp)
    else:
        notes.append("no electricity consumption found (neither a facility meter nor per-step intensity)")

    # --- Fuels: every declared stream (several allowed). The legacy single stream
    #     (monthly_fuel_consumption + fuel_type) is folded in as one more stream.
    streams = list(em.get("fuel_streams") or [])
    if em.get("monthly_fuel_consumption"):
        streams.append({"fuel_type": em.get("fuel_type") or "Diesel",
                        "monthly_consumption": em["monthly_fuel_consumption"], "unit": "L"})
    for st in streams:
        monthly = st.get("monthly_consumption") or 0
        if monthly <= 0:
            continue
        ftxt = f"{st.get('fuel_type') or ''} {st.get('use') or ''}".lower()
        carrier = ec.carrier_of(st.get("fuel_type"))
        if not carrier:
            notes.append(f"fuel '{st.get('fuel_type')}' not recognised; modelled as diesel")
            carrier = "diesel"
        context = "genset" if "generator" in ftxt else "facility"
        inp, note = ec.carrier_input(carrier, monthly * 12.0, st.get("unit"), context=context,
                                     name=f"{st.get('fuel_type') or carrier} (facility fuel)")
        if inp:
            inputs.append(inp)
        if note:
            notes.append(note)

    # --- Water: bought (tap / treated) vs self-supplied (elementary withdrawal, applied
    #     after the solve by process_service). Wastewater: discharged share, treated or not.
    wm = ops.get("water_management") or {}
    water_m3 = _water_m3(request)
    bought_m3, withdrawn, treat_ds = _water_split(request)
    if bought_m3 > 0:
        inputs.append({"name": "process water" if treat_ds else "tap water",
                       "match_as": treat_ds or "market for tap water",
                       "amount": bought_m3 * 1000.0, "unit": "kg", "kind": "water",
                       "water_source": wm.get("water_source") or []})
        if not (wm.get("water_source") or treat_ds):
            notes.append("water source not given; process water modelled as a public tap-water supply")
    if withdrawn:
        notes.append("self-supplied water modelled as elementary withdrawal: "
                     + ", ".join(f"{n} {m:.0f} m3" for n, m in withdrawn))
    if water_m3 > 0:
        ww_m3 = water_m3 * WASTEWATER_SHARE
        if (wm.get("wastewater_treatment") or "BasicSedimentation") == "None":
            notes.append(f"wastewater ({ww_m3:.0f} m3) discharged untreated: no treatment burden, and its "
                         "pollutant load (COD, N, P) is NOT quantified. Data gap: measure effluent "
                         "COD/BOD to model it")
        else:
            inputs.append({"name": "wastewater treatment", "match_as": WASTEWATER_DATASET,
                           "amount": ww_m3, "unit": "m3", "kind": "wastewater"})

    # --- Packaging: material per product, scaled by number of packages.
    for p in products:
        pk = p.get("packaging") or {}
        out_kg = (p.get("annual_production") or 0.0) * 1000.0
        pack_size = pk.get("package_size") or 0.0
        wt = pk.get("packaging_weight_per_unit") or 0.0
        if out_kg > 0 and pack_size > 0 and wt > 0:
            mat = pk.get("packaging_material") or "PlasticBag"
            inputs.append({"name": f"{mat} packaging",
                           "match_as": PACKAGING_MATCH.get(mat, PACKAGING_MATCH["PlasticBag"]),
                           "amount": out_kg / pack_size * wt, "unit": "kg", "kind": "packaging"})

    # --- Solid waste: by-product utilisation leaves burden-free (cut-off); the rest splits
    #     into organic and inorganic fractions with method-specific treatment datasets.
    wam = ops.get("waste_management") or {}
    kg_day = wam.get("solid_waste_generation")
    op_days = fp.get("operational_days_per_year") or 250
    if kg_day:
        total_waste = kg_day * op_days
        utilised = min(sum(max(b.get("percentage_utilized") or 0.0, 0.0)
                           for b in (wam.get("byproduct_utilization") or [])), 100.0) / 100.0
        if utilised > 0:
            notes.append(f"{utilised * 100:.0f}% of solid waste is used as by-products ("
                         + ", ".join(f"{b.get('byproduct_name')}: {b.get('utilization_method')}"
                                     for b in wam.get("byproduct_utilization") or [])
                         + "): leaves the system burden-free (cut-off)")
        to_treat = total_waste * (1.0 - utilised)
        org = min(max((wam.get("organic_waste_percentage") if wam.get("organic_waste_percentage")
                        is not None else 70.0) / 100.0, 0.0), 1.0)
        method = wam.get("waste_disposal_method") or "Landfill"
        org_ds, inorg_ds = WASTE_SPLIT_MATCH.get(method, WASTE_SPLIT_MATCH["Landfill"])
        for label, frac, ds in (("organic", org, org_ds), ("inorganic", 1.0 - org, inorg_ds)):
            if ds is None:
                if to_treat * frac > 0:
                    notes.append(f"{label} solid waste sent to recycling: burden-free (cut-off)")
                continue
            if to_treat * frac > 0:
                inputs.append({"name": f"solid waste ({label}), {method.lower()}", "match_as": ds,
                               "amount": to_treat * frac, "unit": "kg", "kind": "waste"})

    # --- Inbound transport of raw materials (tonne.km), declared or default materials.
    rms = ops.get("raw_material_sourcing") or {}
    raw_tonnes = sum(r["kg"] for r in raw_rows.values()) / 1000.0
    distance = rms.get("average_transport_distance")
    estimated_km = distance is None
    if estimated_km:
        local = min(max((rms.get("local_sourcing_percentage") if rms.get("local_sourcing_percentage")
                         is not None else 80.0) / 100.0, 0.0), 1.0)
        distance = local * LOCAL_KM + (1.0 - local) * NONLOCAL_KM
    if distance > 0 and raw_tonnes > 0:
        mode = rms.get("transport_mode") or "Truck"
        row = {"name": f"inbound transport ({mode.lower()})",
               "match_as": TRANSPORT_MATCH.get(mode, TRANSPORT_MATCH["Truck"]),
               "amount": raw_tonnes * distance, "unit": "tkm", "kind": "transport"}
        if estimated_km:
            row["estimated"] = True
            row["estimate_meta"] = {"basis": f"{distance:.0f} km = local share x {LOCAL_KM:g} km "
                                             f"({LOCAL_KM_SOURCE}) + rest x {NONLOCAL_KM:g} km "
                                             f"({NONLOCAL_KM_SOURCE})"}
        inputs.append(row)

    if not inputs:
        notes.append("no purchased inputs extracted from the facility data")
    if output_t <= 0:
        notes.append("total processed output is zero; results cannot be expressed per kg")
    return inputs, notes, total_kg


def report_only_metadata(request: dict) -> dict:
    """Processing fields kept as metadata (ISO report goal & scope); they do not change the
    numbers. Includes a capacity-utilisation check for the data-quality section."""
    fp = request.get("facility_profile") or {}
    products = request.get("processed_products") or []
    cap = fp.get("processing_capacity") or 0.0
    days = fp.get("operational_days_per_year") or 0
    out_t = total_output_kg(request) / 1000.0
    util = (out_t / (cap * days)) if cap and days else None
    return {
        "note": "Reported for context; these fields do not change the numbers.",
        "facility": {k: fp.get(k) for k in ("facility_type", "processing_capacity",
                                             "operational_hours_per_day", "operational_days_per_year",
                                             "location_type")},
        "capacity_utilisation": round(util, 3) if util is not None else None,
        "capacity_check": (None if util is None else
                           "annual output exceeds stated capacity x operating days; check inputs"
                           if util > 1.0 else "consistent"),
        "products": [{"name": p.get("name"), "quality_grade": p.get("quality_grade"),
                      "market_destination": p.get("market_destination"),
                      "packaging_recyclable": (p.get("packaging") or {}).get("recyclable"),
                      "raw_material_source_locations": [ri.get("source_location")
                                                        for ri in (p.get("raw_material_inputs") or [])
                                                        if ri.get("source_location")]}
                     for p in products],
    }


if __name__ == "__main__":
    import json, sys
    req = json.load(open(sys.argv[1])) if len(sys.argv) > 1 else {}
    inp, notes, tkg = extract_processing_inputs(req)
    for i in inp:
        print(f"  {i['name']:<28} {i['amount']:>12.1f} {i['unit']:<4} ({i['kind']})  -> {i.get('match_as', i['name'])}")
    print("total output kg:", tkg, "| notes:", notes)
