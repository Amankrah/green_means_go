#!/usr/bin/env python3
"""
inputs.py: auto-extract the purchased inputs (for the supply-chain solver) from a submitted
farm assessment, so the frontend doesn't pass them separately.

Every wizard field that physically implies a flow becomes one here (or an elementary flow in
engine/farm_flows.py):

  Fertiliser   : rate (kg PRODUCT/ha per application) x applications_per_season x
                 sum(area x crops_per_year) over the row's crop_ids (all crops when blank).
                 Product-basis rows (kg product) go to product datasets; compound NPK of a
                 grade other than 15-15-15 and graded foliar / unknown products become
                 nutrient-basis rows (kg N, P2O5, K2O). Every row carries its nutrient
                 content so a nutrient-basis match can be converted (to_matched_basis).
                 Type "None", rate 0 and 0 applications are skipped.
  Seed         : seed rate (kg/ha, user or FAO default) x area x crops_per_year -> kg
  Pesticides   : kg active ingredient -> AI production dataset (engine/pesticides.py)
  Fuels        : fuel_consumption (L/month x 12), per carrier (diesel, petrol, kerosene, LPG,
                 biodiesel) via engine/energy_carriers.py
  Energy       : energy_sources per type: grid kWh, diesel generator L (or kWh via the genset
                 specific consumption), solar kWh, biogas m3, firewood kg, charcoal kg
  Equipment    : hours x fuel_efficiency (or ASABE D497 class estimate); a metered fuel of
                 the same carrier replaces the estimate only when its use covers that
                 equipment (USE RULE below); manual / animal / solar power -> no fuel
  Irrigation   : pumping energy per m3 (ecoinvent irrigation dataset coefficients) when the
                 farm did not declare its pumping energy and does not irrigate by bucket /
                 hand; the water itself is an elementary withdrawal (engine/farm_flows.py)
  Compost      : purchased compost, rate t/ha/YEAR x area of compost_crop_ids crops
  Lime         : lime_applications (limestone / dolomite) t/ha/year x area of their crops
  Storage      : cold-storage refrigerant top-up = annual leakage (engine/refrigerants.py)
  Logistics    : packaging of the harvest, transport of inputs to the farm, transport of the
                 harvest to the first point of sale (when a distance is given)

USE RULE (metered fuel vs equipment estimates). Each metered fuel row is classed by its
primary_use: generator / transport / heat / pumping / field operations / general (blank or
unrecognised). A metered row of carrier C replaces the estimate of equipment on carrier C
only when its class covers that equipment (pumping -> water pumps, field operations ->
tractors and other field machinery) or is general. A motorbike's metered petrol therefore no
longer zeroes a petrol tractor; every replacement and every kept estimate is disclosed.
"""
from __future__ import annotations

import re

try:
    from . import energy_carriers as ec
    from . import crop_defaults as cd
    from . import pesticides as pz
except ImportError:  # script use
    import energy_carriers as ec  # type: ignore
    import crop_defaults as cd  # type: ignore
    import pesticides as pz  # type: ignore

# Litre LHVs (MJ/L) for callers that import them; same numbers as energy_carriers.LHV.
FUEL_MJ_PER_L = {"diesel": ec.LHV["diesel"]["L"][0], "petrol": ec.LHV["petrol"]["L"][0],
                 "gasoline": ec.LHV["petrol"]["L"][0], "kerosene": ec.LHV["kerosene"]["L"][0],
                 "biodiesel": ec.LHV["biodiesel"]["L"][0]}

# ---- fertiliser ------------------------------------------------------------------------
# Legacy steer table (cited by scripts/regenerate_inventory_mapping.py); the steering itself
# is FERTILISER_PRODUCTS below, which keeps these two entries.
FERTILISER_MATCH = {
    "ammonium sulfate": "market for ammonium sulfate",
    "ammonium sulphate": "market for ammonium sulfate",
    "sulphate of ammonia": "market for ammonium sulfate",
    "calcium ammonium nitrate": "market for calcium ammonium nitrate",
    "(can)": "market for calcium ammonium nitrate",
}
GRADE_SOURCE = ("FAO & IFA (2000) Fertilizers and their use, 4th ed., common fertilizers and "
                "their nutrient content (urea 46% N, AS 21% N, CAN 26-28% N, AN 33.5% N, DAP "
                "18-46-0, MAP 11-52-0, SSP 16-20% P2O5, TSP 46% P2O5, MOP 60% K2O, SOP 50% K2O)")
