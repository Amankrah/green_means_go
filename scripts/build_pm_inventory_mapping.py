"""Build the clean, PM-facing inventory mapping from the full validated mapping.

Output: docs/inventory_mapping/PM_inventory_mapping.json
No repository details (paths, line numbers, code names) are carried over.
"""
import datetime
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs/inventory_mapping/GMG_inventory_database_mapping.json"
OUT = ROOT / "docs/inventory_mapping/PM_inventory_mapping.json"

d = json.load(open(SRC, encoding="utf-8"))
REGION_NAME = {"GH": "Ghana", "NG": "Nigeria", "SN": "Senegal", "ZA": "South Africa"}

PATH_RE = re.compile(r"(?:[\w\-]+/)*[\w\-.]+\.(?:py|rs|json|jsonl|ts|tsx|md|toml|sqlite|npz)(?::\d+(?:-\d+)?)?")
WORDS = [
    (r"\bPydantic defaults?\b", "software default"),
    (r"\bengine (?:logic|design)\b", "software default"),
    (r"\s*\(cited in code\)", ""),
    (r"\bfuel_type\b", "fuel type"),
    (r"\bproduct_type\b", "product type"),
    (r"\bprimary_energy_source\b", "primary energy source"),
    (r"\baverage_transport_distance\b", "average transport distance"),
    (r"\blocal_sourcing_percentage\b", "local sourcing percentage"),
    (r"\boperational_days_per_year\b", "operational days per year"),
    (r"\btransport_mode\b", "transport mode"),
    (r"\bextraction fallback\b", "software default"),
    (r"\bstorage_loss_percentage\b", "storage loss percentage"),
]


def clean_text(s):
    if not isinstance(s, str):
        return s
    s = PATH_RE.sub("", s)
    for pat, rep in WORDS:
        s = re.sub(pat, rep, s)
    s = re.sub(r"\(\s*\)", "", s)
    s = re.sub(r"\s{2,}", " ", s).strip(" ;,")
    return s


def mapped(proc, source, location, unit):
    parts = [proc, source, location]
    if unit:
        parts.append("per " + str(unit))
    return " | ".join(str(p) for p in parts if p)


# ---------- shared farm data per region ----------
def region_block(R):
    r = d["regions"][R]
    g = r.get("grid", {})
    return {
        "impact_assessment_method": r.get("default_method"),
        "ipcc_climate_zone": r.get("climate_zone"),
        "n2o_emission_factor_ef1_kg_n2o_n_per_kg_n": r.get("ipcc_n2o_ef1"),
        "ef4_volatilisation": r.get("ef4"),
        "ef5_leaching": r.get("ef5"),
        "frac_gasf": r.get("frac_gasf"),
        "frac_gasm": r.get("frac_gasm"),
        "frac_leach": r.get("frac_leach"),
        "grid_electricity_dataset": g.get("matched_dataset"),
        "grid_electricity_kg_co2e_per_kwh": g.get("calibration_kgco2e_per_kwh") or g.get("official_grid_ef_kgco2_per_kwh"),
        "water_scarcity_indicator": "AWARE 2.0, country factor for " + r.get("aware_country_key", R),
    }


def farm_inputs(R, seed_keywords):
    rows = [p for p in d["shared_farm_inventory"]["purchased_inputs_to_database_processes"] if p["region"] == R]
    out = {}
    for p in sorted(rows, key=lambda x: (x["input_category"], x["input_name"])):
        name = p["input_name"]
        if name.lower().endswith(" seed") and not any(k in name.lower() for k in seed_keywords):
            continue
        entry = {
            "category": p["input_category"],
            "unit_entered": p.get("amount_unit_passed"),
            "mapped_data": mapped(p["matched_process"], p["source_database"], p["location"], p["ref_unit"]),
        }
        if p.get("needs_review"):
            entry["status"] = "needs review: " + clean_text(p.get("review_reason") or "")
        out[name] = entry
    return out


def field_emissions():
    out = []
    for f in d["shared_farm_inventory"]["on_farm_field_flows_to_characterisation"]:
        cfs = [c for c in f.get("characterised_by", []) if "ReCiPe" in c["method"]]
        out.append({
            "emission_or_resource": f.get("store_flow_name"),
            "compartment": (f.get("compartment") or "").replace("Elementary flows/", ""),
            "characterised_as": [f'{c["category"]}: {c["cf_per_unit"]} {c["unit"]} per unit' for c in cfs]
            or ["not characterised under ReCiPe 2016"],
        })
    return out


DROP = ("frontend", "recommendation measure", "band-calibration", "legacy", "measure ids", "variety list",
        "price feed", "processing-stage factors", "conversion ratio", "raw-material hint", "canonical store",
        "palmoilmill", "crop-residue parameters")

