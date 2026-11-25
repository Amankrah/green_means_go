#!/usr/bin/env python3
"""
pesticides.py: pesticide inventory for the farm path.

Two flows per application, both in kg of ACTIVE INGREDIENT (AI):
  1. Production: the AI's chemical-class dataset (ecoinvent pesticide datasets are per kg
     AI), e.g. glyphosate -> "market for glyphosate", lambda-cyhalothrin -> "market for
     pyrethroid-compound". An AI that is not in the table is modelled with the WFLDB
     class mix for its pesticide_type and crop group ("Herbicide, unspecified, mix for maize
     crops, at plant"), else "market for pesticide, unspecified".
  2. Field emission: the applied AI as ELEMENTARY flows so the USEtox-based toxicity
     categories of the LCIA method pick it up. Split by method:
       * ecoinvent / AGRIBALYSE convention (default, ReCiPe and every non-EF method): 100% to
         agricultural soil. Nemecek T., Kaegi T. (2007) Life Cycle Inventories of Swiss and
         European Agricultural Production Systems, ecoinvent report No. 15, s.3.9; Koch P.,
         Salou T. (2020) AGRIBALYSE v3.0 methodology report, ADEME.
       * EF methods: 90% agricultural soil, 9% air, 1% (surface) water. Commission
         Recommendation (EU) 2021/2279 Annex I (PEF method), agricultural modelling rules;
         the same default as EC (2018) PEFCR Guidance v6.3.

AI mass = product rate (kg or L product / ha / application) x applications per season x
sum over the crops it is applied to of (area x crops_per_year). AI content is the user's
value, else the typical formulation strength of that AI (the number in the product code,
e.g. "Glyphosate 360 SL" = 360 g AI per litre), else 1.0 (conservative upper bound, warned).
Biological / botanical products (Bio-pesticide, Organic-approved) whose AI is not in the
table are NOT treated as synthetic AI: no production dataset represents them, so they are
excluded and disclosed.

The flow mapping lives here (PESTICIDE_FLOWS), not in engine/flowmap.py.
"""
from __future__ import annotations

import re

# Notes carrying this prefix are lifted into data_quality.warnings (engine/service.py).
WARNING_PREFIX = "validation warning: "

EMISSION_FRACTION_SOIL = 1.0
EMISSION_SOURCE = ("Nemecek & Kaegi (2007) ecoinvent report No. 15, s.3.9; AGRIBALYSE 3.0 "
                   "methodology (Koch & Salou 2020): 100% of applied active ingredient to "
                   "agricultural soil")
# PEF/EF split: (compartment candidates in preference order, fraction)
PEF_SPLIT = (
    (("Elementary flows/Emission to soil/agricultural",), 0.90),
    (("Elementary flows/Emission to air/low population density",
      "Elementary flows/Emission to air/unspecified"), 0.09),
    (("Elementary flows/Emission to water/surface water",
      "Elementary flows/Emission to water/fresh water",
      "Elementary flows/Emission to water/unspecified"), 0.01),
)
PEF_SOURCE = ("Commission Recommendation (EU) 2021/2279 Annex I (PEF method), agricultural "
              "modelling rules; EC (2018) PEFCR Guidance v6.3: pesticide active ingredient "
              "90% to agricultural soil, 9% to air, 1% to water")
FORMULATION_SOURCE = ("typical registered formulation strength as encoded in the product code "
                      "(FAO/WHO JMPS formulation conventions, e.g. '360 SL' = 360 g AI/L); "
                      "replace with the label value")
SOIL_COMPARTMENT = "Elementary flows/Emission to soil/agricultural"
# Liquid formulations are entered in L; their mass for inbound transport is taken at 1 kg/L
# (water density, engine/units.FUELS["water"]); a screening approximation, disclosed.
LIQUID_PRODUCT_KG_PER_L = 1.0

