#!/usr/bin/env python3
"""
land_use_change.py: direct land-use change (dLUC) carbon for a crop on recently converted
land, IPCC 2019 Refinement Vol 4 Tier 1 stock-difference method with 20-year linear
amortisation (PAS 2050:2011 clause 5.6 and PAS 2050-1:2012; IPCC 2019 Vol 4 Ch 2 Eq 2.25
uses the same 20-year default transition period D).

dLUC is applied ONLY when the user declares a conversion within the last 20 years:

    foods[i].land_use_change = {"previous_land_use": "forest" | "grassland" |
                                "annual cropland" | "perennial cropland",
                                "years_since_conversion": <int>}

(also accepted at assessment level as `land_use_change`). Without it the default is "no
conversion within 20 years" and no dLUC is added; that assumption is stated in the notes.

Stock change (t C/ha) = [biomass + dead organic matter + SOC] before - [biomass + SOC] after
    SOC   = SOC_REF(climate, soil) x F_LU x F_MG x F_I         (Vol 4 Ch 2 Eq 2.25)
    forest biomass = AGB x (1 + R) x CF                         (Vol 4 Ch 4 Tables 4.7/4.4/4.3)
Annual emission (kg CO2/ha/yr) = max(0, dC) x 44/12 x 1000 / 20. Carbon gains are not
credited (conservative screening choice). The SOC loss also mineralises N (IPCC 2019 Eq
11.8, F_SOM = dC_soil / R with C:N ratio R = 15 for land-use change), which adds N2O at the
EF1 for other N inputs.

Factors: the region file engine/recommend/reference/ipcc_stock_change_factors_<cc>.json is
used when it exists (Ghana today). Other regions fall back to the IPCC defaults for their
climate zone below, flagged as such. Built-in defaults were transcribed from FAO EX-ACT
v9.4.2 (data/recommendations/Tier1/EX-ACT_V9.4.2.xlsb, sheet 'IPCC'), which compiles the
IPCC 2019 Refinement tables cited per value.
"""
from __future__ import annotations

import json
from pathlib import Path

_REF_DIR = Path(__file__).resolve().parent / "recommend" / "reference"
AMORTISATION_YEARS = 20          # PAS 2050:2011 5.6; IPCC 2019 Vol 4 Ch 2 default D = 20 yr
C_TO_CO2 = 44.0 / 12.0
CN_RATIO_LUC = 15.0              # IPCC 2019 Vol 4 Ch 11 Eq 11.8: R = 15 for land-use change
CARBON_FRACTION_TROPICAL = 0.47  # IPCC 2006 Vol 4 Ch 4 Table 4.3 (tropical/subtropical, all)

EXACT = "FAO EX-ACT v9.4.2 'IPCC' sheet"

# SOC_REF, t C/ha 0-30 cm, IPCC 2019 Refinement Vol 4 Ch 2 Table 2.3 (updated)
# (EX-ACT 'IPCC' sheet rows 39-48). HAC high-activity clay, LAC low-activity clay,
# SAN sandy, VOL volcanic.
SOC_REF = {
    "tropical wet":        {"HAC": 60.0, "LAC": 52.0, "SAN": 46.0, "VOL": 77.0},
    "tropical moist":      {"HAC": 40.0, "LAC": 38.0, "SAN": 27.0, "VOL": 70.0},
    "tropical dry":        {"HAC": 21.0, "LAC": 19.0, "SAN": 9.0, "VOL": 50.0},
    "tropical montane":    {"HAC": 51.0, "LAC": 44.0, "SAN": 52.0, "VOL": 96.0},
    "warm temperate moist": {"HAC": 64.0, "LAC": 55.0, "SAN": 36.0, "VOL": 138.0},
    "warm temperate dry":  {"HAC": 24.0, "LAC": 19.0, "SAN": 10.0, "VOL": 84.0},
    "cool temperate moist": {"HAC": 81.0, "LAC": 76.0, "SAN": 51.0, "VOL": 136.0},
    "cool temperate dry":  {"HAC": 43.0, "LAC": 33.0, "SAN": 13.0, "VOL": 20.0},
}
SRC_SOC_REF = f"IPCC 2019 Refinement Vol 4 Ch 2 Table 2.3 (updated), via {EXACT}"

# F_LU, IPCC 2019 Refinement Vol 4 Ch 5 Table 5.5 (updated) (EX-ACT rows 58-67).
FLU = {
    "tropical wet":        {"long_term_cultivated": 0.83, "perennial": 1.01},
    "tropical moist":      {"long_term_cultivated": 0.83, "perennial": 1.01},
    "tropical dry":        {"long_term_cultivated": 0.92, "perennial": 1.01},
    "tropical montane":    {"long_term_cultivated": 0.64, "perennial": 1.00},
    "warm temperate moist": {"long_term_cultivated": 0.69, "perennial": 0.72},
    "warm temperate dry":  {"long_term_cultivated": 0.76, "perennial": 0.72},
    "cool temperate moist": {"long_term_cultivated": 0.70, "perennial": 0.72},
    "cool temperate dry":  {"long_term_cultivated": 0.77, "perennial": 0.72},
}
SRC_FLU = f"IPCC 2019 Refinement Vol 4 Ch 5 Table 5.5 (updated), via {EXACT}"