# (regex on the lower-cased type, key, default grade N-P2O5-K2O %, product-basis match_as or
#  None to match on the declared name). Order matters: CAN / UAN before AN, SOP before MOP.
FERTILISER_PRODUCTS = (
    (r"calcium ammonium nitrate|\(can\)|\bcan\b", "CAN", (27.0, 0.0, 0.0),
     "market for calcium ammonium nitrate"),
    (r"urea ammonium nitrate|\buan\b", "UAN", (30.0, 0.0, 0.0), None),
    (r"ammonium sul(f|ph)ate|sul(f|ph)ate of ammonia", "AS", (21.0, 0.0, 0.0),
     "market for ammonium sulfate"),
    (r"ammonium nitrate", "AN", (33.5, 0.0, 0.0), None),
    (r"diammonium phosphate|\bdap\b", "DAP", (18.0, 46.0, 0.0), None),
    (r"monoammonium phosphate|\bmap\b", "MAP", (11.0, 52.0, 0.0), None),
    (r"triple super ?phosphate|\btsp\b", "TSP", (0.0, 46.0, 0.0), None),
    (r"single super ?phosphate|\bssp\b|super ?phosphate", "SSP", (0.0, 18.0, 0.0), None),
    (r"sul(f|ph)ate of potash|potassium sul(f|ph)ate|\bsop\b", "SOP", (0.0, 0.0, 50.0),
     "market for potassium sulfate"),
    # The matcher otherwise lands on "nutrient supply from potash salt | ..., as K2O" (per kg
    # K2O) while the amount is kg KCl: ~1.67x too high.
    (r"muriate of potash|potassium chloride|\bmop\b|\bkcl\b|potash", "MOP", (0.0, 0.0, 60.0),
     "market for potassium chloride | potassium chloride | Cutoff, U"),
    (r"\burea\b", "urea", (46.0, 0.0, 0.0), None),
)
# Matcher text for a product identified from its grade alone (the declared name is free
# text such as "white prills"): the same texts the wizard's own type names produce.
PRODUCT_QUERY = {
    "CAN": "market for calcium ammonium nitrate", "AS": "market for ammonium sulfate",
    "UAN": "urea ammonium nitrate fertiliser", "AN": "ammonium nitrate fertiliser",
    "DAP": "Diammonium Phosphate (DAP) fertiliser", "MAP": "monoammonium phosphate fertiliser",
    "TSP": "triple superphosphate fertiliser", "SSP": "Single Super Phosphate fertiliser",
    "SOP": "market for potassium sulfate",
    "MOP": "market for potassium chloride | potassium chloride | Cutoff, U",
    "urea": "urea fertiliser",
}
_ORGANIC_RE = re.compile(r"organic|manure|compost|bio-?fertili|poultry|vermi|guano")
NUTRIENTS = ("N", "P2O5", "K2O")
NPK_REFERENCE_GRADE = (15.0, 15.0, 15.0)
NPK_DEFAULT_SOURCE = ("NPK 15-15-15 assumed when no grade is given: the store's compound-"
                      "fertiliser datasets (WFLDB 'NPK (15-15-15)'; ecoinvent 3.11 'nutrient "
                      "supply from NPK (15-15-15) fertiliser') are for this grade; enter the "
                      "bag grade")
# ecoinvent 3.11 compound route: 'nutrient supply from NPK (15-15-15) fertiliser' is a
# multi-output activity (one product per nutrient, per kg nutrient; the allocated outputs
# together carry the whole compound burden), so any NPK grade is modelled nutrient by
# nutrient on the compound production route.
NPK_NUTRIENT_DATASET = {
    "N": "nutrient supply from NPK (15-15-15) fertiliser | inorganic nitrogen fertiliser, as N | Cutoff, U",
    "P2O5": "nutrient supply from NPK (15-15-15) fertiliser | inorganic phosphorus fertiliser, as P2O5 | Cutoff, U",
    "K2O": "nutrient supply from NPK (15-15-15) fertiliser | inorganic potassium fertiliser, as K2O | Cutoff, U",
}
# Unknown product of known grade (foliar, trade blends): the ecoinvent 3.11 nutrient
# markets (per kg nutrient, the global supply mix of each nutrient).
GENERIC_NUTRIENT_DATASET = {
    "N": "market for inorganic nitrogen fertiliser, as N | inorganic nitrogen fertiliser, as N | Cutoff, U",
    "P2O5": "market for inorganic phosphorus fertiliser, as P2O5 | inorganic phosphorus fertiliser, as P2O5 | Cutoff, U",
    "K2O": "market for inorganic potassium fertiliser, as K2O | inorganic potassium fertiliser, as K2O | Cutoff, U",
}
_NUTRIENT_BASIS_RE = re.compile(r"\bas (n|p2o5|k2o)\b", re.IGNORECASE)

