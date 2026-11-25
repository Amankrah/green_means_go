#!/usr/bin/env python3
"""
perennials.py: perennial crops (tree crops, palms, plantain/banana) in a single-year farm LCA.

A perennial stand yields nothing for its first years, then produces for years to decades. A
one-year snapshot of a mature farm therefore misses the establishment phase. Following PAS
2050-1:2012 (supplementary requirements for horticultural products, clause on perennial
crops) and the WFLDB methodological guidelines (Nemecek et al. 2019, perennial crops), the
burden of the non-productive establishment years is amortised over the productive years of
the plantation:

    establishment factor  =  (immature_years x input_share + productive_years) / productive_years

applied to the annual field emissions, purchased inputs and land occupation of a mature
year. Without primary data on establishment-year inputs we take input_share = 1 (the
establishment years use the same inputs and land as a mature year): a conservative
screening assumption, flagged in the notes and overridable per crop with
`foods[].establishment = {"immature_years": .., "productive_years": .., "input_share": ..}`.
Blank (None) establishment fields fall back to the table values. A crop that is not in the
table is treated as perennial when the farmer gives both immature_years and productive_years.

Land occupation is reported as "Occupation, permanent crop" (not annual crop).

Phase lengths (immature = years before the first harvest; productive = harvest years), each
cited in PERENNIALS below. Only crops with a published phase split are listed; there is no
generic perennial default.
"""
from __future__ import annotations

PERENNIALS: dict[str, dict] = {
    "cocoa": {
        "tokens": ("cocoa", "cacao"),
        "immature_years": 3,
        "productive_years": 22,
        "lifetime_years": 25,
        "biomass_class": "Shaded Perennial",
        "source": "IITA crop profile 'Cocoa (Theobroma cacao)'; ICCO growing guidance: "
                  "pods from year 3 to 5, about 25 years economic life",
    },
    "oil palm": {
        "tokens": ("oil palm", "palm oil", "palm fruit", "fresh fruit bunch", "ffb"),
        "immature_years": 3,
        "productive_years": 22,
        "lifetime_years": 25,
        "biomass_class": "Oil palm",
        "source": "RSPO PalmGHG (Chase et al. 2012): 25-year cycle, 3-year immature phase; "
                  "Corley & Tinker (2016) The Oil Palm, 5th ed.",
    },
    # biomass_class None: no IPCC perennial biomass class is assigned for these crops yet
    # (engine/land_use_change.py must handle None, see .fix_team/requests/D2-service.md).
    "cashew": {
        "tokens": ("cashew",),
        "immature_years": 4,
        "productive_years": 31,
        "lifetime_years": 35,
        "biomass_class": None,
        "source": "European Forest Institute Land-use Planner, 'Raw cashew nuts - conventional "
                  "practices, Cote d'Ivoire' (2023): first harvest year 5, last harvest year 35, "
                  "then replanted",
    },
    "coffee": {
        "tokens": ("coffee",),
        "immature_years": 3,
        "productive_years": 22,
        "lifetime_years": 25,
        "biomass_class": None,
        "source": "CIRAD for USAID (2023) Consultancy on Coffee Carbon Footprint, s. 'The "
                  "perennial cycle scope': first fruits after 2-3 years, commercial cycle "
                  "25-30 years, immature phase 10-12% of the cycle (25-year cycle used)",
    },
    "rubber": {
        "tokens": ("rubber", "latex", "hevea"),
        "immature_years": 6,
        "productive_years": 19,
        "lifetime_years": 25,
        "biomass_class": None,
        "source": "Warren-Thomas et al. (2015) Conservation Letters, Supporting Information "
                  "(after Hansen & Top 2006; Hing & Thun 2009): 25-year cycle, about six years "
                  "to become productive, production declining after about 19 years",
    },
    "coconut": {
        "tokens": ("coconut", "copra"),
        "immature_years": 5,
        "productive_years": 37,
        "lifetime_years": 42,
        "biomass_class": None,
        "source": "Life cycle assessment of coconut plantation, copra, and charcoal production, "
                  "Global J. Environ. Sci. Manage. (2023), doi:10.22034/gjesm.2023.04.01: tall "
                  "coconut, 42-year cycle, nuts harvested since the sixth year of planting",
    },
    "citrus": {
        "tokens": ("citrus", "orange", "tangerine", "mandarin", "lemon", "lime fruit",
                   "grapefruit"),
        "exclude": ("potato",),            # "orange-fleshed sweet potato" is not citrus
        "immature_years": 3,
        "productive_years": 22,
        "lifetime_years": 25,
        "biomass_class": None,
        "source": "Bessou et al. (2014) LCA Food 2014, San Francisco (agritrop.cirad.fr/591337): "
                  "small citrus orchard, non-productive years 0-3, orchard assumed to last 25 years",
    },
    "mango": {
        "tokens": ("mango",),
        "immature_years": 3,
        "productive_years": 17,
        "lifetime_years": 20,
        "biomass_class": None,
        "source": "European Forest Institute Land-use Planner, 'Mango, Tolima, Colombia' (2021, "
                  "UPRA 2020): first harvest year 4, last harvest year 20, then replanted",
    },
    "plantain": {
        "tokens": ("plantain", "banana"),
        "immature_years": 0,
        "productive_years": 5,
        "lifetime_years": 5,
        "biomass_class": None,
        "source": "European Forest Institute Land-use Planner, 'Plantain, South and Central "
                  "Cameroon' (2020, S. Blomme field work 2018): first harvest year 1, last "
                  "harvest year 5, then replanted",
    },
}

