#!/usr/bin/env python3
"""
soil_carbon.py: soil organic carbon (SOC) stock change from cropland MANAGEMENT (tillage and
carbon input), IPCC 2019 Refinement Vol 4 Tier 1, reported SEPARATELY from the headline
climate result (ISO 14067:2018 asks for GHG emissions and removals from soil-carbon change
to be documented separately in the CFP study report; CONTRACT key `soc_management`). It is
never merged into the inventory here.

    SOC = SOC_REF x F_LU x F_MG x F_I                                (Vol 4 Ch 2 Eq 2.25)
    dSOC (t C/ha/yr) = (SOC_current - SOC_previous) / D,  D = 20 yr  (Vol 4 Ch 2 Eq 2.25)
    CO2 (kg/yr) = -dSOC x 44/12 x 1000 x area     (positive = emission, negative = removal)

Booked only while the practice change is inside the 20-year transition, i.e. when
`soil_management.practices_adopted_years_ago` is given and < 20 (CONTRACT). Previous
practice is the IPCC reference management: full tillage, medium input (Table 5.5 factor
1.0 for both), unless the caller states otherwise.

Current practice (CONTRACT keyword vocabulary, case-insensitive):
  F_MG  "no-till"/"no till"/"zero till" -> no tillage; "minimum"/"reduced" -> reduced
        tillage; otherwise full tillage.
  F_I   follows the input-level DEFINITIONS of Table 5.5 (IPCC 2006 Vol 4 Ch 5, retained in the
        2019 Refinement); see INPUT_DEFINITIONS and input_class(). Where the payload cannot
        separate two classes (partial residue removal, manure without another high-input
        practice, compost / mulch of unknown origin) the engine applies a disclosed rule and
        reports the alternative class as a range (`value_range`); it never interpolates
        between classes (not an IPCC method).

Factors: IPCC 2019 Refinement Vol 4 Ch 5 Table 5.5 (updated), transcribed from FAO EX-ACT
v9.4.2 (data/recommendations/Tier1/EX-ACT_V9.4.2.xlsb, sheet 'IPCC', rows 59-68; the
tropical-montane row carries IPCC 2006 values, flagged red in EX-ACT). SOC_REF and the
climate / soil-class mapping are reused from engine/land_use_change.py (Table 2.3).
Perennial tree crops are not modelled (Table 5.5 F_MG / F_I describe annual-crop tillage and
residue regimes); disclosed.
"""
from __future__ import annotations

try:
    from . import land_use_change as _luc
except ImportError:  # script use
    import land_use_change as _luc  # type: ignore

TRANSITION_YEARS = 20            # IPCC 2019 Vol 4 Ch 2 Eq 2.25, default D = 20 yr
C_TO_CO2 = 44.0 / 12.0
# Engine assumption (no IPCC threshold exists): residues count as "removed" when the majority
# is removed or burnt (fraction_removed + fraction_burnt > 0.5). Any partial removal reports
# the other class as the alternative in `value_range`.
RESIDUE_REMOVED_THRESHOLD = 0.5

# IPCC 2006 Vol 4 Ch 5 Table 5.5 input-level definitions (retained in the 2019 Refinement).
INPUT_DEFINITIONS = {
    "low input": ("Low residue return occurs when there is due to removal of residues (via "
                  "collection or burning), frequent bare-fallowing, production of crops yielding "
                  "low residues (e.g., vegetables, tobacco, cotton), no mineral fertilization or "
                  "N-fixing crops."),
    "medium input": ("Representative for annual cropping with cereals where all crop residues "
                     "are returned to the field. If residues are removed then supplemental "
                     "organic matter (e.g., manure) is added. Also requires mineral fertilization "
                     "or N-fixing crop in rotation."),
    "high input without manure": (
        "Represents significantly greater crop residue inputs over medium C input cropping "
        "systems due to additional practices, such as production of high residue yielding "
        "crops, use of green manures, cover crops, improved vegetated fallows, irrigation, "
        "frequent use of perennial grasses in annual crop rotations, but without manure "
        "applied."),
    "high input with manure": ("Represents high input of crop residues together with regular "
                               "addition of animal manure."),
}
LOW_RESIDUE_CROPS = ("vegetable", "tobacco", "cotton")       # the Table 5.5 low-input examples
HIGH_INPUT_PRACTICE_WORDS = ("green manure", "improved fallow", "perennial grass")