# ---- lime --------------------------------------------------------------------------------
# Agricultural lime is ground limestone / dolomite (ecoinvent 3.11 products). The CO2 released
# in the field (IPCC 2019 Vol 4 Ch 11 Eq 11.12) is a field emission, not booked here.
LIME_DATASETS = {
    "limestone": "market for limestone, milled, loose | limestone, milled, loose | Cutoff, U",
    "dolomite": "market for dolomite | dolomite | Cutoff, U",
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

# Metered-fuel use classes (USE RULE). First matching class wins.
_USE_CLASSES = (
    ("genset", ("generat", "genset", "lighting")),
    ("transport", ("transport", "motorbike", "motorcycle", "motor bike", "vehicle", "truck",
                   "pickup", "pick-up", "haul", "deliver", "market", "car ", "tricycle")),
    ("heat", ("dry", "cook", "heat", "boil", "smok", "roast", "process", "milling", "mill ")),
    ("pump", ("irrig", "pump")),
    ("field", ("land", "till", "plough", "plow", "harrow", "ridg", "plant", "sow", "spray",
               "harvest", "thresh", "tractor", "machin", "field", "farm operation", "weed",
               "cultivat", "mechani")),
)
# Machinery carriers: a metered row of these, used for field work / pumping / unstated use,
# covers the field-operation diesel default of engine/activity_defaults.py.
MACHINERY_CARRIERS = ("diesel", "petrol", "biodiesel")
# Same-stream tolerance between a diesel-generator energy source and a diesel fuel row
# (a data-entry dedupe heuristic, not an emission factor).
GENERATOR_SAME_STREAM_TOL = 0.05

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
_MANUAL_IRRIGATION = ("bucket", "manual", "watering can", "by hand", "hand ")

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
INPUT_MASS_KINDS = ("fertiliser", "pesticide", "seed", "compost", "lime")
LORRY = "market for transport, freight, lorry, unspecified"
LCV = "market for transport, freight, light commercial vehicle, fleet average"
# Ordered: "pickup" must be tested before "truck" ("Pickup truck" is a light commercial
# vehicle, not a lorry). The store has no freight dataset for motorcycles, tricycles or
# buses; the light commercial vehicle is their proxy (disclosed).
MARKET_TRANSPORT_MATCH = {
    "pickup": LCV, "pick-up": LCV, "large truck": LORRY, "lorry": LORRY, "truck": LORRY,
    "public transport": LCV, "motorcycle": LCV, "motorbike": LCV, "tricycle": LCV,
}
_LCV_PROXY_MODES = ("public transport", "motorcycle", "motorbike", "tricycle")
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


def _crops_per_year(food: dict) -> int:
    try:
        return max(1, int(food.get("crops_per_year") or 1))
    except (TypeError, ValueError):
        return 1


def crop_scope(assessment: dict, crop_ids=None, per_season: bool = True) -> tuple[float, float, list[dict]]:
    """(sum of area x crops_per_year, sum of area, foods) over the foods named in crop_ids
    ([] or None = every food). per_season=False ignores crops_per_year (annual rates such as
    compost and lime). In a per-crop sub-assessment a row for other crops scopes to 0."""
    foods = assessment.get("foods") or []
    ids = {str(c).strip() for c in (crop_ids or []) if str(c).strip()}
    picked = [f for f in foods if not ids or str(f.get("id")) in ids]
    area = sum((f.get("area_allocated") or 0) for f in picked)
    if not per_season:
        return area, area, picked
    return sum((f.get("area_allocated") or 0) * _crops_per_year(f) for f in picked), area, picked


def use_class(text) -> str:
    """Class of a metered fuel row's primary_use (USE RULE); 'general' when blank/unknown."""
    low = f"{_norm(text)} "
    for cls, words in _USE_CLASSES:
        if any(w in low for w in words):
            return cls
    return "general"


def is_manual_irrigation(system_text) -> bool:
    low = f"{_norm(system_text)} "
    return any(w in low for w in _MANUAL_IRRIGATION)


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


# ---- fertiliser ------------------------------------------------------------------------

def _parse_grade(text: str | None) -> tuple[float, float, float] | None:
    """'15-15-15', '20:10:10', '23 10 5' -> (N, P2O5, K2O) percent; None when invalid."""
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*[-:/ ]\s*(\d+(?:\.\d+)?)\s*[-:/ ]\s*(\d+(?:\.\d+)?)",
                 str(text or ""))
    if not m:
        return None
    g = tuple(float(x) for x in m.groups())
    if any(v > 100 for v in g) or not (0 < sum(g) <= 100):
        return None
    return g  # type: ignore[return-value]


def _fertiliser_product(ftype: str, grade=None):
    """(key, default grade, match_as) from the type text; else, for a free-text name, from a
    declared grade equal to a straight product's standard grade (46-0-0 is urea)."""
    low = _norm(ftype)
    for pat, key, g, match_as in FERTILISER_PRODUCTS:
        if re.search(pat, low):
            return key, g, match_as
    if grade is not None and "foliar" not in low and not _ORGANIC_RE.search(low):
        for _pat, key, g, _m in FERTILISER_PRODUCTS:
            if tuple(grade) == g:
                return key, g, PRODUCT_QUERY[key]
    return None


def is_none_fertiliser(ftype) -> bool:
    return _norm(ftype) in ("", "none", "no fertilizer", "no fertiliser", "not used")


def nutrient_basis_of(name: str | None) -> str | None:
    """'N' / 'P2O5' / 'K2O' when a dataset name or reference product is expressed per kg of
    that nutrient ('..., as N', 'as P2O5', 'as K2O'), else None (per kg product)."""
    m = _NUTRIENT_BASIS_RE.search(name or "")
    if not m:
        return None
    return {"n": "N", "p2o5": "P2O5", "k2o": "K2O"}[m.group(1).lower()]


class FertiliserBasisError(ValueError):
    """A fertiliser amount cannot be expressed on the matched dataset's nutrient basis."""


