"""
vocab.py: controlled vocabularies the engine actually recognises, plus deterministic
synonyms. classify() maps free text onto these labels; a label is always one of them.

Sources (checked against the code, not invented):
  crop        : crops the Rust kernel's regional data carries (african_lca_backend/src/
                production/data.rs), the wizard's COMMON_CROPS_BY_REGION
                (african-lca-frontend/src/lib/enhanced-assessment-schema.ts), the crop
                keywords of engine/process_inputs.RAW_MATERIAL_HINTS, and the crops named for
                the new SN / BF / ZA regions in the team brief (section 3b).
  fertiliser  : the wizard's FertilizerType enum (african-lca-frontend/src/types/
                enhanced-assessment.ts) plus the straight N/P/K products sold in West and
                Southern Africa that have ecoinvent 3.11 market datasets (ammonium nitrate,
                calcium ammonium nitrate, ammonium sulphate, triple superphosphate,
                potassium sulphate).
  fuel        : keys of engine/inputs.FUEL_MJ_PER_L and engine/process_inputs.FUEL_MJ_PER_L
                (the only fuels with a lower heating value in code; anything else silently
                becomes diesel today, which is exactly why classification helps).
  raw_material: keys of engine/process_inputs.REFINED_MATERIAL_HINTS and RAW_MATERIAL_HINTS
                (a label is a string _raw_material_match() resolves deterministically).
  packaging   : app/processing/models.PackagingMaterial values (= process_inputs.PACKAGING_MATCH keys).
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.inputs import FUEL_MJ_PER_L as _FARM_FUELS  # noqa: E402
from engine.process_inputs import (  # noqa: E402
    FUEL_MJ_PER_L as _FACILITY_FUELS,
    PACKAGING_MATCH,
    RAW_MATERIAL_HINTS,
    REFINED_MATERIAL_HINTS,
)

KINDS = ("crop", "fertiliser", "fuel", "raw_material", "packaging")

CROPS = sorted({
    # Rust kernel regional data + wizard regional crop lists (GH, NG, CA)
    "maize", "rice", "millet", "sorghum", "cowpea", "groundnut", "cocoa", "cassava", "yam",
    "cocoyam", "plantain", "sweet potato", "soybean", "cotton", "oil palm", "wheat", "canola",
    "barley", "oats", "lentils", "field peas", "flax", "potato", "vegetables",
    # process_inputs.RAW_MATERIAL_HINTS crops
    "banana", "coffee", "sugarcane", "sunflower", "tomato", "cabbage", "onion", "carrot",
    "fava bean",
    # new regions SN / BF / ZA (team brief section 3b)
    "sesame", "citrus", "grapes", "apples", "pears",
})

FERTILISERS = [
    "NPK Compound", "Urea", "Diammonium Phosphate (DAP)", "Single Super Phosphate",
    "Muriate of Potash", "Organic Fertilizer", "Bio-fertilizer", "Foliar Fertilizer", "None",
    "Ammonium Nitrate", "Calcium Ammonium Nitrate", "Ammonium Sulphate",
    "Triple Super Phosphate", "Potassium Sulphate",
]

_FUEL_CANON = {"gasoline": "petrol"}
FUELS = sorted({_FUEL_CANON.get(k, k) for k in list(_FARM_FUELS) + list(_FACILITY_FUELS)})

RAW_MATERIALS = sorted(set(REFINED_MATERIAL_HINTS) | set(RAW_MATERIAL_HINTS))

PACKAGING = list(PACKAGING_MATCH.keys())

VOCABULARIES: dict[str, list[str]] = {
    "crop": CROPS,
    "fertiliser": FERTILISERS,
    "fuel": FUELS,
    "raw_material": RAW_MATERIALS,
    "packaging": PACKAGING,
}

# Deterministic synonyms: normalised surface form -> label. Only unambiguous, well-known
# equivalences go here (trade names and local market terms included); anything doubtful is
# left to the model with a confirmation flag.
SYNONYMS: dict[str, dict[str, str]] = {
    "crop": {
        "corn": "maize", "mais": "maize", "maize grain": "maize",
        "paddy": "rice", "paddy rice": "rice", "riz": "rice",
        "mil": "millet", "pearl millet": "millet", "sorgho": "sorghum", "guinea corn": "sorghum",
        "peanut": "groundnut", "peanuts": "groundnut", "groundnuts": "groundnut",
        "arachide": "groundnut", "arachides": "groundnut",
        "black-eyed pea": "cowpea", "black eyed pea": "cowpea", "niebe": "cowpea",
        "manioc": "cassava", "manioc root": "cassava", "soya": "soybean", "soy": "soybean",
        "soybeans": "soybean", "soya bean": "soybean", "soya beans": "soybean",
        "palm": "oil palm", "palm fruit": "oil palm", "oil palm fruit": "oil palm",
        "cocoa beans": "cocoa", "cacao": "cocoa", "sweet potatoes": "sweet potato",
        "potatoes": "potato", "rapeseed": "canola", "oat": "oats", "lentil": "lentils",
        "pea": "field peas", "peas": "field peas", "linseed": "flax", "seed cotton": "cotton",
        "coton": "cotton", "sugar cane": "sugarcane", "sesame seed": "sesame", "benniseed": "sesame",
        "orange": "citrus", "oranges": "citrus", "lemon": "citrus", "grape": "grapes",
        "apple": "apples", "pear": "pears", "tomatoes": "tomato", "onions": "onion",
        "bananas": "banana", "plantains": "plantain", "yams": "yam", "carrots": "carrot",
        "faba bean": "fava bean", "broad bean": "fava bean",
    },
    "fertiliser": {
        "npk": "NPK Compound", "npk 15 15 15": "NPK Compound", "npk 15-15-15": "NPK Compound",
        "compound fertiliser": "NPK Compound", "compound fertilizer": "NPK Compound",
        "15-15-15": "NPK Compound", "20-10-10": "NPK Compound", "23-10-5": "NPK Compound",
        "urea 46%": "Urea", "urea 46-0-0": "Urea", "46-0-0": "Urea",
        "dap": "Diammonium Phosphate (DAP)", "diammonium phosphate": "Diammonium Phosphate (DAP)",
        "18-46-0": "Diammonium Phosphate (DAP)",
        "ssp": "Single Super Phosphate", "single superphosphate": "Single Super Phosphate",
        "tsp": "Triple Super Phosphate", "triple superphosphate": "Triple Super Phosphate",
        "mop": "Muriate of Potash", "potassium chloride": "Muriate of Potash", "kcl": "Muriate of Potash",
        "0-0-60": "Muriate of Potash",
        "sop": "Potassium Sulphate", "potassium sulfate": "Potassium Sulphate",
        "sulphate of ammonia": "Ammonium Sulphate", "sulfate of ammonia": "Ammonium Sulphate",
        "ammonium sulfate": "Ammonium Sulphate", "21-0-0": "Ammonium Sulphate",
        "can": "Calcium Ammonium Nitrate", "an": "Ammonium Nitrate",
        "manure": "Organic Fertilizer", "poultry manure": "Organic Fertilizer",
        "compost": "Organic Fertilizer", "organic": "Organic Fertilizer",
        "biofertilizer": "Bio-fertilizer", "bio fertilizer": "Bio-fertilizer",
        "foliar": "Foliar Fertilizer", "none": "None", "no fertiliser": "None", "no fertilizer": "None",
    },
    "fuel": {
        # West African retail terms: AGO = automotive gas oil (diesel), PMS = premium motor
        # spirit (petrol), DPK = dual purpose kerosene (Nigeria NNPC product codes).
        "ago": "diesel", "gas oil": "diesel", "gasoil": "diesel", "automotive gas oil": "diesel",
        "diesel fuel": "diesel", "gazole": "diesel",
        "pms": "petrol", "premium motor spirit": "petrol", "gasoline": "petrol", "petrol gasoline": "petrol",
        "essence": "petrol",
        "dpk": "kerosene", "paraffin": "kerosene", "dual purpose kerosene": "kerosene", "petrole": "kerosene",
        "liquefied petroleum gas": "lpg", "liquefied petroleum gas lpg": "lpg", "cooking gas": "lpg",
        "butane": "lpg", "propane": "lpg", "gas cylinder": "lpg",
        "b100": "biodiesel", "fame": "biodiesel",
    },
    "raw_material": {
        "corn": "maize", "manioc": "cassava", "peanuts": "peanut", "groundnuts": "groundnut",
        "soya": "soy", "soybeans": "soy", "paddy rice": "paddy", "cocoa beans": "cocoa",
        "palm fruit": "palm", "fresh fruit bunches": "palm", "ffb": "palm",
        "sugar cane": "sugarcane", "tomatoes": "tomato", "onions": "onion",
    },
    "packaging": {
        "plastic bag": "PlasticBag", "plastic bags": "PlasticBag", "polythene bag": "PlasticBag",
        "polythene": "PlasticBag", "nylon bag": "PlasticBag", "sachet": "PlasticBag",
        "pp": "Polypropylene", "pp bag": "Polypropylene", "pp woven sack": "Polypropylene",
        "woven polypropylene sack": "Polypropylene", "woven sack": "Polypropylene",
        "paper bag": "PaperBag", "paper sack": "PaperBag", "kraft paper": "PaperBag",
        "jute sack": "Jute", "jute bag": "Jute", "hessian": "Jute", "burlap": "Jute",
        "carton": "Cardboard", "cartons": "Cardboard", "corrugated box": "Cardboard",
        "cardboard box": "Cardboard", "tin": "Metal", "tin can": "Metal", "can": "Metal",
        "steel can": "Metal", "aluminium can": "Metal", "glass bottle": "Glass", "glass jar": "Glass",
        "tetra pak": "Composite", "laminated pouch": "Composite",
        "multilayer": "Composite",
    },
}