# Natural forest by climate: above-ground biomass AGB (t d.m./ha), Africa rows of IPCC 2019
# Vol 4 Ch 4 Table 4.7/4.12 (updated); root:shoot R from Table 4.4 (updated); litter and
# dead wood (t C/ha) from Vol 4 Ch 2 Table 2.2 (updated). All via EX-ACT rows 594, 621, 642-644.
FOREST = {
    "tropical wet":   {"type": "Tropical rainforest", "agb": 404.2, "r": 0.532, "litter": 4.8, "deadwood": 14.8},
    "tropical moist": {"type": "Tropical moist deciduous forest", "agb": 236.6, "r": 0.232, "litter": 5.9, "deadwood": 8.0},
    "tropical dry":   {"type": "Tropical dry forest", "agb": 69.6, "r": 0.332, "litter": 2.4, "deadwood": 9.0},
}
SRC_FOREST = (f"IPCC 2019 Refinement Vol 4 Ch 4 Table 4.7 (AGB, Africa), Table 4.4 (R), "
              f"Ch 2 Table 2.2 (litter, dead wood), via {EXACT}; CF 0.47 IPCC 2006 Vol 4 Table 4.3")

# Time-averaged biomass carbon (t C/ha) of the land use after conversion, or of a non-forest
# land use before it. Tropical rows of EX-ACT 'IPCC' sheet rows 1588-1636: annual cropland
# 4.7 (IPCC 2019 Vol 4 Ch 5 Table 5.9 updated); grassland 7.567 wet/moist, 4.089 dry (IPCC
# 2006 Vol 4 Ch 6 Table 6.4); shaded perennial 24.0 (Ch 5 Table 5.1 updated); oil palm 30.0
# (Ch 5 Table 5.3 updated); rubber 40.1 (Ch 5 Table 5.3 updated, tropical rows, EX-ACT
# 'IPCC' sheet column "Rubber", rows 1585-1648).
BIOMASS_C = {
    "annual cropland": {"tropical wet": 4.7, "tropical moist": 4.7, "tropical dry": 4.7, "default": 4.7},
    "grassland": {"tropical wet": 7.567, "tropical moist": 7.567, "tropical dry": 4.089, "default": 6.345},
    "Shaded Perennial": {"default": 24.0},
    "Oil palm": {"default": 30.0},
    "Rubber": {"tropical wet": 40.1, "tropical moist": 40.1, "tropical dry": 40.1,
               "tropical montane": 40.1},
}
# Perennials whose engine/perennials.py entry has biomass_class None but which have their own
# Table 5.3 row. Other perennials (cashew, coffee, coconut, citrus, mango, plantain/banana,
# farmer-declared) have no tropical Table 5.1/5.3 row (orchard/olive/vine rows are temperate
# only in EX-ACT), so their biomass after conversion is not credited (see _after_biomass).
BIOMASS_CLASS_BY_CROP = {"rubber": "Rubber"}


def _after_biomass(p: dict, clim: str) -> tuple[float, str | None]:
    """(time-averaged biomass C of the perennial, t C/ha; disclosure or None)."""
    cls = p.get("biomass_class") or BIOMASS_CLASS_BY_CROP.get(str(p.get("crop") or ""))
    table = BIOMASS_C.get(cls) if cls else None
    if table:
        val = table.get(clim, table.get("default"))
        if val is not None:
            return val, None
    return 0.0, (f"no IPCC 2019 Vol 4 Ch 5 Table 5.1/5.3 biomass value for perennial "
                 f"'{p.get('crop')}' in a {clim} climate: its biomass after conversion is not "
                 "credited (conservative: the full pre-conversion biomass loss is booked)")
SRC_BIOMASS = (f"IPCC 2019 Refinement Vol 4 Ch 5 Tables 5.1, 5.3, 5.9 (updated) and IPCC 2006 "
               f"Vol 4 Ch 6 Table 6.4, via {EXACT}")

# Region -> forest ecological zone override (FAO Global Ecological Zones 2010: the cocoa and
# oil-palm belts of southern Ghana and Nigeria are tropical moist deciduous forest). Country-
# level FALLBACK only: the admin-region zone from regions.forest_zone_for() wins when known.
FOREST_ZONE_OVERRIDE = {"GH": "tropical moist", "NG": "tropical moist"}