def to_matched_basis(inp: dict, matched_name: str | None,
                     reference_product: str | None = None) -> tuple[float, str | None]:
    """Amount of fertiliser input `inp` on the basis of the dataset it was matched to.

    For the orchestrator (engine/orchestrator.py), before units.to_ref_unit: a product-basis
    row (kg product) matched to a nutrient-basis dataset ('as N' / 'as P2O5' / 'as K2O') is
    converted with its nutrient_content. Raises FertiliserBasisError when that nutrient is
    absent or unknown, or when a nutrient row landed on a dataset of another basis. Non-
    fertiliser inputs pass through unchanged. Returns (amount, note or None)."""
    amount = float(inp["amount"])
    if inp.get("kind") != "fertiliser":
        return amount, None
    ds_basis = nutrient_basis_of(reference_product) or nutrient_basis_of(matched_name)
    if inp.get("basis") == "nutrient":
        if ds_basis == inp.get("nutrient"):
            return amount, None
        raise FertiliserBasisError(
            f"'{inp.get('name')}' is {amount:g} kg {inp.get('nutrient')} but matched "
            f"'{matched_name}' ({'per kg ' + ds_basis if ds_basis else 'per kg product'}); excluded")
    if ds_basis is None:
        return amount, None
    content = inp.get("nutrient_content") or {}
    frac = content.get(ds_basis)
    if not frac:
        raise FertiliserBasisError(
            f"'{inp.get('name')}' is kg product but matched '{matched_name}' (per kg {ds_basis}) "
            f"and its {ds_basis} content is {'zero' if frac == 0 else 'unknown'}; excluded")
    out = amount * frac
    note = (f"'{inp.get('name')}': {amount:g} kg product x {frac:.3g} kg {ds_basis}/kg = "
            f"{out:g} kg {ds_basis} for nutrient-basis dataset '{matched_name}'")
    others = [n for n in NUTRIENTS if n != ds_basis and content.get(n)]
    if others:
        note += (f"; its {', '.join(others)} share is not in that dataset (multi-nutrient product "
                 "matched to a single-nutrient dataset), so the burden is understated: review")
    return out, note


def _nutrient_rows(base_name: str, kg_product: float, grade, datasets: dict, extra: dict) -> list[dict]:
    total = sum(grade)
    rows = []
    for nut, pct in zip(NUTRIENTS, grade):
        if pct <= 0:
            continue
        rows.append({"name": f"{base_name} ({nut})", "match_as": datasets[nut],
                     "amount": kg_product * pct / 100.0, "unit": "kg", "kind": "fertiliser",
                     "basis": "nutrient", "nutrient": nut,
                     "product_kg": kg_product * pct / total, **extra})
    return rows


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
        notes.append(f"{pz.WARNING_PREFIX}fertiliser reported but no crop area: fertiliser "
                     "inputs cannot be scaled, so they are NOT counted")
        return
    used_names: dict[str, int] = {}
    for app in fert.get("fertilizer_applications") or []:
        if not isinstance(app, dict):
            continue
        ftype = str(app.get("fertilizer_type") or "fertiliser").strip()
        if is_none_fertiliser(ftype):
            continue                   # placeholder row: no product, no burden
        rate = app.get("application_rate") or 0
        n = app.get("applications_per_season")
        if n is None:
            n = 1                      # not stated: one application per season
        if rate < 0 or n < 0:
            # Rejected by the API model; defend the engine anyway so a negative rate can
            # never become an emission credit.
            notes.append(f"{pz.WARNING_PREFIX}fertiliser '{ftype}': negative rate or "
                         "application count set to zero")
            rate, n = max(rate, 0), max(n, 0)
        if n == 0:
            # 0 means zero everywhere (the kernel reads it as 0 too).
            notes.append(f"fertiliser '{ftype}': 0 applications per season; not counted")
            continue
        if rate <= 0:
            continue
        crop_ids = app.get("crop_ids") or []
        area_seasons, _area, _foods = crop_scope(assessment, crop_ids, per_season=True)
        if area_seasons <= 0:
            notes.append(f"fertiliser '{ftype}': applied to crops {crop_ids} only; none of them is "
                         "in this product system")
            continue
        kg = rate * n * area_seasons
        npk_txt = (app.get("npk_ratio") or "").strip()
        grade = _parse_grade(npk_txt)
        if npk_txt and grade is None:
            notes.append(f"fertiliser '{ftype}': NPK grade '{npk_txt}' not understood "
                         "(expected N-P2O5-K2O, e.g. 15-15-15); ignored")
        name = f"{ftype} {npk_txt}".strip() + " fertiliser"
        k = used_names.get(name, 0)
        used_names[name] = k + 1
        if k:
            name = f"{name} #{k + 1}"   # contribution_by_source is keyed by input name
        extra = {"fertiliser_type": ftype, "crop_ids": list(crop_ids)}
        low = _norm(ftype)
        product = _fertiliser_product(ftype, grade)
        is_npk = "npk" in low or "compound" in low
        if _ORGANIC_RE.search(low):
            row = {"name": name, "amount": kg, "unit": "kg", "kind": "fertiliser", "basis": "product",
                   "product_kg": kg, **extra}
            if grade:
                row["nutrient_content"] = dict(zip(NUTRIENTS, (g / 100.0 for g in grade)))
            inputs.append(row)
        elif product and not is_npk:
            key, default_grade, match_as = product
            g = grade or default_grade
            row = {"name": name, "amount": kg, "unit": "kg", "kind": "fertiliser", "basis": "product",
                   "product_kg": kg, "nutrient_content": dict(zip(NUTRIENTS, (v / 100.0 for v in g))),
                   "nutrient_content_source": "declared grade" if grade else GRADE_SOURCE, **extra}
            if match_as:
                row["match_as"] = match_as
            inputs.append(row)
        elif is_npk:
            g = grade
            if g is None:
                g = NPK_REFERENCE_GRADE
                notes.append(f"fertiliser '{ftype}': no NPK grade given; {NPK_DEFAULT_SOURCE}")
            if g == NPK_REFERENCE_GRADE:
                # WFLDB / ecoinvent compound product dataset of exactly this grade (kg product)
                row = {"name": name, "amount": kg, "unit": "kg", "kind": "fertiliser", "basis": "product",
                       "product_kg": kg, "nutrient_content": dict(zip(NUTRIENTS, (v / 100.0 for v in g))),
                       **extra}
                if grade is None:
                    row["estimated"] = True
                    row["estimate_meta"] = {"basis": NPK_DEFAULT_SOURCE}
                inputs.append(row)
            else:
                inputs.extend(_nutrient_rows(name, kg, g, NPK_NUTRIENT_DATASET, extra))
                notes.append(f"fertiliser '{name}': grade {npk_txt} modelled per nutrient "
                             f"({', '.join(f'{v:g}% {nut}' for nut, v in zip(NUTRIENTS, g) if v)}) on "
                             "the ecoinvent 3.11 NPK compound route ('nutrient supply from NPK "
                             "(15-15-15) fertiliser', per kg nutrient)")
        elif grade and "foliar" not in low and sum(1 for v in grade if v > 0) >= 2:
            inputs.extend(_nutrient_rows(name, kg, grade, NPK_NUTRIENT_DATASET, extra))
            notes.append(f"fertiliser '{name}': compound product not in the fertiliser table; grade "
                         f"{npk_txt} modelled per nutrient on the ecoinvent 3.11 NPK compound route")
        elif grade:
            inputs.extend(_nutrient_rows(name, kg, grade, GENERIC_NUTRIENT_DATASET, extra))
            notes.append(f"fertiliser '{name}': product not in the fertiliser table; modelled per "
                         "nutrient from its grade with the ecoinvent 3.11 nutrient supply markets "
                         "('market for inorganic ... fertiliser, as N / P2O5 / K2O')")
        elif "foliar" in low:
            notes.append(f"{pz.WARNING_PREFIX}fertiliser '{ftype}': foliar product without an NPK "
                         "grade; its nutrient content is unknown, so its production burden is NOT "
                         "counted. Enter the label grade.")
        else:
            inputs.append({"name": name, "amount": kg, "unit": "kg", "kind": "fertiliser",
                           "basis": "product", "product_kg": kg, **extra})
            notes.append(f"fertiliser '{ftype}': product and grade unknown; matched by name as kg "
                         "of product (a nutrient-basis match is excluded, not converted). Enter "
                         "the NPK grade.")