SRC_T55 = ("IPCC 2019 Refinement Vol 4 Ch 5 Table 5.5 (updated), via FAO EX-ACT v9.4.2 "
           "'IPCC' sheet rows 59-68")

# Table 5.5 (updated): (F_LU long-term cultivated, F_LU flooded rice,
# F_MG full / reduced / no tillage, F_I low / medium / high w/o manure / high with manure).
TABLE_5_5 = {
    "cool temperate dry":   {"flu": 0.77, "flu_rice": 1.35, "fmg": (1.0, 0.98, 1.03), "fi": (0.95, 1.0, 1.04, 1.37)},
    "cool temperate moist": {"flu": 0.70, "flu_rice": 1.35, "fmg": (1.0, 1.04, 1.09), "fi": (0.92, 1.0, 1.11, 1.44)},
    "warm temperate dry":   {"flu": 0.76, "flu_rice": 1.35, "fmg": (1.0, 0.99, 1.04), "fi": (0.95, 1.0, 1.04, 1.37)},
    "warm temperate moist": {"flu": 0.69, "flu_rice": 1.35, "fmg": (1.0, 1.05, 1.10), "fi": (0.92, 1.0, 1.11, 1.44)},
    "tropical dry":         {"flu": 0.92, "flu_rice": 1.35, "fmg": (1.0, 0.99, 1.04), "fi": (0.95, 1.0, 1.04, 1.37)},
    "tropical moist":       {"flu": 0.83, "flu_rice": 1.35, "fmg": (1.0, 1.04, 1.10), "fi": (0.92, 1.0, 1.11, 1.44)},
    "tropical wet":         {"flu": 0.83, "flu_rice": 1.35, "fmg": (1.0, 1.04, 1.10), "fi": (0.92, 1.0, 1.11, 1.44)},
    "tropical montane":     {"flu": 0.64, "flu_rice": 1.35, "fmg": (1.0, 1.09, 1.16), "fi": (0.94, 1.0, 1.08, 1.41)},
}
TILLAGE = ("full tillage", "reduced tillage", "no tillage")
INPUT = ("low input", "medium input", "high input without manure", "high input with manure")


def _practices(sm: dict) -> list[str]:
    return [str(p).strip().lower() for p in (sm.get("conservation_practices") or []) if p]


def tillage_class(sm: dict) -> int:
    """Index into TILLAGE from conservation_practices keywords."""
    ps = _practices(sm)
    if any(("no-till" in p or "no till" in p or "zero till" in p or "zero-till" in p) for p in ps):
        return 2
    if any(("minimum" in p or "reduced" in p) for p in ps):
        return 1
    return 0


def _receives_compost(sm: dict, food: dict) -> bool:
    if not sm.get("uses_compost") or not sm.get("compost_application_rate"):
        return False
    ids = [str(i) for i in (sm.get("compost_crop_ids") or [])]
    return not ids or str(food.get("id")) in ids


def _fert_rows(assessment: dict, food: dict) -> list[str]:
    """Lower-case types of active fertiliser rows applied to `food`."""
    fert = ((assessment.get("management_practices") or {}).get("fertilization")) or {}
    rows = fert.get("fertilizer_applications") if isinstance(fert, dict) else fert
    out = []
    for app in rows or []:
        if not isinstance(app, dict):
            continue
        t = str(app.get("fertilizer_type") or "").strip().lower()
        if not t or t == "none":
            continue
        if (app.get("application_rate") or 0) <= 0 or app.get("applications_per_season") == 0:
            continue
        ids = [str(i) for i in (app.get("crop_ids") or [])]
        if not ids or str(food.get("id")) in ids:
            out.append(t)
    return out