# IPCC 2019 Refinement Vol 4 Ch 11 Table 11.1A rows as applied by the engine (transcribed from the kernel's residue table)
RESIDUE = {
    "maize": dict(n_ag=0.006, n_bg=0.007, r_ag=1.0, rs=0.22, dry=0.87, cf=0.80,
                  source="IPCC 2019 Refinement Vol 4 Ch 11 Table 11.1A row 'Maize'; combustion factor Vol 4 Ch 2 Table 2.6 'Maize'"),
    "groundnuts": dict(n_ag=0.016, n_bg=0.008, r_ag=1.0, rs=0.19, dry=0.94, cf=0.85,
                       source="IPCC 2019 Refinement Vol 4 Ch 11 Table 11.1A row 'Peanuts' (N_BG and RS from 'Beans and Pulses' per note e)"),
    "cocoa": dict(n_ag=0.008, n_bg=0.009, r_ag=1.0, rs=0.22, dry=0.925, cf=0.85,
                  source="IPCC 2019 Table 11.1A generic row (no cocoa row); DRY 0.925 at ICCO 7.5% max moisture; below-ground term renewed at 1/plantation lifetime (Eq 11.6 Frac_Renew)"),
    "palm_oil": dict(n_ag=0.008, n_bg=0.009, r_ag=1.0, rs=0.22, dry=0.85, cf=0.85,
                     source="IPCC 2019 Table 11.1A generic row (no oil palm row); below-ground term renewed at 1/plantation lifetime (Eq 11.6 Frac_Renew)"),
    "tomato": dict(n_ag=0.008, n_bg=0.009, r_ag=1.0, rs=0.22, dry=0.055, cf=0.85,
                   source="IPCC 2019 Table 11.1A generic row; DRY from USDA FoodData Central 'Tomatoes, red, ripe, raw'"),
    "eggplant": dict(n_ag=0.008, n_bg=0.009, r_ag=1.0, rs=0.22, dry=0.077, cf=0.85,
                     source="IPCC 2019 Table 11.1A generic row; DRY from USDA FoodData Central 'Eggplant, raw'"),
    "cucumber": dict(n_ag=0.008, n_bg=0.009, r_ag=1.0, rs=0.22, dry=0.048, cf=0.85,
                     source="IPCC 2019 Table 11.1A generic row; DRY from USDA FoodData Central 'Cucumber, with peel, raw'"),
    "chilli_peppers": dict(n_ag=0.008, n_bg=0.009, r_ag=1.0, rs=0.22, dry=0.12, cf=0.85,
                           source="IPCC 2019 Table 11.1A generic row; DRY from USDA FoodData Central 'Peppers, hot chili, green, raw'"),
    "bell_peppers": dict(n_ag=0.008, n_bg=0.009, r_ag=1.0, rs=0.22, dry=0.061, cf=0.85,
                         source="IPCC 2019 Table 11.1A generic row; DRY from USDA FoodData Central 'Peppers, sweet, green, raw'"),
}


def residue_rows(key):
    r = RESIDUE[key]
    return [{
        "parameter": "Crop residue N2O inputs (IPCC 2019 Eq 11.6 and 11.7)",
        "value": {
            "N content above-ground residue (N_AG)": r["n_ag"],
            "N content below-ground residue (N_BG)": r["n_bg"],
            "above-ground residue to yield ratio (R_AG)": r["r_ag"],
            "root to shoot ratio (RS)": r["rs"],
            "dry matter fraction of harvested product (DRY)": r["dry"],
            "combustion factor if burnt (C_f)": r["cf"],
        },
        "unit": "kg N per kg dry matter; ratios; fractions",
        "source": r["source"],
    }]


def crop_data(key, regions):
    c = d["commodities"][key]
    rows = []
    for p in c.get("farm_production_crop_specific_data", []):
        name = p["parameter"]
        low = name.lower()
        if any(t in low for t in DROP):
            continue
        if "yield guide" in low:
            if str(p.get("value", "")).startswith("no crop key"):
                continue
            if low.startswith("ghana") and "GH" not in regions:
                continue
            m = re.match(r"^([A-Z]{2}) ", name)
            if m and m.group(1) not in regions:
                continue
        val = p.get("value")
        src = clean_text(p.get("source"))
        if (not src or "provenance block" in src) and "yield guide" in low:
            src = "national agricultural statistics (benchmark only)"
        rows.append({"parameter": clean_text(name), "value": val, "unit": p.get("unit"), "source": src})
    return rows + residue_rows(key)


DROP_DEFAULTS = ("legacy", "importer", "energy_carriers", "embedding", "declares no raw")


def processing_block(key, regions):
    out = []
    for t in d["commodities"][key]["processing"]:
        raw = {}
        for i in t["commodity_specific_inputs"]:
            br = i.get("by_region") or {}
            raw[i["input_name"].replace("raw material: ", "").strip("'")] = {
                REGION_NAME[R]: mapped(br[R].get("matched_process"), br[R].get("source"), br[R].get("location"), br[R].get("ref_unit"))
                for R in regions if R in br
            }
        defaults = []
        for p in t.get("default_parameters", []):
            blob = (str(p.get("parameter", "")) + str(p.get("value", ""))).lower()
            if any(tok in blob for tok in DROP_DEFAULTS):
                continue
            defaults.append({"parameter": p["parameter"], "value": p.get("value"), "unit": p.get("unit") or None,
                             "source": p.get("source") or None})
        for p in d["commodities"][key].get("farm_production_crop_specific_data", []):
            if "conversion ratio for product" in p["parameter"].lower():
                defaults.append({"parameter": p["parameter"], "value": p.get("value"), "unit": p.get("unit"), "source": p.get("source")})
        out.append({
            "facility_and_product_type": t["processing_type"].replace("facility_type=", "facility: ").replace("product_type=", "product: "),
            "raw_material_inputs": raw,
            "default_parameters": defaults,
        })
    return out