# ---- seed, compost, lime -----------------------------------------------------------------

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
        cpy = _crops_per_year(f)
        row = {"name": f"{f.get('name', 'crop')} seed", "match_as": sd["match_as"],
               "amount": sd["kg_per_ha"] * area * cpy, "unit": "kg", "kind": "seed"}
        if sd["estimated"]:
            row["estimated"] = True
            row["estimate_meta"] = {"basis": "default seed rate", "source": sd["source"],
                                    "kg_per_ha": sd["kg_per_ha"]}
        if cpy > 1:
            notes.append(f"seed '{f.get('name')}': {cpy} crops per year, sown {cpy} times")
        inputs.append(row)


def _compost_inputs(assessment, inputs, notes):
    mp = assessment.get("management_practices") or {}
    sm = mp.get("soil_management") or {}
    if not sm.get("uses_compost"):
        return
    src = _norm(sm.get("compost_source"))
    rate_t_ha = sm.get("compost_application_rate")
    if rate_t_ha is not None and rate_t_ha < 0:
        notes.append(f"{pz.WARNING_PREFIX}compost application rate is negative; set to zero")
        rate_t_ha = 0
    if "purchas" in src:
        # t/ha/YEAR: not multiplied by crops_per_year.
        area = crop_scope(assessment, sm.get("compost_crop_ids") or [], per_season=False)[1]
        if rate_t_ha and area:
            inputs.append({"name": "compost", "match_as": "market for compost",
                           "amount": rate_t_ha * 1000.0 * area, "unit": "kg", "kind": "compost"})
        elif rate_t_ha and sm.get("compost_crop_ids"):
            notes.append("purchased compost goes to other crops than this product system")
        else:
            notes.append("purchased compost reported but no application rate given; its production "
                         "burden is not quantified")
    elif src:
        notes.append(f"compost source '{sm.get('compost_source')}': on-farm material, no supply-chain "
                     "burden (cut-off); its N drives field N2O")


def _lime_inputs(assessment, inputs, notes):
    sm = (assessment.get("management_practices") or {}).get("soil_management") or {}
    for i, la in enumerate(sm.get("lime_applications") or []):
        if not isinstance(la, dict):
            continue
        mat = _norm(la.get("material"))
        rate = la.get("rate_t_per_ha_per_year") or 0
        if rate <= 0:
            continue
        key = "dolomite" if "dolomit" in mat else "limestone" if ("limestone" in mat or "calc" in mat) else None
        if key is None:
            notes.append(f"lime material '{la.get('material')}' not recognised (limestone / dolomite); "
                         "not counted")
            continue
        area = crop_scope(assessment, la.get("crop_ids") or [], per_season=False)[1]
        if area <= 0:
            continue
        inputs.append({"name": f"agricultural lime ({key})" + (f" #{i + 1}" if i else ""),
                       "match_as": LIME_DATASETS[key], "amount": rate * 1000.0 * area, "unit": "kg",
                       "kind": "lime", "lime_material": key})