_MANURE_WORDS = ("manure", "dung", "poultry", "slurry")
_ORGANIC_WORDS = _MANURE_WORDS + ("organic", "compost")


def _irrigated(assessment: dict) -> bool:
    wm = ((assessment.get("management_practices") or {}).get("water_management")) or {}
    irr = str(wm.get("irrigation_system") or "").strip().lower()
    return bool(irr) and "rainfed" not in irr and irr not in ("none", "no", "n/a")


def _has_legume(food: dict) -> bool:
    try:
        from .field_model import _legume_partners, LEGUMES
    except ImportError:
        from field_model import _legume_partners, LEGUMES
    own = str(food.get("name") or "").lower()
    return bool(_legume_partners(food)) or any(leg in own for leg in LEGUMES)


def input_evidence(assessment: dict, food: dict) -> dict:
    """The payload facts the Table 5.5 definitions are applied to."""
    sm = ((assessment.get("management_practices") or {}).get("soil_management")) or {}
    rm = food.get("residue_management") or {}
    removed = float(rm.get("fraction_removed") or 0.0) + float(rm.get("fraction_burnt") or 0.0)
    rows = _fert_rows(assessment, food)
    compost = _receives_compost(sm, food)
    src = str(sm.get("compost_source") or "").lower()
    animal_manure = (compost and "manure" in src) or any(
        any(w in t for w in _MANURE_WORDS) for t in rows)
    ps = _practices(sm)
    high_practices = (["cover crops"] if sm.get("cover_crops") else []) \
        + (["irrigation"] if _irrigated(assessment) else []) \
        + [p for p in ps if any(w in p for w in HIGH_INPUT_PRACTICE_WORDS)]
    crop_text = f"{food.get('name') or ''} {food.get('category') or ''}".lower()
    return {
        "removed_fraction": min(removed, 1.0),
        "organic_matter_added": compost or any(any(w in t for w in _ORGANIC_WORDS) for t in rows),
        "animal_manure": animal_manure,
        "other_organic": (compost and "manure" not in src) or any("mulch" in p for p in ps),
        "high_practices": high_practices,
        "low_residue_unfertilised": (any(w in crop_text for w in LOW_RESIDUE_CROPS)
                                     and not any(not any(w in t for w in _ORGANIC_WORDS)
                                                 for t in rows)
                                     and not _has_legume(food)),
    }


def _classify(ev: dict, removed: bool) -> tuple[int, str, int | None, str | None]:
    """Table 5.5 class for one residue state: (class, reason, alternative class, why)."""
    if removed:
        if ev["organic_matter_added"]:
            return 1, "residues removed but supplemental organic matter added (medium)", None, None
        return 0, "residues removed or burnt (low)", None, None
    if ev["low_residue_unfertilised"]:
        return 0, "low-residue crop without mineral fertiliser or N-fixing crop (low)", None, None
    if ev["high_practices"]:
        what = ", ".join(ev["high_practices"])
        if ev["animal_manure"]:
            return 3, f"residues returned + {what} + regular animal manure (high, with manure)", None, None
        return 2, f"residues returned + {what} (high, without manure)", None, None
    if ev["animal_manure"]:
        return 1, ("residues returned + animal manure but no other high-input practice: medium "
                   "(Table 5.5 'with manure' needs high residue input as well)"), 3, \
            "if the manure alone is a significant extra C input: high input with manure"
    if ev["other_organic"]:
        return 1, ("residues returned + non-manure compost / mulch: medium (not a Table 5.5 "
                   "high-input practice)"), 2, \
            "if the compost / mulch is a significant extra C input: high input without manure"
    return 1, "all residues returned (medium)", None, None


