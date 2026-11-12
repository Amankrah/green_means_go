#!/usr/bin/env python3
"""
crop_defaults.py: cited per-crop defaults used when a farmer leaves an amount blank.

  * seed / planting-material rate (kg/ha) and the background seed dataset;
  * seasonal crop water need (mm) and irrigation application efficiency, to estimate
    irrigation water (m3) when the farm is irrigated but the volume was not measured.

The crop is identified from the food name (then variety / crop_type). When the crop is not
recognised, `food.category` selects a category default, so the category always matters.
Every value returned carries its source and an `estimated` flag.
"""
from __future__ import annotations

SEED_SOURCE = ("FAO (2010) Seeds in emergencies: a technical handbook, FAO Plant Production and "
               "Protection Paper 202, Annex 1 seed rates (midpoint of the range shown)")

# crop key -> (seed kg/ha, range, background dataset to match)
SEED_RATES = {
    "maize": (25.0, "20-30", "market for maize seed, for sowing"),
    "rice": (60.0, "40-80 transplanted to direct-seeded", "market for rice seed, for sowing"),
    "wheat": (125.0, "100-150", "market for wheat seed, for sowing"),
    "sorghum": (10.0, "8-12", "market for barley seed, for sowing"),     # cereal seed proxy
    "millet": (6.0, "4-8", "market for barley seed, for sowing"),        # cereal seed proxy
    "groundnut": (80.0, "60-100 shelled", "market for peanut seed, for sowing"),
    "cowpea": (25.0, "20-30", "market for pea seed, for sowing"),        # pulse seed proxy
    "bean": (80.0, "60-100", "market for navy bean seed, for sowing"),
    "soybean": (60.0, "50-80", "market for soybean seed, for sowing"),
    "sesame": (4.0, "3-5", "market for linseed seed, for sowing"),       # small oilseed proxy
    "sunflower": (6.0, "5-8", "market for sunflower seed, for sowing"),
    "cotton": (25.0, "20-30", "market for cottonseed, for sowing"),
    "tomato": (0.3, "0.2-0.5 (nursery)", "market for carrot seed, for sowing"),  # vegetable seed proxy
    "pepper": (0.6, "0.5-0.75 (nursery)", "market for carrot seed, for sowing"),
    "eggplant": (0.4, "0.3-0.5 (nursery)", "market for carrot seed, for sowing"),
    "cucumber": (2.5, "2-3", "market for carrot seed, for sowing"),
    "onion": (6.0, "4-8", "market for carrot seed, for sowing"),
    "cabbage": (0.4, "0.3-0.5 (nursery)", "market for carrot seed, for sowing"),
    "carrot": (4.0, "3-5", "market for carrot seed, for sowing"),
}

# Crops propagated vegetatively or established as perennials: no seed dataset. Planting
# material of perennials belongs to the establishment phase (amortised in the field model).
VEGETATIVE = {"cassava", "yam", "plantain", "banana", "cocoa", "oil palm", "palm", "sugarcane",
              "cocoyam", "taro", "sweet potato", "potato", "pineapple", "citrus", "mango",
              "cashew", "coffee", "rubber", "shea"}

# food.category fallback when the crop is not recognised.
CATEGORY_SEED = {
    "Cereals": "maize", "Legumes": "cowpea", "Vegetables": "tomato", "Nuts": "groundnut",
}

WATER_NEED_SOURCE = ("Brouwer C., Heibloem M. (1986) Irrigation Water Management Training Manual "
                     "No. 3: Irrigation Water Needs, FAO, Table 13 approximate seasonal crop water "
                     "needs (midpoint of the range shown)")
# crop key -> (mm per growing season, range)
CROP_WATER_NEED_MM = {
    "maize": (650.0, "500-800"), "rice": (575.0, "450-700"), "wheat": (550.0, "450-650"),
    "sorghum": (550.0, "450-650"), "millet": (550.0, "450-650"),
    "groundnut": (600.0, "500-700"), "bean": (400.0, "300-500"), "cowpea": (400.0, "300-500"),
    "soybean": (575.0, "450-700"), "sunflower": (800.0, "600-1000"), "cotton": (1000.0, "700-1300"),
    "tomato": (600.0, "400-800"), "pepper": (750.0, "600-900"), "eggplant": (600.0, "tomato proxy"),
    "cucumber": (500.0, "melon proxy 400-600"), "onion": (450.0, "350-550"),
    "cabbage": (425.0, "350-500"), "potato": (600.0, "500-700"),
    "banana": (1700.0, "1200-2200"), "plantain": (1700.0, "banana proxy"),
    "citrus": (1050.0, "900-1200"), "sugarcane": (2000.0, "1500-2500"),
}
CATEGORY_WATER = {
    "Cereals": "maize", "Legumes": "bean", "Vegetables": "tomato", "Fruits": "citrus",
    "Roots": "potato", "Oils": "groundnut", "Nuts": "groundnut",
}

EFFICIENCY_SOURCE = ("Brouwer C., Prins K., Heibloem M. (1989) Irrigation Water Management Training "
                     "Manual No. 4: Irrigation Scheduling, FAO, field application efficiency "
                     "(surface 60%, sprinkler 75%, drip 90%)")