# ---- energy ------------------------------------------------------------------------------

def _diesel_litres(amount, unit) -> float | None:
    """Diesel amount in litres (kg / m3 / MJ via units.FUELS diesel density and NCV), so a
    generator and a fuel row entered in different units can be compared; None when the unit
    cannot be converted (kWh is electricity output, handled by the genset consumption)."""
    u = ec._norm_unit(unit) or "L"
    if u == "kWh":
        return None
    try:
        return ec._units.convert(float(amount), u, "L", "diesel")
    except (ec._units.UnitMismatchError, TypeError, ValueError):
        return None


def _energy_inputs(assessment, inputs, notes):
    ee = assessment.get("equipment_energy") or {}
    metered: dict[str, list] = {}       # carrier -> [{use, cls, monthly, litres}]
    diesel_rows: list[dict] = []        # diesel fuel rows in litres (generator dedupe)
    for fu in ee.get("fuel_consumption") or []:
        monthly = fu.get("monthly_consumption") or 0
        if monthly < 0:
            notes.append(f"{pz.WARNING_PREFIX}fuel '{fu.get('fuel_type')}': negative monthly "
                         "consumption ignored")
            continue
        if monthly <= 0:
            continue
        carrier = carrier_or_classify(fu.get("fuel_type"), notes)
        if not carrier:
            notes.append(f"fuel type '{fu.get('fuel_type')}' not recognised; modelled as diesel")
            carrier = "diesel"
        unit = fu.get("unit") or "L"
        inp, note = ec.carrier_input(carrier, monthly * 12, unit, context="farm",
                                     name="diesel, burned in agricultural machinery"
                                     if carrier == "diesel" else None, strict=True)
        if inp:
            rec = {"use": _norm(fu.get("primary_use")), "cls": use_class(fu.get("primary_use")),
                   "monthly": monthly, "text": fu.get("primary_use"), "input": inp}
            inp["use_class"] = rec["cls"]
            inputs.append(inp)
            metered.setdefault(carrier, []).append(rec)
            litres = _diesel_litres(monthly, unit) if carrier == "diesel" else None
            if litres is not None:
                rec["litres"] = litres
                diesel_rows.append(rec)
        if note:
            notes.append(note)

    for en in ee.get("energy_sources") or []:
        et = _norm(en.get("energy_type"))
        monthly = en.get("monthly_consumption") or 0
        if monthly < 0:
            notes.append(f"{pz.WARNING_PREFIX}energy source '{en.get('energy_type')}': negative "
                         "monthly consumption ignored")
            continue
        if monthly <= 0:
            continue
        annual = monthly * 12
        use = _norm(en.get("primary_use"))
        if "generator" in et:
            unit = ec._norm_unit(en.get("unit")) or "L"
            estimated = basis = None
            if unit == "kWh":
                # metered as electricity: diesel = kWh x genset specific consumption (cited)
                litres_m = monthly * ec.GENSET_L_PER_KWH
                estimated, basis = True, ec.GENSET_L_PER_KWH_SOURCE
                notes.append(f"diesel generator '{en.get('primary_use')}': {monthly:g} kWh/month x "
                             f"{ec.GENSET_L_PER_KWH} L/kWh = {litres_m:.1f} L/month diesel")
            else:
                litres_m = _diesel_litres(monthly, unit)
            twin = None
            if litres_m is not None:
                for rec in diesel_rows:
                    big = max(rec["litres"], litres_m)
                    if (rec["cls"] == "genset" or (use and rec["use"] == use)
                            or abs(rec["litres"] - litres_m) <= GENERATOR_SAME_STREAM_TOL * big):
                        twin = rec
                        break
            if twin is not None:
                notes.append(f"diesel generator '{en.get('primary_use')}' is the same stream as the diesel "
                             f"fuel entry '{twin['text']}' (same use, generator use, or amounts within "
                             f"{GENERATOR_SAME_STREAM_TOL:.0%}); counted once")
                continue
            if diesel_rows and litres_m is not None and litres_m <= sum(r["litres"] for r in diesel_rows):
                notes.append(f"diesel generator '{en.get('primary_use')}' ({litres_m:g} L/month) counted "
                             "in addition to the declared diesel fuel; if the generator's diesel is part "
                             "of that fuel entry, remove one of them")
            amount, amt_unit = (litres_m * 12, "L") if litres_m is not None else (annual, unit)
            inp, note = ec.carrier_input("diesel", amount, amt_unit, context="genset",
                                         name="diesel, burned in generator (farm)",
                                         estimated=bool(estimated), basis=basis, strict=True)
            if inp:
                inp["use_class"] = "genset"
        elif "solar" in et:
            inp, note = ec.carrier_input("solar", annual, en.get("unit") or "kWh",
                                         name="solar PV electricity (on-farm)", strict=True)
        elif "grid" in et or "electric" in et:
            inp, note = ec.carrier_input("grid", annual, en.get("unit") or "kWh",
                                         name="electricity low voltage", strict=True)
        else:
            carrier = ec.carrier_of(et)
            if not carrier:
                notes.append(f"energy source '{en.get('energy_type')}' not recognised; not counted")
                continue
            inp, note = ec.carrier_input(carrier, annual, en.get("unit"), context="heat",
                                         name=f"{carrier.replace('_', ' ')} (on-farm)", strict=True)
        if inp:
            inputs.append(inp)
        if note:
            notes.append(note)

    # Equipment: estimate fuel unless a metered row of the same carrier covers it (USE RULE).
    for eq in ee.get("equipment") or []:
        ps = _norm(eq.get("power_source"))
        hrs = eq.get("hours_per_year") or 0
        etype = _norm(eq.get("equipment_type"))
        if hrs < 0:
            notes.append(f"{pz.WARNING_PREFIX}equipment '{eq.get('equipment_type')}': negative "
                         "hours per year ignored")
            continue
        if hrs <= 0:
            continue
        if any(w in ps for w in ("manual", "human", "animal")):
            continue          # human / animal labour: outside the system boundary (no fuel)
        if "solar" in ps:
            continue          # solar-powered equipment: no operational fuel
        if "electric" in ps:
            if not any(i.get("kind") == "electricity" for i in inputs):
                notes.append(f"electric equipment '{eq.get('equipment_type')}': enter its electricity "
                             "under energy sources (kWh); not estimated")
            continue
        carrier = ec.carrier_of(ps) or "diesel"
        eq_cls = "pump" if "pump" in etype else "field"
        rows = metered.get(carrier) or []
        cover = next((r for r in rows if r["cls"] in (eq_cls, "general")), None)
        if cover is not None:
            notes.append(f"equipment '{eq.get('equipment_type')}': {carrier} taken from the metered "
                         f"fuel entry '{cover['text']}' (use covers {eq_cls} equipment); not estimated")
            continue
        if rows:
            notes.append(f"equipment '{eq.get('equipment_type')}': metered {carrier} is for "
                         f"{', '.join(sorted({r['text'] or r['cls'] for r in rows}))}, not for this "
                         "equipment; its fuel is estimated separately")
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
            inp["use_class"] = eq_cls
            if len([i for i in inputs if i.get("name") == inp["name"]]):
                inp["name"] = f"{inp['name']} ({eq.get('equipment_type')})"
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
    system = ((assessment.get("management_practices") or {}).get("water_management") or {}).get(
        "irrigation_system")
    if is_manual_irrigation(system):
        notes.append(f"irrigation water {w['m3']:.0f} m3 ({tag}) applied by bucket / hand: no "
                     "pumping energy")
        return
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