def input_class(assessment: dict, food: dict) -> tuple[int, str, list[tuple[int, str]]]:
    """(class index into INPUT, reason, [(alternative class, why), ...]).

    Disclosed rules: residues are "removed" when fraction_removed + fraction_burnt >
    RESIDUE_REMOVED_THRESHOLD (majority); a partial removal also reports the class of the
    other residue state. Only animal manure (compost_source "Animal manure" or manure
    fertiliser rows) qualifies for "with manure"; any declared annual application counts as
    "regular" (IPCC gives no minimum rate)."""
    ev = input_evidence(assessment, food)
    frac = ev["removed_fraction"]
    removed = frac > RESIDUE_REMOVED_THRESHOLD
    cls, why, alt, alt_why = _classify(ev, removed)
    alts: list[tuple[int, str]] = []
    if alt is not None:
        alts.append((alt, alt_why))
    if 0.0 < frac < 1.0:
        o_cls, o_why, o_alt, o_alt_why = _classify(ev, not removed)
        state = "returned" if removed else "removed"
        if o_cls != cls:
            alts.append((o_cls, f"if the {frac:.0%} partial removal is read as residues {state}: "
                                f"{o_why}"))
        if o_alt is not None and o_alt != cls:
            alts.append((o_alt, o_alt_why))
    seen, uniq = {cls}, []
    for a in alts:
        if a[0] not in seen:
            seen.add(a[0])
            uniq.append(a)
    return cls, why, uniq


def _is_flooded_rice(food: dict) -> bool:
    name = str(food.get("name") or "").lower()
    if "rice" not in name and "paddy" not in name:
        return False
    regime = str(food.get("water_regime") or "").lower()
    return "upland" not in name and regime != "upland"