APPLICATION_EFFICIENCY = {"surface": 0.60, "sprinkler": 0.75, "drip": 0.90}

# Share of the crop water need supplied by irrigation. Dry-season / year-round irrigated
# crops get all of it; wet-season irrigation is supplementary. GMG screening assumption,
# flagged as estimated: a measured volume always replaces it.
IRRIGATION_SHARE = {"DrySeason": 1.0, "YearRound": 1.0, "WetSeason": 0.5}
IRRIGATION_SHARE_NOTE = ("GMG screening assumption: full crop water need irrigated in the dry "
                         "season / year round, half in the wet season (rain supplies the rest)")

_ALIASES = [
    ("oil palm", "oil palm"), ("palm", "palm"), ("maize", "maize"), ("corn", "maize"),
    ("rice", "rice"), ("paddy", "rice"), ("wheat", "wheat"), ("sorghum", "sorghum"),
    ("millet", "millet"), ("groundnut", "groundnut"), ("peanut", "groundnut"),
    ("cowpea", "cowpea"), ("soy", "soybean"), ("bean", "bean"), ("sesame", "sesame"),
    ("sunflower", "sunflower"), ("cotton", "cotton"), ("tomato", "tomato"),
    ("chilli", "pepper"), ("chili", "pepper"), ("pepper", "pepper"), ("eggplant", "eggplant"),
    ("aubergine", "eggplant"), ("garden egg", "eggplant"), ("cucumber", "cucumber"),
    ("onion", "onion"), ("cabbage", "cabbage"), ("carrot", "carrot"), ("cassava", "cassava"),
    ("yam", "yam"), ("plantain", "plantain"), ("banana", "banana"), ("cocoa", "cocoa"),
    ("sugarcane", "sugarcane"), ("sweet potato", "sweet potato"), ("potato", "potato"),
    ("citrus", "citrus"), ("orange", "citrus"), ("mango", "mango"), ("cashew", "cashew"),
]


def crop_key(food: dict) -> str | None:
    text = " ".join(str(food.get(k) or "") for k in ("name", "crop_type", "variety")).lower()
    for kw, key in _ALIASES:
        if kw in text:
            return key
    return None


def seed_default(food: dict) -> dict | None:
    """Seed rate for a food: user value, else crop default, else category default.
    Returns {kg_per_ha, match_as, estimated, source, crop} or None (vegetative / unknown)."""
    key = crop_key(food)
    user = food.get("seed_rate_kg_per_ha")
    basis_key = key if key in SEED_RATES else None
    via_category = False
    if basis_key is None and key not in VEGETATIVE:
        basis_key = CATEGORY_SEED.get(food.get("category") or "")
        via_category = basis_key is not None
    if user is not None:
        if user <= 0:
            return None
        ds = SEED_RATES[basis_key][2] if basis_key else None
        return {"kg_per_ha": float(user), "match_as": ds or f"{food.get('name', 'crop')} seed, for sowing",
                "estimated": False, "source": "farmer", "crop": key}
    if basis_key is None:
        return None
    rate, rng, ds = SEED_RATES[basis_key]
    src = f"{SEED_SOURCE}: {basis_key} {rng} kg/ha"
    if via_category:
        src += f" (crop not recognised; category '{food.get('category')}' default)"
    return {"kg_per_ha": rate, "match_as": ds, "estimated": True, "source": src, "crop": key or basis_key}


def _system_key(irrigation_system: str | None) -> str | None:
    s = (irrigation_system or "").lower()
    if not s or "none" in s or "rainfed" in s:
        return None
    if "drip" in s:
        return "drip"
    if "sprinkler" in s or "pivot" in s:
        return "sprinkler"
    return "surface"     # flood, furrow, basin, bucket/manual


def irrigation_default_m3(food: dict, irrigation_system: str | None) -> dict | None:
    """Estimated irrigation water (m3/season) for one food on its own area. None when the
    system is rainfed or the area is unknown."""
    sys_key = _system_key(irrigation_system)
    area = food.get("area_allocated") or 0.0
    if not sys_key or area <= 0:
        return None
    key = crop_key(food)
    basis = key if key in CROP_WATER_NEED_MM else CATEGORY_WATER.get(food.get("category") or "", "maize")
    mm, rng = CROP_WATER_NEED_MM[basis]
    share = IRRIGATION_SHARE.get(food.get("seasonal_factor") or "", 0.5)
    eff = APPLICATION_EFFICIENCY[sys_key]
    m3 = mm * 10.0 * area * share / eff          # 1 mm over 1 ha = 10 m3
    return {"m3": m3, "system": sys_key, "estimated": True,
            "source": (f"{WATER_NEED_SOURCE}: {basis} {rng} mm; {EFFICIENCY_SOURCE}; "
                       f"{IRRIGATION_SHARE_NOTE} (share {share:g})")}


def irrigation_system_key(irrigation_system: str | None) -> str | None:
    return _system_key(irrigation_system)