def irrigation_pumping_accounted(assessment: dict, inputs: list[dict]) -> bool:
    """True when irrigation pumping energy is already in `inputs` (per-m3 estimate), declared
    by the farm (pump equipment / pumping fuel), or not motorised (bucket / hand)."""
    system = ((assessment.get("management_practices") or {}).get("water_management") or {}).get(
        "irrigation_system")
    return (any(i.get("kind") == "irrigation_energy" for i in inputs)
            or pumping_declared(assessment) is not None or is_manual_irrigation(system))


# ---- storage -----------------------------------------------------------------------------

def _refrigerants():
    try:
        from . import refrigerants as rf
    except ImportError:
        import refrigerants as rf  # type: ignore
    return rf


def refrigerant_leakage(assessment: dict, method: str | None = None) -> dict | None:
    """Cold-storage refrigerant leakage for the climate term (booked by the adapter):
    {kg_co2e, note, info} from engine/refrigerants.storage_leakage_co2e, or None."""
    storage = (assessment.get("equipment_energy") or {}).get("storage")
    fn = getattr(_refrigerants(), "storage_leakage_co2e", None)
    if not storage or fn is None:
        return None
    co2e, note, info = fn(storage, method)
    if not co2e and not note:
        return None
    leaked = (info.get("charge_kg") or 0.0) * (info.get("leak_rate") or 0.0)
    return {"kg_co2e": co2e, "leaked_kg": leaked, "note": note, "info": info}


# Leaked refrigerant is replaced: the top-up is a purchase. Only R-134a has a production
# dataset in the store.
REFRIGERANT_DATASETS = {"R-134a": "refrigerant R134a production | tetrafluoroethane, R134a | Cutoff, U"}


def _storage_inputs(assessment, inputs, notes):
    storage = (assessment.get("equipment_energy") or {}).get("storage") or {}
    facilities = [_norm(f) for f in (storage.get("facilities") or [])]
    if not any("cold" in f for f in facilities):
        return
    rf = _refrigerants()
    gas, charge = storage.get("refrigerant"), storage.get("refrigerant_charge_kg")
    leak_fn = getattr(rf, "annual_leakage_from_charge", None)
    if not gas or not charge or leak_fn is None:
        notes.append("cold storage declared without refrigerant and charge: refrigerant leakage "
                     "not modelled; enter cold-store electricity under energy sources")
        return
    kg, info = leak_fn(charge)
    desig = rf.canonical_name(gas) if hasattr(rf, "canonical_name") else gas
    desig = getattr(rf, "_ALIASES", {}).get(desig, desig)
    ds = REFRIGERANT_DATASETS.get(desig)
    if kg > 0 and ds:
        inputs.append({"name": f"refrigerant {desig} top-up (cold-storage leakage)", "match_as": ds,
                       "amount": kg, "unit": "kg", "kind": "refrigerant", "estimated": True,
                       "estimate_meta": {"basis": info.get("source"), "charge_kg": info.get("charge_kg"),
                                         "leak_rate": info.get("leak_rate")}})
    elif kg > 0:
        notes.append(f"cold storage: production of the {gas} top-up ({kg:.3g} kg/yr) not modelled "
                     "(no dataset for this refrigerant); its leakage emission is still counted")