def soc_management(assessment: dict, region) -> dict:
    """SOC change from current management vs the IPCC reference (full tillage, medium
    input). Returns the CONTRACT `soc_management` record; `value` is None when not booked."""
    sm = ((assessment.get("management_practices") or {}).get("soil_management")) or {}
    years = sm.get("practices_adopted_years_ago")
    base = {"value": None, "unit": "kg CO2/yr", "reported_separately": True,
            "included_in_headline": False,
            "method": ("IPCC 2019 Refinement Vol 4 Tier 1 SOC stock change (Ch 2 Eq 2.25, "
                       f"D = {TRANSITION_YEARS} yr; Ch 5 Table 5.5 F_LU/F_MG/F_I)"),
            "sign_convention": "positive = net CO2 emission from soil, negative = removal",
            "per_crop": [], "assumptions": []}
    if years is None:
        base["booked"] = False
        base["assumptions"].append(
            "practices_adopted_years_ago not given: SOC change from management NOT booked")
        return base
    try:
        years = float(years)
    except (TypeError, ValueError):
        base["booked"] = False
        base["assumptions"].append("practices_adopted_years_ago not numeric: not booked")
        return base
    if years < 0 or years >= TRANSITION_YEARS:
        base["booked"] = False
        base["assumptions"].append(
            f"practices adopted {years:g} years ago, outside the {TRANSITION_YEARS}-year IPCC "
            "transition: soil assumed at its new equilibrium, no SOC change booked")
        return base

    try:
        from . import perennials as _per
    except ImportError:
        import perennials as _per
    perennial_of = getattr(_per, "perennial_for_food", None) or (
        lambda f: _per.perennial_for(f.get("name")))
    clim, exact = _luc.ipcc_climate(region)
    t = TABLE_5_5.get(clim) or TABLE_5_5["tropical moist"]
    soil = _luc._soil_class(assessment)
    soc_ref = _luc.SOC_REF.get(clim, _luc.SOC_REF["tropical moist"])[soil]
    till = tillage_class(sm)
    total = lo_total = hi_total = 0.0

    def co2_for(flu: float, inp: int, area: float) -> tuple[float, float]:
        soc_prev = soc_ref * flu * t["fmg"][0] * t["fi"][1]
        soc_now = soc_ref * flu * t["fmg"][till] * t["fi"][inp]
        d = (soc_now - soc_prev) / TRANSITION_YEARS                # t C/ha/yr
        return d, -d * C_TO_CO2 * 1000.0 * area

    for food in assessment.get("foods") or []:
        name = food.get("name", "crop")
        area = float(food.get("area_allocated") or 0.0)
        if area <= 0:
            continue
        if perennial_of(food) is not None:
            base["per_crop"].append({"crop": name, "value": None,
                                     "note": "perennial tree crop: Table 5.5 tillage/input "
                                             "factors not applied"})
            continue
        inp, why, alts = input_class(assessment, food)
        flu = t["flu_rice"] if _is_flooded_rice(food) else t["flu"]
        d_soc, co2 = co2_for(flu, inp, area)
        alt_rows = [{"input": INPUT[a], "f_i": t["fi"][a], "value": co2_for(flu, a, area)[1],
                     "why": w} for a, w in alts]
        vals = [co2] + [r["value"] for r in alt_rows]
        total += co2
        lo_total += min(vals)
        hi_total += max(vals)
        base["per_crop"].append({
            "crop": name, "area_ha": area, "value": co2, "unit": "kg CO2/yr",
            "delta_soc_t_c_per_ha_yr": d_soc, "soc_ref_t_c_per_ha": soc_ref,
            "f_lu": flu, "f_mg": t["fmg"][till], "f_i": t["fi"][inp],
            "tillage": TILLAGE[till], "input": INPUT[inp], "input_reason": why,
            "input_definition": INPUT_DEFINITIONS[INPUT[inp]],
            "input_alternatives": alt_rows,
            "value_range": [min(vals), max(vals)]})
    base["value"] = total
    base["value_range"] = [lo_total, hi_total]
    base["booked"] = True
    base["years_remaining_in_transition"] = TRANSITION_YEARS - years
    base["climate"] = clim
    base["soil_class"] = soil
    base["assumptions"] += [
        "previous practice = IPCC reference (full tillage, medium input; F_MG = F_I = 1.0)",
        f"current tillage: {TILLAGE[till]} (from conservation_practices)",
        "input class from the IPCC 2006/2019 Table 5.5 input-level definitions",
        f"engine assumption (no IPCC threshold): residues 'removed' when fraction_removed + "
        f"fraction_burnt > {RESIDUE_REMOVED_THRESHOLD:g} (majority); partial removal reports the "
        "other residue class in value_range (sensitivity, not interpolated)",
        "only animal manure (compost source 'Animal manure' or manure fertiliser rows) qualifies "
        "for 'with manure'; any declared annual application counts as regular (IPCC gives no "
        "minimum rate); non-manure compost and mulch are supplemental organic matter",
        "bare fallow frequency is not collected: cannot trigger low input",
        f"SOC_REF {soc_ref:g} t C/ha ({soil}, {clim}): {_luc.SRC_SOC_REF}",
        f"factors: {SRC_T55}",
    ]
    if not exact:
        base["assumptions"].append(f"climate '{getattr(region, 'climate_zone', '')}' mapped to "
                                   f"IPCC '{clim}' (fallback mapping)")
    return base


def note(rec: dict) -> str:
    """One-line disclosure for result notes."""
    if not rec.get("booked"):
        return ("soil carbon from management (reported separately, not in the headline): "
                + "; ".join(rec.get("assumptions") or []))
    v = rec["value"]
    word = "emission" if v > 0 else "removal" if v < 0 else "no change"
    lo, hi = rec.get("value_range") or (v, v)
    rng = (f"; input-class sensitivity range {lo:.0f} to {hi:.0f} kg CO2/yr (alternative "
           "Table 5.5 class where the inputs are ambiguous)") if abs(hi - lo) > 1e-9 else ""
    return (f"soil carbon from management (reported separately, NOT in the headline GWP): "
            f"{abs(v):.0f} kg CO2/yr {word} for the remaining "
            f"{rec['years_remaining_in_transition']:g} years of the IPCC 20-year transition "
            f"({rec['method']}){rng}")