# Rust land-occupation substance key -> permanent-crop key (flowmap.ONFARM_FLOWS)
LAND_OCC_ANNUAL = "land_occ"
LAND_OCC_PERMANENT = "land_occ_perm"


def perennial_for(crop_name) -> dict | None:
    n = str(crop_name or "").lower()
    if not n:
        return None
    for key, p in PERENNIALS.items():
        if any(t in n for t in p["tokens"]) and not any(x in n for x in p.get("exclude", ())):
            return {"crop": key, **p}
    # bare "palm" (e.g. "Palm", "Palm kernels") is oil palm in a West African farm context
    if n.strip() in ("palm", "palms") or n.startswith("palm "):
        return {"crop": "oil palm", **PERENNIALS["oil palm"]}
    return None


def _num(value) -> float | None:
    """float(value), or None when blank / not a number (a None field means 'not given')."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# Crops modelled as ANNUAL whatever the farmer enters as establishment: the seed-sown crops of
# engine/crop_defaults.SEED_RATES, the annual rows of IPCC 2019 Vol 4 Ch 11 Table 11.1A
# (cereals, pulses, tubers, used by african_lca_backend/src/production/field.rs), and the root
# and tuber crops. Cassava is botanically semi-perennial but is harvested within 1-2 years and
# treated as an annual crop by IPCC Table 11.1A and ecoinvent's cassava production datasets.
ANNUAL_TOKENS = ("maize", "corn", "rice", "paddy", "wheat", "barley", "oat", "sorghum", "millet",
                 "fonio", "teff", "groundnut", "peanut", "cowpea", "soy", "bean", "pea", "lentil",
                 "chickpea", "bambara", "sesame", "sunflower", "cotton", "tomato", "pepper",
                 "chilli", "chili", "eggplant", "aubergine", "garden egg", "okra", "cucumber",
                 "melon", "watermelon", "pumpkin", "onion", "cabbage", "lettuce", "carrot",
                 "cassava", "yam", "cocoyam", "taro", "potato", "vegetable")
# Tree crops whose common name contains an annual token ("African locust bean" is Parkia
# biglobosa; "pigeon pea" stays annual-like and is not listed).
ANNUAL_EXCLUDE = ("locust bean", "shea", "kola", "cola nut", "tamarind", "pear", "black pepper")
# foods[].category values (app/production/models.py) that are annual crops in this model.
ANNUAL_CATEGORIES = {"cereals", "legumes", "vegetables", "roots"}


def known_annual(food: dict) -> bool:
    """True when the food is a recognised annual crop (name / crop_type / variety, else its
    category). Table perennials are never annual."""
    food = food or {}
    if perennial_for(food.get("name")) is not None:
        return False
    text = " ".join(str(food.get(k) or "") for k in ("name", "crop_type", "variety")).lower()
    if any(x in text for x in ANNUAL_EXCLUDE):
        return False
    if any(t in text for t in ANNUAL_TOKENS):
        return True
    return str(food.get("category") or "").strip().lower() in ANNUAL_CATEGORIES


def _declared_phases(food: dict) -> tuple[float | None, float | None]:
    est = (food or {}).get("establishment") or {}
    return _num(est.get("immature_years")), _num(est.get("productive_years"))


def establishment_ignored_note(food: dict) -> str | None:
    """Validation warning when establishment years were entered for a known annual crop."""
    immature, productive = _declared_phases(food)
    if immature is None and productive is None:
        return None
    if perennial_for((food or {}).get("name")) is not None or not known_annual(food):
        return None
    return (f"validation warning: establishment years entered for '{food.get('name')}' ignored: "
            f"it is an annual crop (establishment amortisation, permanent-crop land and "
            f"perennial residue turnover apply to perennial crops only, PAS 2050-1:2012)")


def perennial_for_food(food: dict) -> dict | None:
    """Perennial spec of a food: the table entry for its name, else a farmer-declared
    perennial when foods[].establishment gives both immature_years and productive_years and
    the crop is not a known annual (known_annual)."""
    p = perennial_for((food or {}).get("name"))
    if p is not None:
        return p
    immature, productive = _declared_phases(food)
    if immature is None or productive is None or productive <= 0 or known_annual(food):
        return None
    return {"crop": str(food.get("name") or "crop").strip().lower(), "tokens": (),
            "immature_years": immature, "productive_years": productive,
            "lifetime_years": immature + productive, "biomass_class": None,
            "source": "farmer-declared establishment phase (foods[].establishment)"}


def establishment_factor(food: dict) -> tuple[float, dict | None, str | None]:
    """(factor, perennial spec, note) for one food. factor = 1 for annual crops."""
    p = perennial_for_food(food)
    if p is None:
        return 1.0, None, establishment_ignored_note(food)
    est = food.get("establishment") or {}
    immature = _num(est.get("immature_years"))
    productive = _num(est.get("productive_years"))
    share = _num(est.get("input_share"))
    immature = p["immature_years"] if immature is None else immature
    productive = p["productive_years"] if productive is None else productive
    share = 1.0 if share is None else share
    if productive <= 0:
        return 1.0, p, None
    factor = (immature * share + productive) / productive
    farmer = [k for k in ("immature_years", "productive_years", "input_share")
              if _num(est.get(k)) is not None]
    basis = f"farmer-entered {', '.join(farmer)}; " if farmer else ""
    note = (f"{p['crop']} treated as a perennial: {immature:g} establishment years amortised "
            f"over {productive:g} productive years (factor {factor:.3f}; establishment-year "
            f"input share {share:g}, screening assumption; {basis}{p['source']}; "
            f"PAS 2050-1:2012)")
    return factor, p, note


def single_perennial(assessment: dict) -> tuple[float, dict | None, str | None]:
    """Establishment factor for a single-crop product system. Multi-crop assessments are
    split per crop by engine/service.py before reaching here; if several foods remain
    (no areas), perennial amortisation is skipped with a note."""
    foods = assessment.get("foods") or []
    if len(foods) != 1:
        if any(perennial_for_food(f) for f in foods):
            return 1.0, None, ("perennial establishment not amortised: several crops share "
                               "one product system without crop areas")
        return 1.0, None, None
    return establishment_factor(foods[0])


def scale_purchased_inputs(inputs: list[dict], assessment: dict) -> tuple[list[dict], list[str]]:
    """Scale purchased-input amounts of a perennial product system by its establishment
    factor (establishment-year inputs amortised over the productive years)."""
    factor, p, note = single_perennial(assessment)
    if p is None or factor == 1.0:
        return inputs, ([note] if note else [])
    out = []
    for i in inputs:
        j = dict(i)
        try:
            j["amount"] = float(i["amount"]) * factor
        except (KeyError, TypeError, ValueError):
            pass
        j["establishment_factor"] = factor
        out.append(j)
    return out, [f"purchased inputs scaled by the {p['crop']} establishment factor {factor:.3f}"]


def apply_to_field_flows(flows: list[dict], assessment: dict) -> tuple[list[dict], list[str]]:
    """Scale on-farm flows by the establishment factor and report land as permanent crop."""
    factor, p, note = single_perennial(assessment)
    if p is None:
        # the ignored-establishment warning is already emitted by scale_purchased_inputs
        return flows, []
    notes = [note] if note else []
    out = []
    for f in flows:
        g = dict(f)
        g["quantity"] = (g.get("quantity") or 0.0) * factor
        if g.get("substance") == LAND_OCC_ANNUAL:
            g["substance"] = LAND_OCC_PERMANENT
        out.append(g)
    if factor != 1.0:
        notes.append(f"field model notes quote mature-year (unamortised) amounts; every on-farm "
                     f"flow was then multiplied by the {p['crop']} establishment factor "
                     f"{factor:.3f}")
    notes.append(f"{p['crop']} land occupation reported as 'Occupation, permanent crop'")
    return out, notes