# ---- logistics -----------------------------------------------------------------------------

def _market_mode(text) -> tuple[str | None, str | None, list[str]]:
    """(dataset or None for zero-emission, matched mode word, all modes) for the declared
    market transport mode. Several modes: the frontend's priority order decides (lorry modes,
    then light commercial vehicles, then zero-emission modes)."""
    mode = _norm(text)
    parts = [p.strip() for p in re.split(r",|;|\+|&| and ", mode) if p.strip()] or [mode]
    found = []
    for p in parts:
        kw = next((k for k in MARKET_TRANSPORT_MATCH if k in p), None)
        if kw:
            found.append((MARKET_TRANSPORT_MATCH[kw], kw))
        elif any(z in p for z in ZERO_EMISSION_MODES):
            found.append((None, p))
    for ds in (LORRY, LCV):
        hit = next((f for f in found if f[0] == ds), None)
        if hit:
            return hit[0], hit[1], parts
    if found:
        return None, found[0][1], parts
    return LORRY, None, parts


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

    # Inbound transport of purchased material inputs: PRODUCT mass (formulated pesticide, kg
    # fertiliser product, not kg AI / kg nutrient), kg -> t.
    basis = [{"name": i["name"], "kg": float(i.get("product_kg", i["amount"]))}
             for i in inputs if i.get("kind") in INPUT_MASS_KINDS and i.get("unit") == "kg"]
    t_inputs = sum(b["kg"] for b in basis) / 1000.0
    if t_inputs > 0:
        km = lg.get("input_transport_km")
        est = km is None
        if est:
            km = INPUT_TRANSPORT_DEFAULT_KM
        if km > 0:
            row = {"name": "transport of inputs to farm", "match_as": LORRY,
                   "amount": t_inputs * km, "unit": "tkm", "kind": "transport",
                   "km": km, "basis_inputs": basis}
            if est:
                row["estimated"] = True
                row["estimate_meta"] = {"basis": INPUT_TRANSPORT_SOURCE, "km": km}
                # The default distance must not be added to inputs matched to 'market for' /
                # 'market group for' datasets (they already carry average transport); only
                # the matcher knows the dataset, so the orchestrator rescales this row
                # (inbound_transport_tkm).
                row["default_distance_production_only"] = True
            inputs.append(row)

    km_mkt = lg.get("distance_to_market_km")
    if km_mkt and km_mkt > 0 and harvest_t > 0:
        ds, word, parts = _market_mode(lg.get("market_transport_mode"))
        if ds is None:
            notes.append("harvest carried to market on foot / bicycle / animal: no transport emissions")
        else:
            inputs.append({"name": "transport of harvest to first point of sale", "match_as": ds,
                           "amount": harvest_t * km_mkt, "unit": "tkm", "kind": "transport"})
            notes.append("system boundary extended to the first point of sale (transport to market "
                         "declared)")
            if word in _LCV_PROXY_MODES:
                notes.append(f"market transport by {word}: no freight dataset for this mode in the "
                             "store; light commercial vehicle used as proxy")
            if len(parts) > 1:
                notes.append(f"several market transport modes declared ({', '.join(parts)}); modelled "
                             f"with {word or 'lorry'} (priority: lorry, light vehicle, non-motorised)")
            if word is None:
                notes.append("market transport mode not stated or not recognised; lorry assumed")


def inbound_transport_tkm(row: dict, production_only_names: set[str] | None) -> float:
    """tkm of the inbound-transport row restricted to inputs whose matched dataset is a
    production dataset (not 'market for' / 'market group for'), when the distance is the
    default. For the orchestrator, after all inputs are matched. A declared distance is
    farmer data and applies to every input."""
    if not row.get("default_distance_production_only") or production_only_names is None:
        return float(row["amount"])
    kg = sum(b["kg"] for b in row.get("basis_inputs") or [] if b["name"] in production_only_names)
    return kg / 1000.0 * float(row.get("km") or INPUT_TRANSPORT_DEFAULT_KM)


def is_market_dataset(name: str | None) -> bool:
    low = _norm(name)
    return low.startswith("market for") or low.startswith("market group for") or "| market for" in low \
        or "| market group for" in low


def extract_purchased_inputs(assessment: dict) -> tuple[list[dict], list[str]]:
    """Return (purchased_inputs, notes) for the supply-chain solver. Raises ValueError for an
    energy amount whose unit can never be converted (the API returns 422)."""
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
    _compost_inputs(assessment, inputs, notes)
    _lime_inputs(assessment, inputs, notes)
    _storage_inputs(assessment, inputs, notes)
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
