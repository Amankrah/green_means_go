#!/usr/bin/env python3
"""
conversion_ratios.py: default raw-material requirement per tonne of processed product, used
when a processor leaves a product's raw-material input blank. Without it the cradle part of
cradle-to-gate (usually the dominant burden) silently disappeared.

kg raw per tonne output = 1000 / extraction rate. Each ratio cites its source; values are
national / industry averages and must be replaced by the mill's own figure when known.
The product_type selects the ratio; for product_type "Other" the facility_type does.

Co-products named here (palm kernels, cocoa butter vs powder, bran) are reported so the
user can declare them as products for allocation; they are not invented as outputs.
"""
from __future__ import annotations

FAO_TCF = ("FAO (2000) Technical Conversion Factors for Agricultural Commodities, FAO Statistics "
           "Division, Rome (extraction rates by commodity and country)")

# product_type -> spec
RATIOS = {
    "PalmOil": {
        "raw_material": "Oil palm fresh fruit bunches (FFB)",
        "extraction_rate": 0.20,
        "source": ("Oil extraction rate (OER) CPO/FFB 19.7 to 20.4% in 2019-2023, MPOB Malaysian Oil "
                   "Palm Statistics; FAO (2000) TCF palm oil from bunches 0.17 to 0.22. Small-scale "
                   "West African mills are often lower (12 to 16%, Poku 2002 FAO Agric. Services "
                   "Bulletin 148): enter the mill's own OER"),
        "coproducts": "palm kernels about 5% of FFB (kernel extraction rate, MPOB); fibre and shell "
                      "(boiler fuel); empty fruit bunches",
    },
    "CocoaPowder": {
        "raw_material": "Cocoa beans (dried, fermented)",
        "extraction_rate": 0.80,
        "source": ("Cocoa liquor (mass) about 80% of dried beans after shell removal and roasting "
                   "losses (shell 12 to 15%); FAO (2000) TCF cocoa paste from beans 0.80. Pressing "
                   "splits liquor into butter and cake (powder) of roughly equal mass"),
        "coproducts": "cocoa butter (declare it as a second product so the beans are shared)",
    },
    "CocoaButter": {
        "raw_material": "Cocoa beans (dried, fermented)",
        "extraction_rate": 0.80,
        "source": ("Cocoa liquor about 80% of dried beans (FAO 2000 TCF cocoa paste 0.80); butter "
                   "and cake are co-products of pressing"),
        "coproducts": "cocoa cake / powder (declare it as a second product so the beans are shared)",
    },
    "FlourMaize": {
        "raw_material": "Maize grain",
        "extraction_rate": 0.80,
        "source": ("FAO (1992) Maize in human nutrition, FAO Food and Nutrition Series 25, ch. 4: "
                   "dry-milled degermed products 60 to 70%, whole meal up to 95%; 0.80 is the "
                   "midpoint used as a screening default (FAO 2000 TCF maize flour 0.8 to 0.9)"),
        "coproducts": "bran and germ (feed)",
    },
    "FlourWheat": {
        "raw_material": "Wheat grain",
        "extraction_rate": 0.75,
        "source": f"{FAO_TCF}: wheat flour 0.72 to 0.80 of grain",
        "coproducts": "wheat bran (feed)",
    },
    "RiceProcessed": {
        "raw_material": "Paddy rice",
        "extraction_rate": 0.67,
        "source": f"{FAO_TCF}: milled rice 0.667 of paddy (also the FAOSTAT paddy-to-milled factor)",
        "coproducts": "rice husk (fuel), rice bran (feed)",
    },
    "FlourCassava": {
        "raw_material": "Fresh cassava roots",
        "extraction_rate": 0.25,
        "source": (f"{FAO_TCF}: cassava flour / gari about 0.25 to 0.30 of fresh roots (fresh roots "
                   "are about 60 to 70% water)"),
        "coproducts": "peels (feed or waste)",
    },
}

# facility_type -> product_type used when the product is declared as "Other"
FACILITY_DEFAULT_PRODUCT = {
    "PalmOilMill": "PalmOil",
    "CocoaProcessing": "CocoaPowder",
    "RiceProcessing": "RiceProcessed",
    "CassivaProcessing": "FlourCassava",
}


def default_raw_input(product: dict, facility_type: str | None) -> dict | None:
    """Default raw-material input for one product: {material_name, kg_per_tonne, source,
    coproducts, product_type_used} or None when no default exists."""
    ptype = product.get("product_type") or "Other"
    if ptype == "Other" or ptype not in RATIOS:
        ptype = FACILITY_DEFAULT_PRODUCT.get(facility_type or "", ptype)
    spec = RATIOS.get(ptype)
    if not spec:
        return None
    return {"material_name": spec["raw_material"],
            "kg_per_tonne": 1000.0 / spec["extraction_rate"],
            "extraction_rate": spec["extraction_rate"],
            "source": spec["source"], "coproducts": spec["coproducts"],
            "product_type_used": ptype}
