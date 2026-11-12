#!/usr/bin/env python3
"""
regenerate_inventory_mapping.py: rebuild the executed-matcher parts of the PM's inventory
mapping (docs/inventory_mapping/GMG_inventory_database_mapping.json and
GMG_inventory_mapping_summary.json) from the CURRENT engine code.

Nothing here is typed in by hand: every input row is produced by executing the engine's own
extraction code on a small synthetic request that exercises one branch (engine/inputs.py
extract_purchased_inputs and engine/process_inputs.py extract_processing_inputs, followed by
engine/fuels.py expand_fuel_inputs exactly as engine/service.py and engine/process_service.py
do), and every match is FarmLCA.resolve_input on that input dict, run for every region in
REGIONS_RUN. Reproducibility:

  * GMG_LLM_ADJUDICATE=0 (no LLM adjudication; set before the engine is imported);
  * query embeddings come from the pinned cache engine/golden/matcher_query_embeddings.npz
    (as in engine/test_matcher_regression.py); queries that are not pinned (new region
    names, new inputs) are embedded live with OPENAI_API_KEY (loaded by ingestion/matching.py
    from app/.env). Pass --query-cache PATH to also read/write those extra vectors so later
    runs are fully offline and bit-identical;
  * candidate ranking is deterministic (region fit, score, uid; engine/orchestrator.py).

The previous match is taken from the mapping as committed in BASELINE_FILE_REV (which describes
engine commit BASELINE_COMMIT), read with git show and parsed by
engine/test_matcher_regression.collect_rows(), so re-running this script never loses the
"matched_process_at_<commit>" column.

Usage (repo root):
    .venv/Scripts/python.exe scripts/regenerate_inventory_mapping.py
    .venv/Scripts/python.exe scripts/regenerate_inventory_mapping.py --dry-run --dump runA.json

Only the executed parts are rewritten (matcher rows, quick tables, on-farm flow mapping,
region registry values). Prose sections of the two files are edited by hand and kept.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ["GMG_LLM_ADJUDICATE"] = "0"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DOC_DIR = ROOT / "docs" / "inventory_mapping"
DETAIL = DOC_DIR / "GMG_inventory_database_mapping.json"
SUMMARY = DOC_DIR / "GMG_inventory_mapping_summary.json"
BASELINE_COMMIT = "45ad6b6"         # engine commit the previous mapping describes
BASELINE_FILE_REV = "3cc32e5"       # commit that added that mapping (its repository_commit is 45ad6b6)
BASE_KEY = f"matched_process_at_{BASELINE_COMMIT}"
REGIONS_RUN = ["GH", "NG", "SN", "BF", "ZA", "CA"]


# ---------------------------------------------------------------------------------------
# citations resolved against the current source (file:line found by pattern, not typed)
# ---------------------------------------------------------------------------------------
_SRC_CACHE: dict[str, list[str]] = {}


def _lines(rel: str) -> list[str]:
    if rel not in _SRC_CACHE:
        _SRC_CACHE[rel] = (ROOT / rel).read_text(encoding="utf-8").splitlines()
    return _SRC_CACHE[rel]


def line_of(rel: str, pattern: str, start: int = 1) -> int:
    rx = re.compile(pattern)
    for i, ln in enumerate(_lines(rel)[start - 1:], start):
        if rx.search(ln):
            return i
    raise LookupError(f"citation anchor not found: {rel}: /{pattern}/")


def cite(rel: str, pattern: str, end_pattern: str | None = None) -> str:
    a = line_of(rel, pattern)
    if end_pattern is None:
        return f"{rel}:{a}"
    b = line_of(rel, end_pattern, a + 1)
    return f"{rel}:{a}-{b}"


def cite_def(rel: str, name: str) -> str:
    """file:first-last line of a Python `def name` or Rust `fn name` (to the end of its body)."""
    lines = _lines(rel)
    a = line_of(rel, rf"^\s*(?:pub(?:\([a-z]+\))? )?(?:def|fn) {re.escape(name)}\b")
    indent = len(lines[a - 1]) - len(lines[a - 1].lstrip())
    b = a
    for i in range(a, len(lines)):
        ln = lines[i]
        if ln.strip() and (len(ln) - len(ln.lstrip())) <= indent and not ln.lstrip().startswith((")", "#", "}")):
            break
        if ln.strip() and not ln.lstrip().startswith("#"):
            b = i + 1
    return f"{rel}:{a}-{b}"


def C_MATCH() -> str:
    return "; ".join([cite_def("engine/orchestrator.py", "resolve_input"),
                      cite_def("engine/orchestrator.py", "_match_input"),
                      cite_def("engine/orchestrator.py", "_rank"),
                      cite_def("engine/regions.py", "location_rank")])


# ---------------------------------------------------------------------------------------
# input catalogues built by executing the engine's extraction code
# ---------------------------------------------------------------------------------------
_FOOD = {"id": "f1", "name": "Maize", "category": "Cereals", "quantity_kg": 5000.0,
         "area_allocated": 2.0}


def _farm(**patch) -> dict:
    a = {"country": "Ghana", "foods": [dict(_FOOD)], "management_practices": {},
         "equipment_energy": {}, "logistics": {}}
    for k, v in patch.items():
        a[k] = v
    return a


def _strip(inp: dict) -> dict:
    """The input dict as the matcher sees it (amounts are irrelevant to matching)."""
    return {k: v for k, v in inp.items()
            if k not in ("amount", "native_amount", "declared_amount", "estimate_meta",
                         "irrigation_m3", "ai_content", "ai_content_source", "lhv_mj_per_unit")}


def farm_catalogue() -> list[dict]:
    from engine.inputs import extract_purchased_inputs
    from engine import fuels
    I = "engine/inputs.py"
    EC = "engine/energy_carriers.py"
    c_ext = cite_def(I, "extract_purchased_inputs")
    c_fert = cite_def(I, "_fertiliser_inputs")
    c_fmatch = cite(I, r"^FERTILISER_MATCH = \{", r"^\}")
    c_energy = cite_def(I, "_energy_inputs")
    c_ds = cite(EC, r"^DATASETS = \{", r"^\}")
    c_carrier = cite_def(EC, "carrier_input")
    c_comb = cite("engine/fuels.py", r"^COMBUSTION: dict", r"^\}") + "; " + cite_def("engine/fuels.py", "expand_fuel_inputs")
    c_irr = cite_def(I, "_irrigation_inputs") + "; " + cite(I, r"^PUMP_MJ_PER_M3 = \{", r"^PUMP_DATASET")
    c_pest = cite("engine/pesticides.py", r"^PESTICIDE_FLOWS = \{", r"^\}") + "; " + cite_def("engine/pesticides.py", "purchased_inputs")
    c_seed = cite_def(I, "_seed_inputs") + "; " + cite("engine/crop_defaults.py", r"^SEED_RATES = \{", r"^\}")
    c_comp = cite_def(I, "_compost_inputs")
    c_log = cite_def(I, "_logistics_inputs") + "; " + cite(I, r"^FARM_PACKAGING_MATCH = \{", r"^\}")

    cases = []

    def add(case, assessment, kinds, how, cloc):
        cases.append((case, assessment, kinds, how, cloc))

    ferts = [("NPK Compound", "15-15-15"), ("NPK Compound", ""), ("Urea", "46-0-0"), ("Urea", ""),
             ("Diammonium Phosphate (DAP)", "18-46-0"), ("Diammonium Phosphate (DAP)", ""),
             ("Single Super Phosphate", ""), ("Muriate of Potash", ""),
             ("Ammonium Sulfate", "21-0-0"), ("Calcium Ammonium Nitrate (CAN)", ""),
             ("Organic Fertilizer", ""), ("Bio-fertilizer", ""), ("Foliar Fertilizer", ""),
             ("None", "")]
    for ft, npk in ferts:
        app = {"fertilizer_type": ft, "application_rate": 100, "applications_per_season": 1}
        if npk:
            app["npk_ratio"] = npk
        how = (f"wizard fertilizer_type='{ft}'" + (f", npk_ratio='{npk}'" if npk else ", npk_ratio blank")
               + "; name = f\"{fertilizer_type} {npk_ratio}\".strip() + \" fertiliser\""
               + ("; FERTILISER_MATCH steers it (match_as)" if ft in ("Ammonium Sulfate", "Calcium Ammonium Nitrate (CAN)") else "")
               + ("; the builder does not filter the wizard value 'None' when a rate is entered" if ft == "None" else ""))
        add(f"fertiliser:{ft}:{npk}",
            _farm(management_practices={"fertilization": {"uses_fertilizers": True, "fertilizer_applications": [app]}}),
            ("fertiliser",), how, f"{c_fert}; {c_fmatch}")
    for ft, unit in [("Diesel", None), ("Petrol/Gasoline", None), ("Kerosene", None),
                     ("Liquefied Petroleum Gas (LPG)", "kg"), ("Biodiesel", None)]:
        row = {"fuel_type": ft, "monthly_consumption": 10.0, "primary_use": "Land preparation"}
        if unit:
            row["unit"] = unit
        add(f"fuel:{ft}", _farm(equipment_energy={"fuel_consumption": [row]}), ("fuel",),
            f"equipment_energy.fuel_consumption[].fuel_type='{ft}'" + (f" (unit {unit})" if unit else " (litres)")
            + "; carrier from energy_carriers.carrier_of (classifier only for unrecognised text); "
              "carrier_input(context='farm'); LPG/kerosene then split by fuels.expand_fuel_inputs into the "
              "production dataset (kg) plus direct combustion CO2/CH4/N2O",
            f"{c_energy}; {c_carrier}; {c_ds}; {c_comb}")
    for et in ["Grid Electricity", "Diesel Generator", "Solar Panels", "Biogas", "Firewood", "Charcoal"]:
        add(f"energy:{et}",
            _farm(equipment_energy={"energy_sources": [{"energy_type": et, "monthly_consumption": 10.0,
                                                        "primary_use": "Storage"}]}),
            ("fuel", "electricity", "electricity_onsite", "heat_fuel"),
            f"equipment_energy.energy_sources[].energy_type='{et}' (natural unit when unit is blank); "
            "carrier_input; firewood/charcoal then split by fuels.expand_fuel_inputs",
            f"{c_energy}; {c_carrier}; {c_ds}; {c_comb}")
    add("irrigation:pumping",
        _farm(management_practices={"water_management": {"irrigation_system": "Drip irrigation",
                                                         "water_source": ["Borehole"],
                                                         "irrigation_water_m3": 1000.0}}),
        ("irrigation_energy", "water"),
        "management_practices.water_management: irrigated and no pump / irrigation fuel declared -> "
        "pumping energy per m3 from the ecoinvent irrigation dataset coefficients, both a diesel and an "
        "electric pump row; the water itself is an elementary withdrawal (engine/farm_flows.py)",
        c_irr)
    add("irrigation:municipal",
        _farm(management_practices={"water_management": {"irrigation_system": "Drip irrigation",
                                                         "water_source": ["Municipal supply"],
                                                         "irrigation_water_m3": 1000.0}}),
        ("water",),
        "irrigation water from a municipal / tap / piped source is a purchased product (tap water)",
        c_irr)
    for ai in ["glyphosate", "Lambda-cyhalothrin", "Mancozeb", "Chlorpyrifos", "Copper hydroxide",
               "Imidacloprid", "Neem extract"]:
        add(f"pesticide:{ai}",
            _farm(management_practices={"pest_management": {"pesticides": [
                {"pesticide_type": "Insecticide", "active_ingredient": ai, "application_rate": 1.0,
                 "applications_per_season": 1}]}}),
            ("pesticide",),
            f"pest_management.pesticides[].active_ingredient='{ai}' is the display name; match_as is the "
            "AI's chemical-class production dataset from PESTICIDE_FLOWS, else 'market for pesticide, "
            "unspecified'; amount = kg active ingredient",
            c_pest)
    for crop, cat in [("Maize", "Cereals"), ("Groundnuts", "Legumes"), ("Tomato", "Vegetables"),
                      ("Eggplant", "Vegetables"), ("Cucumber", "Vegetables"),
                      ("Chilli pepper", "Vegetables"), ("Bell pepper", "Vegetables"),
                      ("Cocoa", "Other"), ("Oil palm", "Oils")]:
        food = {**_FOOD, "name": crop, "category": cat}
        add(f"seed:{crop}", _farm(foods=[food]), ("seed",),
            f"foods[].name='{crop}': seed rate (user value or FAO default) x area; match_as is the "
            "crop's seed dataset (crop_defaults.SEED_RATES); vegetatively propagated / perennial crops "
            "(cocoa, oil palm, cassava, ...) get no seed row",
            c_seed)
    add("compost:purchased",
        _farm(management_practices={"soil_management": {"uses_compost": True,
                                                        "compost_source": "Purchased compost",
                                                        "compost_application_rate": 2.0}}),
        ("compost",), "soil_management.uses_compost and compost_source contains 'purchas' -> market for compost",
        c_comp)
    for mat in ["Jute bags", "Polypropylene sacks", "Plastic crates"]:
        add(f"packaging:{mat}", _farm(logistics={"packaging_material": mat}), ("packaging",),
            f"logistics.packaging_material='{mat}' (keyword table FARM_PACKAGING_MATCH; blank kg/t -> "
            "2 kg per tonne of harvest)", c_log)
    add("transport:inputs",
        _farm(management_practices={"fertilization": {"uses_fertilizers": True, "fertilizer_applications": [
            {"fertilizer_type": "Urea", "application_rate": 100, "applications_per_season": 1}]}}),
        ("transport",), "transport of purchased fertiliser / pesticide / seed / compost mass to the farm; "
                        "blank input_transport_km -> 230 km lorry default (PEFCR v6.3)", c_log)
    for mode in ["Truck", "Motorcycle"]:
        add(f"transport:market:{mode}",
            _farm(logistics={"distance_to_market_km": 20.0, "market_transport_mode": mode}),
            ("transport",), f"logistics.distance_to_market_km with market_transport_mode='{mode}' "
                            "(MARKET_TRANSPORT_MATCH)", c_log)

    out, seen = [], set()
    for case, assessment, kinds, how, cloc in cases:
        inputs, _notes = extract_purchased_inputs(copy.deepcopy(assessment))
        inputs, _flows, _fn = fuels.expand_fuel_inputs(inputs)
        for inp in inputs:
            if inp.get("kind") not in kinds:
                continue
            if case.startswith("transport:market") and "harvest" not in inp["name"]:
                continue
            if case == "transport:inputs" and "inputs to farm" not in inp["name"]:
                continue
            if inp["name"] in seen:
                continue
            seen.add(inp["name"])
            out.append({"input_name": inp["name"], "inp": _strip(inp), "case": case,
                        "how_name_is_built": how, "code_location": f"{c_ext}; {cloc}; {C_MATCH()}",
                        "produced_by": "engine.inputs.extract_purchased_inputs + engine.fuels.expand_fuel_inputs"})
    # free text accepted by POST /farm/assess purchased_inputs[] (app/farm/routes.py)
    c_api = cite("app/farm/routes.py", r"purchased_inputs: list\[PurchasedInput\]")
    for name in ["NPK fertiliser", "urea fertiliser"]:
        out.append({"input_name": name, "inp": {"name": name, "kind": "fertiliser", "unit": "kg"},
                    "case": "free-text", "how_name_is_built": "free text sent directly in POST /farm/assess "
                    "purchased_inputs[].name (no wizard builder)", "code_location": f"{c_api}; {C_MATCH()}",
                    "produced_by": "API free text"})
    return out


_PROD = {"name": "Product", "product_type": "Other", "annual_production": 100.0,
         "raw_material_inputs": [{"material_name": "Maize kernels", "quantity_per_tonne_output": 1000.0}],
         "packaging": {"packaging_material": "PlasticBag", "package_size": 0.0,
                       "packaging_weight_per_unit": 0.0}}


def _proc(ops: dict | None = None, products: list | None = None, facility_type: str = "General") -> dict:
    return {"facility_profile": {"facility_type": facility_type, "operational_days_per_year": 250},
            "processed_products": products or [copy.deepcopy(_PROD)],
            "processing_operations": ops or {}}


def processing_catalogue() -> list[dict]:
    from engine.process_inputs import extract_processing_inputs
    from engine.commodities import flag_processing_raw_materials
    from engine import fuels
    P = "engine/process_inputs.py"
    c_ext = cite_def(P, "extract_processing_inputs")
    c_ds = cite("engine/energy_carriers.py", r"^DATASETS = \{", r"^\}")
    c_comb = cite("engine/fuels.py", r"^COMBUSTION: dict", r"^\}")
    cases = []

    def add(case, req, kinds, user_fields, amount_rule, cloc, name_filter=None, label=None):
        cases.append((case, req, kinds, user_fields, amount_rule, cloc, name_filter, label))

    EM = "processing_operations.energy_management"
    add("electricity:grid", _proc({"energy_management": {"monthly_electricity_consumption": 1000.0}}),
        ("electricity",), [f"{EM}.monthly_electricity_consumption (kWh/month)",
                           f"{EM}.renewable_energy_percentage (%)", f"{EM}.primary_energy_source",
                           "processed_products[].processing_steps[].energy_intensity (kWh/t) [fallback]"],
        "annual kWh = monthly x 12 (meter) else sum(step kWh/t) x t; grid share = 1 - renewable %; "
        "supply by primary_energy_source (ELECTRICITY_CARRIER)",
        f"{cite(P, r'^ELECTRICITY_CARRIER = ')}; {c_ds}; " + cite_def("engine/grid_calibration.py", "apply"))
    add("electricity:solar", _proc({"energy_management": {"monthly_electricity_consumption": 1000.0,
                                                         "renewable_energy_percentage": 50.0}}),
        ("electricity_onsite",), [f"{EM}.renewable_energy_percentage (%)"],
        "renewable share of annual kWh = on-site PV (capital goods included in the dataset)", c_ds)
    for src, kind in [("DieselGenerator", ("fuel",)), ("HydroElectricity", ("electricity_onsite",)),
                      ("WindPower", ("electricity_onsite",))]:
        add(f"electricity:{src}", _proc({"energy_management": {"monthly_electricity_consumption": 1000.0,
                                                               "primary_energy_source": src}}),
            kind, [f"{EM}.primary_energy_source='{src}'", f"{EM}.monthly_electricity_consumption (kWh/month)"],
            "genset kWh x 0.30 L/kWh diesel (GENSET_L_PER_KWH, IRENA 2015) else kWh of the declared supply",
            f"{cite(P, r'^ELECTRICITY_CARRIER = ')}; {c_ds}; {cite('engine/energy_carriers.py', r'^GENSET_L_PER_KWH = ')}")
    for ft in ["Diesel", "Diesel generator", "Petrol", "LPG", "Natural gas", "Kerosene", "Biodiesel",
               "Firewood", "Charcoal", "Palm kernel shell", "Palm fibre", "Biogas"]:
        add(f"fuel:{ft}", _proc({"energy_management": {"fuel_streams": [
            {"fuel_type": ft, "monthly_consumption": 10.0}]}}),
            ("fuel", "heat_fuel"), [f"{EM}.fuel_streams[] (fuel_type, monthly_consumption, unit, use)",
                                    f"{EM}.monthly_fuel_consumption + fuel_type (legacy single stream)"],
            "monthly x 12 in the declared unit (natural unit when blank); carrier_input converts to the "
            "dataset unit with the cited LHV; LPG/kerosene/firewood/charcoal split by fuels.expand_fuel_inputs",
            f"{c_ds}; {cite_def('engine/energy_carriers.py', 'carrier_input')}; {c_comb}")
    WM = "processing_operations.water_management"
    add("water:tap", _proc({"water_management": {"monthly_water_consumption": 100.0,
                                                 "water_source": ["Municipal"]}}),
        ("water",), [f"{WM}.monthly_water_consumption (m3/month)", f"{WM}.water_source",
                     "processed_products[].processing_steps[].water_usage (L/t) [fallback]"],
        "m3 x 1000 kg for municipal / unspecified sources; borehole, well, river, dam -> elementary "
        "withdrawal added after the solve (not matched)", cite_def(P, "_water_split"))
    for tr in ["ChemicalTreatment", "ReverseOsmosis"]:
        add(f"water:{tr}", _proc({"water_management": {"monthly_water_consumption": 100.0,
                                                       "water_treatment": tr}}),
            ("water",), [f"{WM}.water_treatment='{tr}'"],
            "treated-water dataset replaces the intake (WATER_TREATMENT_MATCH)",
            cite(P, r"^WATER_TREATMENT_MATCH = \{", r"^\}"), label=f"process water [water_treatment={tr}]")
    add("wastewater", _proc({"water_management": {"monthly_water_consumption": 100.0}}),
        ("wastewater",), [f"{WM}.wastewater_treatment (None -> no treatment row, flagged)"],
        "0.8 x water m3 (WASTEWATER_SHARE)", cite(P, r"^WASTEWATER_SHARE = "))
    for mat in ["PlasticBag", "Polypropylene", "PaperBag", "Jute", "Cardboard", "Metal", "Glass", "Composite"]:
        prod = copy.deepcopy(_PROD)
        prod["packaging"] = {"packaging_material": mat, "package_size": 50.0, "packaging_weight_per_unit": 0.1}
        add(f"packaging:{mat}", _proc(products=[prod]), ("packaging",),
            ["processed_products[].packaging.packaging_material", "package_size (kg)", "packaging_weight_per_unit (kg)"],
            "output kg / package_size x weight per unit", cite(P, r"^PACKAGING_MATCH = \{", r"^\}"))
    WS = "processing_operations.waste_management"
    for meth in ["Landfill", "Mixed", "Incineration", "Composting", "AnaerobicDigestion", "Recycling"]:
        add(f"waste:{meth}", _proc({"waste_management": {"solid_waste_generation": 10.0,
                                                         "waste_disposal_method": meth}}),
            ("waste",), [f"{WS}.solid_waste_generation (kg/day)", f"{WS}.organic_waste_percentage (default 70)",
                         f"{WS}.waste_disposal_method", f"{WS}.byproduct_utilization[] (cut-off)",
                         "facility_profile.operational_days_per_year"],
            "kg/day x days x (1 - by-product share) split organic / inorganic; recyclables burden-free",
            cite(P, r"^WASTE_SPLIT_MATCH = \{", r"^\}"))
    RS = "processing_operations.raw_material_sourcing"
    for mode in ["Truck", "Mixed", "Rail", "Ship"]:
        add(f"transport:{mode}", _proc({"raw_material_sourcing": {"transport_mode": mode}}),
            ("transport",), [f"{RS}.average_transport_distance (km)", f"{RS}.local_sourcing_percentage",
                             f"{RS}.transport_mode"],
            "raw-material tonnes x km; blank km -> local share x 50 km + rest x 230 km (PEFCR v6.3)",
            cite(P, r"^TRANSPORT_MATCH = \{", r"^\}"))
    out, seen = [], set()
    for case, req, kinds, uf, rule, cloc, _nf, label in cases:
        inputs, _notes, _kg = extract_processing_inputs(copy.deepcopy(req))
        inputs, _hn = flag_processing_raw_materials(inputs)   # same order as process_service
        inputs, _flows, _fn = fuels.expand_fuel_inputs(inputs)
        for inp in inputs:
            if inp.get("kind") not in kinds:
                continue
            name = label or inp["name"]
            if name in seen:
                continue
            seen.add(name)
            out.append({"input_name": name, "inp": _strip(inp), "case": case, "category": inp.get("kind"),
                        "user_fields": uf, "amount_rule": rule,
                        "code_location": f"{c_ext}; {cloc}; {C_MATCH()}",
                        "engine_display_name": inp["name"]})
    return out


# commodity -> raw-material names: the names at the baseline plus names the current hint table
# or default conversion ratios now cover.
NEW_RAW_MATERIALS = {
    "cocoa": ["Cocoa beans (dried, fermented)"],
    "palm_oil": ["Oil palm fresh fruit bunches (FFB)", "Palm fruit"],
    "maize": ["Maize grain"],
    "groundnuts": ["Groundnut paste"],
    "eggplant": ["Garden eggs", "Brinjal"],
    "chilli_peppers": ["Scotch bonnet pepper", "Hot pepper"],
    "bell_peppers": ["Sweet pepper"],
}


def raw_material_input(name: str) -> dict:
    from engine.process_inputs import extract_processing_inputs
    prod = copy.deepcopy(_PROD)
    prod["raw_material_inputs"] = [{"material_name": name, "quantity_per_tonne_output": 1000.0}]
    from engine.commodities import flag_processing_raw_materials
    inputs, _n, _k = extract_processing_inputs(_proc(products=[prod]))
    inputs, _hn = flag_processing_raw_materials(inputs)      # as engine/process_service.py
    rm = [i for i in inputs if i.get("kind") == "raw_material"]
    assert len(rm) == 1, name
    return _strip(rm[0])


# ---------------------------------------------------------------------------------------
# baseline (45ad6b6) via collect_rows()
# ---------------------------------------------------------------------------------------
FARM_ALIASES = {"petrol (farm)": "petrol, burned in agricultural machinery",
                "kerosene (farm)": "kerosene, burned in agricultural machinery",
                "biodiesel (farm)": "biodiesel, burned in agricultural machinery"}
PROC_ALIASES = {"solid waste (organic), landfill": "solid waste, landfill",
                "solid waste (organic), mixed": "solid waste, mixed",
                "solid waste (inorganic), incineration": "solid waste, incineration",
                "solid waste (organic), composting": "solid waste, composting",
                "solid waste (organic), anaerobicdigestion": "solid waste, anaerobicdigestion",
                "solid waste (organic), recycling": "solid waste, recycling"}


def load_baseline() -> tuple[dict, dict]:
    import engine.test_matcher_regression as tmr
    raw = subprocess.run(["git", "show", f"{BASELINE_FILE_REV}:docs/inventory_mapping/GMG_inventory_database_mapping.json"],
                         cwd=ROOT, capture_output=True, check=True).stdout
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "baseline.json"
        p.write_bytes(raw)
        old = tmr.MAPPING
        tmr.MAPPING = p
        try:
            rows = tmr.collect_rows()
        finally:
            tmr.MAPPING = old
    base = {}
    for r in rows:
        base[(r["section"], r["region"], r["input_name"].lower())] = r["before"]
    return base, json.loads(raw.decode("utf-8"))


# ---------------------------------------------------------------------------------------
# matcher
# ---------------------------------------------------------------------------------------
class Runner:
    def __init__(self, extra_cache: Path | None):
        import engine.test_matcher_regression as tmr
        from ingestion.matching import ProcessMatcher, OpenAIEmbedder
        from ingestion.query import CanonicalQuery
        why = tmr._store_ready()
        if why:
            raise SystemExit(f"cannot run the matcher: {why}")
        self.q = CanonicalQuery()
        emb = None
        if os.getenv("OPENAI_API_KEY"):
            try:
                emb = OpenAIEmbedder()
            except Exception:
                emb = None
        self.matcher = ProcessMatcher(self.q, embedder=emb or tmr._PinnedOnly())
        self.matcher.build_index()
        self.pinned = self.matcher.load_query_cache(tmr.QCACHE)
        self.extra_cache = extra_cache
        self.extra_loaded = self.matcher.load_query_cache(extra_cache) if extra_cache and extra_cache.exists() else 0
        self.fingerprint = tmr._fingerprint(self.matcher)
        self.live_embedder = emb is not None
        self._eng = {}

    def engine(self, region):
        from engine.orchestrator import FarmLCA
        if region not in self._eng:
            self._eng[region] = FarmLCA(region, matcher=self.matcher)
        return self._eng[region]

    def run(self, region: str, inp: dict) -> dict:
        from engine import units
        eng = self.engine(region)
        m, used = eng.resolve_input(dict(inp))
        if not m:
            return {"matched_process": None}
        proc = self.q.get_process(m["uid"]) or {}
        ref_unit = proc.get("ref_unit")
        try:
            _amt, note = units.to_ref_unit({**inp, "amount": 1.0}, ref_unit)
            unit_check = "same unit" if note is None else note
        except units.UnitMismatchError as e:
            unit_check = f"UNIT MISMATCH, input excluded at solve time: {e}"
        return {"matched_process": m["name"], "source": self.q.source_label(m["uid"]),
                "location": m.get("location"), "ref_unit": ref_unit, "uid": m["uid"],
                "score": round(float(m["score"]), 2), "needs_review": bool(m.get("needs_review")),
                "review_reason": m.get("review_reason") if m.get("needs_review") else None,
                "identity_basis": (m.get("identity") or {}).get("basis"),
                "fallback_used": used, "unit_check": unit_check}

    def close(self):
        if self.extra_cache:
            self.matcher.save_query_cache(self.extra_cache)
        for e in self._eng.values():
            e.close()
        self.q.close()


def _baseline_entry(base: dict, section: str, region: str, name: str, aliases: dict) -> dict | None:
    for nm in (name, aliases.get(name)):
        if nm and (section, region, nm.lower()) in base:
            b = base[(section, region, nm.lower())]
            out = {"name": b.get("name"), "location": b.get("location"), "uid": b.get("uid")}
            if nm != name:
                out["input_name_at_45ad6b6"] = nm
            return out
    return None


def _changed(before: dict | None, res: dict) -> bool | None:
    if before is None:
        return None
    if before.get("uid"):
        return before["uid"] != res.get("uid")
    return not ((before.get("name") or "")[:70] == (res.get("matched_process") or "")[:70]
                and before.get("location") == res.get("location"))


# Reviewer notes: wrong-product or wrong-location matches that the identity gate lets through
# (needs_review is false). Keyed by (input name, region or "*", substring of the matched name);
# a note is attached only while the executed match still contains that substring, so a code
# fix makes the note disappear on the next run instead of going stale.
REVIEWER_NOTES = [
    ("*", "*", "import from RoW", "fuel SUPPLY dataset (import, no combustion): the combustion emissions of the fuel are missing for this region"),
    ("*", "*", "market for diesel | diesel", "diesel SUPPLY dataset, not a combustion or generator dataset: combustion emissions are missing for this region"),
    ("*", "*", "voltage transformation from medium to low", "a voltage-transformation activity of ANOTHER country's grid, not the national low-voltage mix: no Burkina Faso grid dataset exists in the store, and the identity gate accepted this one"),
    ("*", "*", "platinum group metal", "wrong product: a platinum-group-metal refinery (copper co-product) instead of a copper fungicide production dataset"),
    ("*", "*", "market for waste glass", "wrong product: waste glass instead of packaging glass production"),
    ("*", "*", "Waste polyethylene", "wrong product: waste polyethylene instead of packaging film production"),
    ("*", "*", "market for maize grain", "wrong product: maize grain (food/feed) instead of maize seed for sowing; the hint 'market for maize seed, for sowing' lost to the grain market"),
    ("*", "*", "maize grain production | maize grain", "wrong product for a SEED input: maize grain instead of maize seed for sowing"),
    ("*", "*", "Digestate, from anaerobic digestion", "wrong product: digestate (per kg) instead of biogas; the m3 amount cannot be converted, so the input is excluded at solve time"),
    ("*", "*", "market for water, decarbonised", "for reverse-osmosis water this is decarbonised (not deionised) water"),
    ("*", "*", "market for wood chips", "wood chips instead of cleft timber (firewood); combustion added separately by engine/fuels.py"),
    ("*", "*", "carrot seed production", "carrot seed is the declared vegetable seed proxy (engine/crop_defaults.SEED_RATES)"),
    ("*", "*", "cucumber production, in heated greenhouse", "only a heated-greenhouse cucumber dataset exists in the store; open-field cucumber is a proxy"),
    ("*", "*", "Honey, raw, small-scale production", "WFLDB Swiss small-scale honey: order-of-magnitude proxy, flagged by engine/commodities.py"),
    ("*", "*", "processed in FR | Ambient", "consumer-stage French Agribalyse cocoa butter (includes packaging and retail stages): a refined-ingredient proxy"),
    ("hydro", "*", "", "hydro and wind electricity: no African dataset; the location chosen is outside the region's preference list (unranked), so it is effectively arbitrary among equal-product datasets"),
    ("wind", "*", "", "hydro and wind electricity: no African dataset; the location chosen is outside the region's preference list (unranked), so it is effectively arbitrary among equal-product datasets"),
]


def reviewer_note(input_name: str, region: str, res: dict) -> str:
    name = (res or {}).get("matched_process") or ""
    out = []
    for inp, reg, needle, note in REVIEWER_NOTES:
        if inp not in ("*", input_name) or reg not in ("*", region):
            continue
        if needle and needle not in name:
            continue
        if note not in out:
            out.append(note)
    if str((res or {}).get("unit_check", "")).startswith("UNIT MISMATCH"):
        out.append("the matched dataset's reference unit cannot take this amount: the input is EXCLUDED from the result at solve time (validation warning)")
    return ("; ".join(f"{region}: {n}" if region else n for n in out)) if out else ""


def short(res: dict) -> str | None:
    if not res or not res.get("matched_process"):
        return None
    s = f"{res['matched_process']} [{res['source']}, {res['location']}, per {res['ref_unit']}]"
    if res.get("needs_review"):
        s += " (NEEDS REVIEW)"
    return s


# ---------------------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------------------
def build(runner: Runner, base: dict, old_doc: dict) -> dict:
    farm = farm_catalogue()
    proc = processing_catalogue()
    stats = {"rows": 0, "changed": 0, "unchanged": 0, "new": 0, "needs_review": [], "per_section_region": {}}

    def tally(section, region, res, before):
        k = f"{section}|{region}"
        stats["per_section_region"][k] = stats["per_section_region"].get(k, 0) + 1
        stats["rows"] += 1
        ch = _changed(before, res)
        if ch is None:
            stats["new"] += 1
        elif ch:
            stats["changed"] += 1
        else:
            stats["unchanged"] += 1
        if res.get("needs_review"):
            stats["needs_review"].append(f"{section}|{region}|{res.get('_name')}")
        return ch

    farm_rows = []
    for row in farm:
        inp = row["inp"]
        for reg in REGIONS_RUN:
            res = runner.run(reg, inp)
            before = _baseline_entry(base, "farm", reg, row["input_name"], FARM_ALIASES)
            res["_name"] = row["input_name"]
            ch = tally("farm", reg, res, before)
            res.pop("_name")
            farm_rows.append({
                "input_name": row["input_name"], "input_category": inp.get("kind"),
                "how_name_is_built": row["how_name_is_built"], "amount_unit_passed": inp.get("unit"),
                "match_target": inp.get("match_as") or inp["name"], "region": reg,
                "matched_process": res.get("matched_process"), "source_database": res.get("source"),
                "location": res.get("location"), "ref_unit": res.get("ref_unit"), "uid": res.get("uid"),
                "match_score": res.get("score"), "needs_review": res.get("needs_review"),
                "review_reason": res.get("review_reason"), "identity_basis": res.get("identity_basis"),
                "unit_check": res.get("unit_check"),
                "unit_consistent": not str(res.get("unit_check", "")).startswith("UNIT MISMATCH"),
                BASE_KEY: before or "not run at 45ad6b6 (new region or new input row)",
                "changed_vs_45ad6b6": ch,
                "produced_by": row["produced_by"], "code_location": row["code_location"],
                "notes": reviewer_note(row["input_name"], reg, res),
            })
    proc_rows = []
    for row in proc:
        inp = row["inp"]
        by_region = {}
        for reg in REGIONS_RUN:
            res = runner.run(reg, inp)
            before = _baseline_entry(base, "processing", reg, row["input_name"], PROC_ALIASES)
            res["_name"] = row["input_name"]
            ch = tally("processing", reg, res, before)
            res.pop("_name")
            by_region[reg] = {"matched_process": res.get("matched_process"), "location": res.get("location"),
                              "ref_unit": res.get("ref_unit"), "source": res.get("source"),
                              "cosine_score": res.get("score"), "uid": res.get("uid"),
                              "needs_review": res.get("needs_review"), "review_reason": res.get("review_reason"),
                              "unit_check": res.get("unit_check"),
                              BASE_KEY: before or "not run at 45ad6b6 (new region or new input row)",
                              "changed_vs_45ad6b6": ch}
        proc_rows.append({
            "input_name": row["input_name"], "engine_display_name": row["engine_display_name"],
            "category": row["category"], "user_fields": row["user_fields"], "amount_rule": row["amount_rule"],
            "match_target_sent_to_matcher": inp.get("match_as") or inp["name"],
            "amount_unit_passed": inp.get("unit"), "by_region": by_region,
            "source_database_or_citation": "; ".join(f"{r}: {v['source']}" for r, v in by_region.items()),
            "code_location": row["code_location"],
            "notes": [n for n in (reviewer_note(row["input_name"], reg, v) for reg, v in by_region.items()) if n],
        })

    raw_rows: dict[str, list] = {}
    P = "engine/process_inputs.py"
    c_raw = "; ".join([cite(P, r"^REFINED_MATERIAL_HINTS = \{", r"^\}"), cite(P, r"^RAW_MATERIAL_HINTS = \{", r"^\}"),
                       cite_def(P, "_raw_material_match"), cite_def(P, "_raw_material_rows"),
                       cite_def(P, "extract_processing_inputs"), C_MATCH()])
    old_names = {}
    for ck, cv in old_doc["commodities"].items():
        names = []
        for p in cv.get("processing") or []:
            for i in p.get("commodity_specific_inputs") or []:
                m = re.match(r"raw material: '(.*)'", i["input_name"])
                if m:
                    names.append(m.group(1))
        old_names[ck] = names
    for ck in old_doc["commodities"]:
        names = list(old_names.get(ck, [])) + [n for n in NEW_RAW_MATERIALS.get(ck, []) if n not in old_names.get(ck, [])]
        for name in names:
            inp = raw_material_input(name)
            by_region = {}
            for reg in REGIONS_RUN:
                res = runner.run(reg, inp)
                before = _baseline_entry(base, "raw_material", reg, name, {})
                res["_name"] = name
                ch = tally("raw_material", reg, res, before)
                res.pop("_name")
                by_region[reg] = {"matched_process": res.get("matched_process"), "location": res.get("location"),
                                  "ref_unit": res.get("ref_unit"), "source": res.get("source"),
                                  "cosine_score": res.get("score"), "uid": res.get("uid"),
                                  "needs_review": res.get("needs_review"), "review_reason": res.get("review_reason"),
                                  BASE_KEY: before or "not run at 45ad6b6 (new region or new input row)",
                                  "changed_vs_45ad6b6": ch}
            raw_rows.setdefault(ck, []).append({
                "input_name": f"raw material: '{name}'",
                "category": "raw material (cradle part; usually dominant)",
                "user_fields": ["processed_products[].raw_material_inputs[].material_name (free text)",
                                "processed_products[].raw_material_inputs[].quantity_per_tonne_output (kg per tonne output)"],
                "amount_rule": ("kg = quantity_per_tonne_output x annual_production t; when no raw material is declared, "
                                "the default conversion ratio for the product type (engine/conversion_ratios.py) "
                                "divided by (1 - storage loss) is used and flagged estimated"),
                "match_target_sent_to_matcher": inp.get("match_as"),
                "refined_ingredient": bool(inp.get("refined")),
                "by_region": by_region,
                "source_database_or_citation": "; ".join(f"{r}: {v['source']}" for r, v in by_region.items()),
                "value_if_factor": None, "code_location": c_raw,
                "added_in_this_version": name not in old_names.get(ck, []),
                "notes": [f"_raw_material_match('{name}') -> hint '{inp.get('match_as')}', refined={bool(inp.get('refined'))}. "
                          "The engine sends no fallback for raw materials: if the hint has no dataset of the right "
                          "product, the match is returned with needs_review=true."]
                + [n for n in (reviewer_note(name, reg, v) for reg, v in by_region.items()) if n],
            })
    return {"farm": farm_rows, "processing": proc_rows, "raw": raw_rows, "stats": stats}


def field_flow_rows() -> list[dict]:
    from engine.flowmap import ONFARM_FLOWS, OnFarmFlowMap
    from ingestion.query import CanonicalQuery
    fmap, q = OnFarmFlowMap(), CanonicalQuery()
    rows = []
    for key, (cands, cas, medium) in ONFARM_FLOWS.items():
        uid = fmap.resolve(key)
        f = q.conn.execute("SELECT * FROM flows WHERE uid=?", (uid,)).fetchone() if uid else None
        f = dict(f) if f else {}
        src = None
        if f:
            s = q.conn.execute("SELECT name, version FROM sources WHERE id=?", (f.get("source_id"),)).fetchone()
            src = f"{s['name']} {s['version'] or ''}".strip() if s else None
        cfs = []
        for method in ("ReCiPe 2016 v1.03, midpoint (H)", "EF v3.1"):
            if not uid:
                continue
            ch = q.characterize_flows({uid: {"amount": 1.0, "name": f.get("name"), "unit": f.get("ref_unit")}}, method)
            for cat, v in sorted(ch.items()):
                val = float(v.get("value") or 0.0)
                if abs(val) > 0:
                    cfs.append({"method": method, "category": cat, "cf_per_unit": round(val, 6), "unit": v.get("unit")})
        rows.append({"kernel_flow": key, "store_flow_uid_or_name": uid, "store_flow_name": f.get("name"),
                     "store_flow_source": src, "compartment": f.get("category"),
                     "flowmap_name_candidates": list(cands), "cas": f.get("cas"), "characterised_by": cfs,
                     "code_location": cite("engine/flowmap.py", rf'^\s*"{re.escape(key)}":')})
    fmap.close()
    q.close()
    return rows


def region_rows(proc_rows: list[dict]) -> dict:
    from engine.regions import REGIONS
    from engine import grid_calibration, activity_defaults
    elec = next((r for r in proc_rows if r["input_name"] == "electricity low voltage"), None)
    out = {}
    for code, r in REGIONS.items():
        ef, src = grid_calibration.grid_factor(r)
        tp = activity_defaults.table_path_for(r)
        g = (elec or {}).get("by_region", {}).get(code, {})
        out[code] = {
            "name": r.name, "default_method": r.default_method, "climate_zone": r.climate_zone,
            "ipcc_n2o_ef1": r.ipcc_n2o_ef1, "ef4": r.ef4, "ef5": r.ef5, "frac_leach": r.frac_leach,
            "frac_gasf": r.frac_gasf, "frac_gasm": r.frac_gasm,
            "aware_country_key": r.aware_country, "aware_key_used_at_runtime": True,
            "location_prefer": list(r.location_prefer),
            "grid": {"matched_dataset": g.get("matched_process"), "matched_location": g.get("location"),
                     "calibration_kgco2e_per_kwh": ef, "calibration_source": src,
                     "calibration": ("grid_calibration.apply adds fossil CO2 to grid-electricity inputs so the "
                                     f"climate result equals {ef} kg CO2e/kWh (USE_OFFICIAL_GRID_EF=1 default)")
                     if ef is not None else "none: raw dataset value (no grid factor for this region)"},
            "activity_defaults": (f"engine/recommend/reference/{tp.name}" if tp else
                                  "none: no activity-defaults table for this region (no diesel/electricity injected)"),
            "ghana_inherited_fields": list(r.ghana_inherited),
            "matcher_executed": code in REGIONS_RUN,
            "code_location": cite("engine/regions.py", rf'^\s*"{code}": Region\('),
        }
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--dry-run", action="store_true", help="do not write the two JSON files")
    ap.add_argument("--dump", type=Path, help="write {row key: uid} here (for determinism checks)")
    ap.add_argument("--query-cache", type=Path, help="extra query-vector cache to read and update")
    args = ap.parse_args(argv)

    base, old_doc = load_baseline()
    runner = Runner(args.query_cache)
    try:
        out = build(runner, base, old_doc)
    finally:
        runner.close()
    flows = field_flow_rows()
    regions = region_rows(out["processing"])
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()
    run_meta = {"script": "scripts/regenerate_inventory_mapping.py", "repository_commit": head,
                "baseline_commit": BASELINE_COMMIT, "regions": REGIONS_RUN,
                "GMG_LLM_ADJUDICATE": os.environ.get("GMG_LLM_ADJUDICATE"),
                "pinned_query_vectors_loaded": runner.pinned,
                "extra_query_vectors_loaded": runner.extra_loaded,
                "live_query_embedding_available": runner.live_embedder,
                "process_index_fingerprint": runner.fingerprint,
                "rows": out["stats"]["rows"], "per_section_region": out["stats"]["per_section_region"],
                "changed_vs_baseline": out["stats"]["changed"], "unchanged_vs_baseline": out["stats"]["unchanged"],
                "not_in_baseline": out["stats"]["new"], "needs_review_rows": out["stats"]["needs_review"]}

    if args.dump:
        keys = {}
        for r in out["farm"]:
            keys[f"farm|{r['region']}|{r['input_name']}"] = r["uid"]
        for r in out["processing"]:
            for reg, v in r["by_region"].items():
                keys[f"processing|{reg}|{r['input_name']}"] = v["uid"]
        for ck, rows in out["raw"].items():
            for r in rows:
                for reg, v in r["by_region"].items():
                    keys[f"raw_material|{reg}|{r['input_name']}"] = v["uid"]
        args.dump.write_text(json.dumps({"meta": run_meta, "uids": keys}, indent=1, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({k: v for k, v in run_meta.items() if k != "needs_review_rows"}, indent=1))
    print(f"needs_review rows: {len(run_meta['needs_review_rows'])}")
    if args.dry_run:
        return 0

    d = json.loads(DETAIL.read_text(encoding="utf-8"))
    s = json.loads(SUMMARY.read_text(encoding="utf-8"))
    # ---- detailed file
    keep_all = [r for r in d["shared_farm_inventory"]["purchased_inputs_to_database_processes"]
                if r.get("region") == "all"]
    d["shared_farm_inventory"]["purchased_inputs_to_database_processes"] = out["farm"] + keep_all
    d["shared_farm_inventory"]["on_farm_field_flows_to_characterisation"] = _merge_flows(
        d["shared_farm_inventory"].get("on_farm_field_flows_to_characterisation") or [], flows)
    refr = [r for r in d["shared_processing_inventory"]["inputs_to_database_processes"]
            if not r.get("by_region")]
    d["shared_processing_inventory"]["inputs_to_database_processes"] = out["processing"] + refr
    for ck, rows in out["raw"].items():
        procs = d["commodities"][ck].get("processing") or []
        if not procs:
            continue
        for p in procs:
            p["commodity_specific_inputs"] = [i for i in (p.get("commodity_specific_inputs") or [])
                                              if not i["input_name"].startswith("raw material: '")]
        old_by_name = {}
        for i, p in enumerate((old_doc["commodities"][ck].get("processing") or [])):
            for it in p.get("commodity_specific_inputs") or []:
                old_by_name[it["input_name"]] = i
        for r in rows:
            idx = min(old_by_name.get(r["input_name"], 0), len(procs) - 1)
            lst = procs[idx].setdefault("commodity_specific_inputs", [])
            lst.append(r)
        for p in procs:   # raw materials first, other commodity inputs after
            p["commodity_specific_inputs"].sort(key=lambda i: not i["input_name"].startswith("raw material: '"))
    d["generation_run"] = run_meta
    s_regions = {**regions, "aliases": (s.get("regions") or {}).get("aliases")}
    d["regions"] = s_regions
    # ---- summary quick tables
    qt = s["quick_mapping_tables"]
    farm_tbl: dict = {}
    for r in out["farm"]:
        e = farm_tbl.setdefault(r["input_name"], {"category": r["input_category"], "match_target": r["match_target"]})
        e[r["region"]] = short({"matched_process": r["matched_process"], "source": r["source_database"],
                                "location": r["location"], "ref_unit": r["ref_unit"], "needs_review": r["needs_review"]})
    qt["farm_purchased_inputs_all_crops"] = farm_tbl
    qt["processing_shared_inputs_all_commodities"] = {
        r["input_name"]: {"match_target": r["match_target_sent_to_matcher"],
                          **{reg: short({**v, "matched_process": v["matched_process"]}) for reg, v in r["by_region"].items()}}
        for r in out["processing"]}
    qt["processing_shared_inputs_all_commodities"]["refrigerant leakage (on-site)"] = {
        "note": "not matched: direct on-site emission characterised from engine/refrigerants.py GWP table"}
    qt["processing_raw_material_by_commodity"] = {
        ck: {r["input_name"]: {"match_target": r["match_target_sent_to_matcher"],
                               **{reg: short(v) for reg, v in r["by_region"].items()}} for r in rows}
        for ck, rows in out["raw"].items()}
    qt["farm_direct_field_emissions_all_crops"] = [
        {"flow": f["kernel_flow"], "store_flow": f["store_flow_name"], "compartment": f["compartment"]} for f in flows]
    s["regions"] = s_regions
    s["generation_run"] = run_meta
    DETAIL.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(s, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {DETAIL.relative_to(ROOT)} and {SUMMARY.relative_to(ROOT)}")
    return 0


def _merge_flows(old: list[dict], new: list[dict]) -> list[dict]:
    """Executed columns from `new`; hand-written kernel_source / notes kept from `old`."""
    prev = {r.get("kernel_flow"): r for r in old}
    out = []
    for r in new:
        p = prev.get(r["kernel_flow"], {})
        out.append({"kernel_flow": r["kernel_flow"], "kernel_source": p.get("kernel_source", ""),
                    **{k: v for k, v in r.items() if k != "kernel_flow"}, "notes": p.get("notes", "")})
    return out


if __name__ == "__main__":
    raise SystemExit(main())