# canonical AI -> (elementary flow name in the store, production dataset, typical kg AI per
#                  kg-or-L of product, formulation label)
# Every flow name below exists in the canonical store with agricultural-soil, air and
# surface-water flows carrying ReCiPe 2016 / EF 3.1 toxicity CFs (checked 2026-11-25; USEtox
# 2.14 reference values in engine/lcia_reference/usetox_pesticide_cfs.json).
PESTICIDE_FLOWS = {
    "glyphosate": ("Glyphosate", "market for glyphosate", 0.360, "360 SL"),
    "paraquat": ("Paraquat", "market for bipyridylium-compound", 0.200, "200 SL"),
    "diquat": ("Diquat", "market for bipyridylium-compound", 0.200, "200 SL"),
    "atrazine": ("Atrazine", "market for atrazine", 0.500, "500 SC"),
    "2,4-d": ("2,4-D", "market for phenoxy-compound", 0.720, "720 SL (amine salt)"),
    "mcpa": ("MCPA", "market for phenoxy-compound", 0.500, "500 SL"),
    "metolachlor": ("Metolachlor", "market for metolachlor", 0.960, "960 EC"),
    "acetochlor": ("Acetochlor", "market for acetamide-anillide-compound, unspecified", 0.900, "900 EC"),
    "butachlor": ("Butachlor", "market for acetamide-anillide-compound, unspecified", 0.600, "600 EC"),
    "alachlor": ("Alachlor", "market for acetamide-anillide-compound, unspecified", 0.480, "480 EC"),
    "propanil": ("Propanil", "market for acetamide-anillide-compound, unspecified", 0.360, "360 EC"),
    "pendimethalin": ("Pendimethalin", "market for dinitroaniline-compound", 0.330, "330 EC"),
    "nicosulfuron": ("Nicosulfuron", "market for [sulfonyl]urea-compound", 0.040, "40 OD"),
    "lambda-cyhalothrin": ("Lambda-cyhalothrin", "market for pyrethroid-compound", 0.025, "2.5 EC"),
    "cypermethrin": ("Cypermethrin", "market for pyrethroid-compound", 0.100, "100 EC"),
    "deltamethrin": ("Deltamethrin", "market for pyrethroid-compound", 0.025, "25 EC"),
    "chlorpyrifos": ("Chlorpyrifos", "market for organophosphorus-compound, unspecified", 0.480, "480 EC"),
    "dimethoate": ("Dimethoate", "market for organophosphorus-compound, unspecified", 0.400, "400 EC"),
    "profenofos": ("Profenofos", "market for organophosphorus-compound, unspecified", 0.500, "500 EC"),
    "acephate": ("Acephate", "market for organophosphorus-compound, unspecified", 0.750, "75 SP"),
    "imidacloprid": ("Imidacloprid", "market for cyclic N-compound", 0.200, "200 SL"),
    "thiamethoxam": ("Thiamethoxam", "market for cyclic N-compound", 0.250, "25 WG"),
    "acetamiprid": ("Acetamiprid", "market for cyclic N-compound", 0.200, "20 SP"),
    "chlorantraniliprole": ("Chlorantraniliprole", "market for pesticide, unspecified", 0.200, "200 SC"),
    # Emamectin benzoate: EF 3.1 characterises it; ReCiPe 2016 has no CF for this flow.
    "emamectin benzoate": ("Emamectin benzoate", "market for pesticide, unspecified", 0.019, "1.9 EC"),
    "abamectin": ("Abamectin", "market for pesticide, unspecified", 0.018, "1.8 EC"),
    "mancozeb": ("Mancozeb", "market for mancozeb", 0.800, "80 WP"),
    "chlorothalonil": ("Chlorothalonil", "market for chlorothalonil", 0.500, "500 SC"),
    "carbendazim": ("Carbendazim", "market for benzimidazole-compound", 0.500, "500 SC"),
    "tebuconazole": ("Tebuconazole", "market for pesticide, unspecified", 0.250, "250 EW"),
    "propiconazole": ("Propiconazole", "market for pesticide, unspecified", 0.250, "250 EC"),
    "carbofuran": ("Carbofuran", "market for [thio]carbamate-compound", 0.030, "3 GR"),
    # Copper fungicides: the emitted substance is the copper ion; content = metallic Cu
    # share stated on labels ("50% metallic copper" for Cu(OH)2 77 WP and oxychloride 85 WP).
    # The store's "Copper" and "Copper ion" soil flows carry identical ReCiPe/EF CFs.
    "copper": ("Copper", "market for copper oxide", 0.500, "50% metallic Cu"),
    # The store has no "Metalaxyl" flow; metalaxyl-M (the active R-enantiomer of the racemate)
    # is its proxy (disclosed in the row note).
    "metalaxyl": ("Metalaxyl-M", "market for pesticide, unspecified", 0.350, "35 WS"),
    # Botanical: the Azadirachtin flow is characterised, but no production dataset exists and
    # neem formulations range widely in strength, so only a label content is accepted.
    "azadirachtin": ("Azadirachtin", None, None, "label strength required"),
}
_FLOW_PROXY_NOTE = {"metalaxyl": "flow 'Metalaxyl-M' used for metalaxyl (racemate) emissions"}