def forest_zone(region, assessment: dict, clim: str) -> tuple[str, str]:
    """(forest zone key in FOREST, basis). Order: admin region (regions.forest_zone_for,
    CONTRACT §2), country override, climate zone."""
    code = str(getattr(region, "code", "") or "")
    admin = ((assessment.get("study_meta") or {}).get("admin_region")) or None
    try:
        try:
            from .regions import forest_zone_for
        except ImportError:
            from regions import forest_zone_for
    except ImportError:
        forest_zone_for = None
    if forest_zone_for is not None:
        try:
            z = forest_zone_for(code, admin)
        except Exception:
            z = None
        if z in FOREST:
            return z, f"admin region '{admin}'" if admin else "region default"
    if code in FOREST_ZONE_OVERRIDE:
        return FOREST_ZONE_OVERRIDE[code], f"country-level zone for {code} (admin region not resolved)"
    return clim, "climate zone"


def ipcc_climate(region) -> tuple[str, bool]:
    """(IPCC climate key, is_exact). Maps the registry's free-text climate_zone to a key of
    the tables above; is_exact=False when the mapping is a fallback."""
    z = (getattr(region, "climate_zone", "") or "").lower()
    if "tropical" in z or "trop" in z:
        if "montane" in z:
            return "tropical montane", True
        if "wet/dry" in z or ("wet" in z and "dry" in z):
            return "tropical moist", False
        if "wet" in z:
            return "tropical wet", True
        if "moist" in z or "humid" in z:
            return "tropical moist", True
        if "dry" in z:
            return "tropical dry", True
        return "tropical moist", False
    if "temperate" in z:
        warm = "warm" in z
        dry = "dry" in z
        key = f"{'warm' if warm else 'cool'} temperate {'dry' if dry else 'moist'}"
        return key, ("moist" in z or dry)
    return "tropical moist", False


def load_stock_change_factors(region) -> tuple[dict, str, bool]:
    """Region-aware loader. Returns (factors, source, region_specific).

    factors keys: FLU_long_term_cultivated, FLU_perennial_tree_crop (plus FMG_/FI_ keys when
    the region file has them). Uses engine/recommend/reference/
    ipcc_stock_change_factors_<cc>.json when present, else IPCC defaults by climate zone."""
    code = str(getattr(region, "code", "") or "").lower()
    path = _REF_DIR / f"ipcc_stock_change_factors_{code}.json"
    if code and path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        src = (data.get("provenance") or {}).get("underlying") or data.get("title") or path.name
        return dict(data.get("factors") or {}), f"{path.name}: {src}", True
    clim, _ = ipcc_climate(region)
    f = FLU.get(clim, FLU["tropical moist"])
    return ({"FLU_long_term_cultivated": f["long_term_cultivated"],
             "FLU_perennial_tree_crop": f["perennial"],
             "FMG_full_tillage": 1.0, "FI_medium_input": 1.0},
            f"{SRC_FLU} ({clim}; IPCC default, no region file)", False)


def _soil_class(assessment: dict) -> str:
    sm = ((assessment.get("management_practices") or {}).get("soil_management")) or {}
    st = str(sm.get("soil_type") or "").lower()
    if "sand" in st and "loam" not in st:
        return "SAN"
    if "volcan" in st:
        return "VOL"
    return "LAC"   # West African upland soils are dominated by low-activity clays


def _declared_luc(assessment: dict, food: dict) -> dict | None:
    luc = food.get("land_use_change") or assessment.get("land_use_change")
    return luc if isinstance(luc, dict) and luc.get("previous_land_use") else None