def shared_processing(regions):
    out = {}
    for i in d["shared_processing_inventory"]["inputs_to_database_processes"]:
        br = i.get("by_region") or {}
        out[i["input_name"]] = {
            "category": i.get("category"),
            "unit_entered": i.get("amount_unit_passed"),
            **{REGION_NAME[R]: mapped(br[R].get("matched_process"), br[R].get("source"), br[R].get("location"), br[R].get("ref_unit"))
               for R in regions if R in br},
        }
    return out


def farm_block(crop_keys, regions, seed_keywords):
    block = {"crop_specific_data": {}, "region_parameters": {}, "purchased_inputs": {}, "direct_field_emissions": field_emissions()}
    for k in crop_keys:
        block["crop_specific_data"][k] = crop_data(k, regions)
    if len(crop_keys) == 1:
        block["crop_specific_data"] = block["crop_specific_data"][crop_keys[0]]
    for R in regions:
        block["region_parameters"][REGION_NAME[R]] = region_block(R)
        block["purchased_inputs"][REGION_NAME[R]] = farm_inputs(R, seed_keywords)
    return block


SCOPES = [
    ("Cocoa", ["cocoa"], ["GH"], ["Farm"], ["cocoa"]),
    ("Palm Oil", ["palm_oil"], ["GH", "NG"], ["Farm", "Processing"], ["palm"]),
    ("Maize", ["maize"], ["GH", "NG"], ["Farm", "Processing"], ["maize"]),
    ("Groundnuts", ["groundnuts"], ["GH", "NG"], ["Farm", "Processing"], ["groundnut"]),
    ("Vegetables (tomato, eggplant, cucumber, chilli peppers, bell peppers)",
     ["tomato", "eggplant", "cucumber", "chilli_peppers", "bell_peppers"], ["SN"], ["Farm"],
     ["tomato", "eggplant", "cucumber", "chilli", "bell pepper"]),
    ("Honey", ["honey"], ["ZA"], ["Processing"], []),
]

commodities = []
for label, keys, regions, stages, seeds in SCOPES:
    entry = {"commodity": label, "countries": [REGION_NAME[R] for R in regions], "stages": stages}
    if "Farm" in stages:
        entry["farm_level"] = farm_block(keys, regions, seeds)
    if "Processing" in stages:
        entry["processing"] = {
            "commodity_specific": processing_block(keys[0], regions),
            "shared_facility_inputs": shared_processing(regions),
        }
    if label == "Honey":
        entry["note"] = ("Honey has no farm-level (apiculture) inventory in Green Means Go. The processing stage treats raw honey as a "
                         "purchased ingredient mapped to the WFLDB small-scale honey dataset (Switzerland) as a proxy, flagged as such in results.")
    commodities.append(entry)

doc = {
    "title": "Green Means Go - Inventory Database Mapping",
    "date": datetime.date.today().isoformat(),
    "scope": [
        "Cocoa - Ghana - Farm only",
        "Palm Oil - Ghana and Nigeria - Farm + Processing",
        "Maize - Ghana and Nigeria - Farm + Processing",
        "Groundnuts - Ghana and Nigeria - Farm + Processing",
        "Vegetables - Senegal - Farm only",
        "Honey - South Africa - Processing only",
    ],
    "how_to_read": {
        "input_name": "The input as entered or selected by the user.",
        "mapped_data": "Background dataset used for that input: dataset name | database | geography | reference unit.",
        "direct_field_emissions": "Emissions and resource uses computed on the farm from the user's own activity data (IPCC 2019 Tier 1) and the impact categories they are characterised in.",
        "region_parameters": "Country-level factors applied to every crop in that country.",
        "crop_specific_data": "Values that depend on the crop itself.",
        "databases": "ecoinvent 3.11 (cut-off), AGRIBALYSE 3.2 (including WFLDB-adapted datasets); characterisation ReCiPe 2016 v1.03 midpoint (H); water scarcity AWARE 2.0.",
    },
    "commodities": commodities,
}


def deep_clean(x):
    if isinstance(x, dict):
        return {k: deep_clean(v) for k, v in x.items()}
    if isinstance(x, list):
        return [deep_clean(v) for v in x]
    return clean_text(x)


doc = deep_clean(doc)
json.dump(doc, open(OUT, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
txt = open(OUT, encoding="utf-8").read()
leaks = sorted(set(re.findall(r"[\w\-/]+\.(?:py|rs|ts|tsx|jsonl|npz)\b|engine/|app/|african_lca|Pydantic|engine logic|engine design|cited in code", txt)))
print(OUT, len(txt) // 1024, "KB; em-dashes:", txt.count("—"), "; leaks:", leaks)