_SYNONYMS = {
    "lambda cyhalothrin": "lambda-cyhalothrin", "lambdacyhalothrin": "lambda-cyhalothrin",
    "s-metolachlor": "metolachlor", "2,4 d": "2,4-d",
    "2-4-d": "2,4-d", "24-d": "2,4-d",
    "copper hydroxide": "copper", "copper oxychloride": "copper", "cuprous oxide": "copper",
    "emamectin": "emamectin benzoate", "mefenoxam": "metalaxyl", "metalaxyl-m": "metalaxyl",
    "neem": "azadirachtin",
}
# Single-AI trade names (word-matched in brand_name and in the AI text). Multi-AI products
# (e.g. Ridomil Gold = metalaxyl-M + mancozeb) are deliberately absent: one AI would hide
# the other.
_BRANDS = {
    "karate": "lambda-cyhalothrin", "roundup": "glyphosate", "gramoxone": "paraquat",
    "cymbush": "cypermethrin", "decis": "deltamethrin", "dursban": "chlorpyrifos",
    "confidor": "imidacloprid", "actara": "thiamethoxam", "mospilan": "acetamiprid",
    "orthene": "acephate", "proclaim": "emamectin benzoate", "vertimec": "abamectin",
    "dithane": "mancozeb", "kocide": "copper", "bravo": "chlorothalonil", "tilt": "propiconazole",
    "folicur": "tebuconazole", "furadan": "carbofuran", "stomp": "pendimethalin",
    "lasso": "alachlor", "weedone": "2,4-d",
}

GENERIC_DATASET = "market for pesticide, unspecified"

# pesticide_type -> WFLDB class word ("Herbicide, unspecified, mix for <group>, at plant").
_CLASS_WORD = {"herbicide": "Herbicide", "insecticide": "Insecticide", "fungicide": "Fungicide"}
# WFLDB crop groups available for each class (store check 2026-11-25).
_CLASS_GROUPS = {
    "Herbicide": {"cereal crops", "citrus", "fruit tree", "maize crops", "oil seed crops",
                  "sugar beet", "vegetables"},
    "Insecticide": {"cereal crops", "citrus", "fruit tree", "grapes and wine", "maize crops",
                    "oil seed crops", "sugar beet", "vegetables"},
    "Fungicide": {"cereal crops", "citrus", "fruit tree", "maize crops", "oil seed crops",
                  "sugar beet", "vegetables"},
}
CLASS_SOURCE = ("WFLDB (Nemecek et al. 2019, World Food LCA Database v3.5) class mix 'unspecified, "
                "mix for <crop group>, at plant', per kg active ingredient")
_BIO_TYPES = ("bio-pesticide", "biopesticide", "organic-approved", "organic approved", "botanical")
_BIO_WORDS = ("bacillus", "beauveria", "metarhizium", "trichoderma", "baculovirus", "neem",
              "azadirachtin", "pyrethrum extract", "garlic", "chilli extract", "pepper extract")