def dluc_flows(assessment: dict, region, ef1_other: float, frac_leach: float,
               ef5: float = 0.011) -> tuple[list[dict], list[str]]:
    """On-farm flows (CO2 from stock change, N2O from F_SOM) for declared recent land
    conversion. Returns ([], [note]) when no conversion within 20 years is declared."""
    try:
        from . import perennials as _per
    except ImportError:
        import perennials as _per
    perennial_of = getattr(_per, "perennial_for_food", None) or (
        lambda f: _per.perennial_for(f.get("name")))
    foods = assessment.get("foods") or []
    flows: list[dict] = []
    notes: list[str] = []
    declared_any = False
    for food in foods:
        luc = _declared_luc(assessment, food)
        if not luc:
            continue
        declared_any = True
        name = food.get("name", "crop")
        try:
            years = float(luc.get("years_since_conversion"))
        except (TypeError, ValueError):
            notes.append(f"validation warning: land_use_change for {name} has no valid "
                         "years_since_conversion; dLUC not applied")
            continue
        if years >= AMORTISATION_YEARS or years < 0:
            notes.append(f"{name}: land converted {years:g} years ago, outside the "
                         f"{AMORTISATION_YEARS}-year amortisation window; no dLUC")
            continue
        area = float(food.get("area_allocated") or 0.0)
        if area <= 0:
            notes.append(f"validation warning: land_use_change for {name} needs area_allocated")
            continue
        clim, exact = ipcc_climate(region)
        factors, fsrc, region_specific = load_stock_change_factors(region)
        soil = _soil_class(assessment)
        soc_ref = SOC_REF.get(clim, SOC_REF["tropical moist"])[soil]
        prev = str(luc.get("previous_land_use")).strip().lower()
        p = perennial_of(food)

        # --- before ---
        dom_before = 0.0
        if "forest" in prev:
            fz, fz_basis = forest_zone(region, assessment, clim)
            forest = FOREST.get(fz) or FOREST["tropical moist"]
            bio_before = forest["agb"] * (1.0 + forest["r"]) * CARBON_FRACTION_TROPICAL
            dom_before = forest["litter"] + forest["deadwood"]
            flu_before = 1.0
            before_label = f"{forest['type']} (zone from {fz_basis}; {SRC_FOREST})"
        elif "grass" in prev or "savanna" in prev or "pasture" in prev:
            b = BIOMASS_C["grassland"]
            bio_before = b.get(clim, b["default"])
            flu_before = 1.0
            before_label = "grassland"
        elif "perennial" in prev or "tree crop" in prev or "plantation" in prev:
            bio_before = BIOMASS_C["Shaded Perennial"]["default"]
            flu_before = factors.get("FLU_perennial_tree_crop", 1.0)
            before_label = "perennial cropland"
        elif "crop" in prev or "annual" in prev or "fallow" in prev:
            b = BIOMASS_C["annual cropland"]
            bio_before = b.get(clim, b["default"])
            flu_before = factors.get("FLU_long_term_cultivated", 0.83)
            before_label = "annual cropland"
        else:
            notes.append(f"validation warning: previous_land_use '{prev}' for {name} not "
                         "recognised (forest, grassland, annual cropland, perennial cropland); "
                         "dLUC not applied")
            continue

        # --- after ---
        if p is not None:
            bio_after, bio_note = _after_biomass(p, clim)
            if bio_note:
                notes.append(f"{name}: {bio_note}")
            flu_after = factors.get("FLU_perennial_tree_crop", 1.0)
        else:
            b = BIOMASS_C["annual cropland"]
            bio_after = b.get(clim, b["default"])
            flu_after = factors.get("FLU_long_term_cultivated", 0.83)

        soc_before = soc_ref * flu_before
        soc_after = soc_ref * flu_after
        d_bio = (bio_before + dom_before) - bio_after
        d_soc = soc_before - soc_after
        d_total = d_bio + d_soc
        if d_total <= 0:
            notes.append(f"{name}: conversion from {before_label} gains carbon "
                         f"({-d_total:.1f} t C/ha); gains are not credited (conservative)")
            continue
        co2_kg = d_total * C_TO_CO2 * 1000.0 * area / AMORTISATION_YEARS
        flows.append({"substance": "CO2_luc", "quantity": co2_kg, "unit": "kg",
                      "origin": "land_use_change"})
        n2o_kg = 0.0
        if d_soc > 0:
            f_som = d_soc * 1000.0 * area / AMORTISATION_YEARS / CN_RATIO_LUC
            n2o_kg = f_som * (ef1_other + frac_leach * ef5) * 44.0 / 28.0
            flows.append({"substance": "N2O", "quantity": n2o_kg, "unit": "kg",
                          "origin": "land_use_change"})
        flag = "" if (exact and region_specific) else " [IPCC default factors for the climate zone, not region-specific]"
        notes.append(
            f"dLUC for {name}: {before_label} converted {years:g} years ago -> stock loss "
            f"{d_total:.1f} t C/ha (biomass+DOM {d_bio:.1f}, SOC {d_soc:.1f}; SOC_REF "
            f"{soc_ref:g} t C/ha {soil}, {clim}) amortised over {AMORTISATION_YEARS} years = "
            f"{co2_kg/1000:.2f} t CO2/yr on {area:g} ha"
            + (f", plus {n2o_kg:.2f} kg N2O from mineralised SOC N (IPCC 2019 Eq 11.8)" if n2o_kg else "")
            + f". Sources: {SRC_SOC_REF}; {fsrc}; {SRC_BIOMASS}; PAS 2050:2011 5.6.{flag}")
    if not declared_any and foods:
        notes.append("no land conversion within the last 20 years assumed (default): dLUC = 0. "
                     "Declare foods[].land_use_change = {previous_land_use, "
                     "years_since_conversion} to include it. When the land-use history is "
                     "unknown, PAS 2050-1:2012 (and PAS 2050:2011 5.6) prescribe a statistical "
                     "country/crop dLUC estimate; that statistical dLUC was NOT applied")
    return flows, notes