def _word_hit(word: str, text: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", text) is not None


def canonical_ai(text: str | None, brand: str | None = None) -> str | None:
    """Canonical AI key from the active-ingredient text, then from the brand name (the
    wizard's second key). Synonyms and the AI table are substring-matched in the AI text;
    trade names are word-matched in both."""
    for src, allow_substring in ((text, True), (brand, False)):
        low = (src or "").strip().lower()
        if not low:
            continue
        if allow_substring:
            for syn, key in sorted(_SYNONYMS.items(), key=lambda kv: -len(kv[0])):
                if syn in low:
                    return key
            for key in sorted(PESTICIDE_FLOWS, key=len, reverse=True):
                if key in low:
                    return key
        else:
            hit = canonical_ai(low)
            if hit:
                return hit
        for b, key in _BRANDS.items():
            if _word_hit(b, low):
                return key
    return None


def _crop_group(food: dict | None) -> str | None:
    """WFLDB crop group for a food, from its name then category; None when no group fits."""
    if not food:
        return None
    name = (food.get("name") or "").lower()
    cat = (food.get("category") or "").lower()
    if "maize" in name or "corn" in name:
        return "maize crops"
    if any(w in name for w in ("orange", "citrus", "lemon", "lime", "mandarin", "grapefruit")):
        return "citrus"
    if any(w in name for w in ("grape", "vine")):
        return "grapes and wine"
    if "cereal" in cat or any(w in name for w in ("rice", "sorghum", "millet", "wheat", "barley", "fonio")):
        return "cereal crops"
    if "vegetable" in cat:
        return "vegetables"
    if "fruit" in cat:
        return "fruit tree"
    if any(w in cat for w in ("oil", "legume", "nut")):
        return "oil seed crops"
    return None


def class_dataset(pesticide_type: str | None, food: dict | None) -> str | None:
    """WFLDB class-mix production dataset for an unknown AI of a known class, or None."""
    word = _CLASS_WORD.get((pesticide_type or "").strip().lower())
    group = _crop_group(food)
    if not word or not group or group not in _CLASS_GROUPS[word]:
        return None
    return f"{word}, unspecified, mix for {group}, at plant"


def _is_bio(p: dict, ai_text: str) -> bool:
    t = (p.get("pesticide_type") or "").lower()
    low = ai_text.lower()
    return any(b in t for b in _BIO_TYPES) or any(w in low for w in _BIO_WORDS)


def _scope(assessment: dict, crop_ids, total_area: float) -> tuple[float, dict | None]:
    """(sum of area x crops_per_year over the crops a row applies to, first such food).
    Without foods (direct callers) the given total_area is used as one season."""
    try:
        from .inputs import crop_scope
    except ImportError:
        from inputs import crop_scope  # type: ignore
    foods = assessment.get("foods") or []
    if not foods:
        return float(total_area or 0.0), None
    area_seasons, _area, picked = crop_scope(assessment, crop_ids, per_season=True)
    return area_seasons, (picked[0] if picked else None)


def applications(assessment: dict, total_area: float) -> tuple[list[dict], list[str]]:
    """Resolve every pesticide application to AI mass. Returns (rows, notes); each row:
    {ai_text, ai_key, kg_product, kg_ai, content, content_source, dataset, flow_name}.
    rate x applications_per_season x sum(area x crops_per_year) over the row's crop_ids
    (all crops when blank); 0 applications means 0."""
    mp = assessment.get("management_practices") or {}
    pm = mp.get("pest_management") or {}
    if isinstance(pm, list):
        pests = pm
    elif isinstance(pm, dict):
        # tolerate the wizard's legacy key when the dict did not pass through the API model
        pests = pm.get("pesticides") or pm.get("pesticides_used") or []
    else:
        pests = []
    rows, notes = [], []
    for p in pests:
        if not isinstance(p, dict):
            continue
        label = (p.get("active_ingredient") or p.get("pesticide_type") or "pesticide").strip()
        rate = p.get("application_rate") or 0
        n = p.get("applications_per_season")
        if n is None:
            n = 1                      # not stated: one application
        if rate < 0 or n < 0:
            # Rejected by the API model; defend the engine anyway (a negative rate would
            # otherwise be dropped silently or, in the kernel, become a credit).
            notes.append(f"{WARNING_PREFIX}pesticide '{label}': negative rate or application "
                         "count set to zero")
            rate, n = max(rate, 0), max(n, 0)
        if n == 0:
            notes.append(f"pesticide '{label}': 0 applications per season; not counted")
            continue
        area_seasons, food = _scope(assessment, p.get("crop_ids") or [], total_area)
        kg_product = rate * n * area_seasons
        if kg_product <= 0:
            if rate and not area_seasons:
                if p.get("crop_ids") and (assessment.get("foods") or []):
                    notes.append(f"pesticide '{label}': applied to crops {p.get('crop_ids')} only; "
                                 "none of them is in this product system")
                else:
                    notes.append(f"{WARNING_PREFIX}pesticide '{label}' reported but no crop area: "
                                 "cannot scale it, so it is NOT counted")
            continue
        ai_text = (p.get("active_ingredient") or p.get("pesticide_type") or "pesticide").strip()
        key = canonical_ai(ai_text, p.get("brand_name"))
        spec = PESTICIDE_FLOWS.get(key) if key else None
        bio = _is_bio(p, ai_text)
        content = p.get("active_ingredient_content")
        dataset = flow_name = None
        if spec:
            flow_name, dataset = spec[0], spec[1]
            if content is not None and 0 < content <= 1.0:
                csrc = "farmer (label)"
            elif spec[2] is not None:
                content, csrc = spec[2], f"{FORMULATION_SOURCE}: {spec[3]}"
            else:
                notes.append(f"pesticide '{ai_text}': {key} strength varies widely between products; "
                             "enter the label active-ingredient content. Not counted.")
                continue
            if dataset is None:
                notes.append(f"pesticide '{ai_text}': no production dataset for {key} (botanical); "
                             "only its field emission is inventoried")
            if key in _FLOW_PROXY_NOTE:
                notes.append(f"pesticide '{ai_text}': {_FLOW_PROXY_NOTE[key]}")
        elif bio:
            notes.append(f"pesticide '{ai_text}' ({p.get('pesticide_type')}): biological / botanical "
                         "product with no representative dataset; its product mass is NOT counted as "
                         "synthetic active ingredient, so it is excluded (disclosed)")
            continue
        else:
            if content is not None and 0 < content <= 1.0:
                csrc = "farmer (label)"
            else:
                content, csrc = 1.0, "unknown formulation: product mass counted as AI (conservative upper bound)"
                notes.append(f"pesticide '{ai_text}': active-ingredient content unknown; product mass "
                             "counted as active ingredient (conservative). Enter the label strength.")
            dataset = class_dataset(p.get("pesticide_type"), food)
            if dataset:
                notes.append(f"pesticide '{ai_text}' not in the active-ingredient table: production "
                             f"modelled with the {p.get('pesticide_type')} class mix '{dataset}' "
                             f"({CLASS_SOURCE}); no field emission flow, so its toxicity is not "
                             "characterised")
            else:
                dataset = GENERIC_DATASET
                notes.append(f"pesticide '{ai_text}' not in the active-ingredient table: production "
                             "modelled with 'pesticide, unspecified' and no soil emission flow, so its "
                             "toxicity is not characterised")
        rows.append({
            "ai_text": ai_text, "ai_key": key, "kg_product": kg_product,
            "kg_ai": kg_product * content, "content": content, "content_source": csrc,
            "dataset": dataset, "flow_name": flow_name,
            "pesticide_type": p.get("pesticide_type"), "brand_name": p.get("brand_name"),
        })
    return rows, notes


def purchased_inputs(rows: list[dict]) -> list[dict]:
    """Production of each AI (kg AI) for the supply-chain solver. product_kg (formulated
    product, L counted at 1 kg/L) is what is transported to the farm."""
    out = []
    for r in rows:
        if not r.get("dataset"):
            continue
        inp = {"name": r["ai_text"], "match_as": r["dataset"], "amount": r["kg_ai"],
               "unit": "kg", "kind": "pesticide", "active_ingredient": r["ai_key"],
               "ai_content": r["content"], "ai_content_source": r["content_source"],
               "product_kg": r["kg_product"] * LIQUID_PRODUCT_KG_PER_L}
        if r["dataset"] != GENERIC_DATASET and not r.get("ai_key"):
            inp["fallbacks"] = [GENERIC_DATASET]
        out.append(inp)
    return out


def _resolve_flow(conn, flow_name: str, compartment: str) -> tuple[str, str] | None:
    row = conn.execute(
        "SELECT f.uid, f.name, (SELECT COUNT(*) FROM characterization_factors cf "
        "WHERE cf.flow_uid = f.uid) AS n FROM flows f WHERE f.flow_type = 'ELEMENTARY_FLOW' "
        "AND lower(f.name) = lower(?) AND f.category = ? ORDER BY n DESC LIMIT 1",
        (flow_name, compartment)).fetchone()
    if not row:
        return None
    return row[0], row[1]


def resolve_soil_flow(conn, flow_name: str) -> tuple[str, str] | None:
    """(uid, name) of the agricultural-soil emission flow for an AI, preferring the flow
    with the most characterisation factors (the ecoinvent 3.11 flow in the store)."""
    return _resolve_flow(conn, flow_name, SOIL_COMPARTMENT)


def emission_split(method: str | None) -> tuple[tuple, str]:
    """(compartment split, source) for the LCIA method: PEF 90/9/1 for EF methods, else
    100% agricultural soil."""
    if method and str(method).strip().upper().startswith("EF"):
        return PEF_SPLIT, PEF_SOURCE
    return (((SOIL_COMPARTMENT,), EMISSION_FRACTION_SOIL),), EMISSION_SOURCE


_COMPARTMENT_LABEL = {"soil": "soil, agricultural", "air": "air", "water": "water"}


def field_emission_flows(conn, rows: list[dict], method: str | None = None) -> tuple[list[dict], list[str]]:
    """Elementary flows {uid, name, unit, amount} for the applied AI, split by compartment
    per emission_split(method)."""
    split, source = emission_split(method)
    flows, notes = [], []
    for r in rows:
        if not r.get("flow_name"):
            continue
        for compartments, frac in split:
            hit = next((h for h in (_resolve_flow(conn, r["flow_name"], c) for c in compartments) if h), None)
            if not hit:
                notes.append(f"no {compartments[0].split('/')[-2].lower()} flow for '{r['flow_name']}' "
                             f"in the store; that share ({frac:.0%}) of its field emission is not "
                             "characterised")
                continue
            comp = compartments[0].split("/")[1].replace("Emission to ", "")
            flows.append({"uid": hit[0], "name": f"{hit[1]} ({_COMPARTMENT_LABEL.get(comp, comp)})",
                          "unit": "kg", "amount": r["kg_ai"] * frac, "source": source})
    return flows, notes
