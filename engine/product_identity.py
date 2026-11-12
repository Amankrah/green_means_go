#!/usr/bin/env python3
"""
product_identity.py: the product-identity gate the matcher applies BEFORE region preference.

Why: the orchestrator ranks matcher candidates by region fit first and similarity second.
Without an identity check, any in-region dataset that clears the similarity floor wins, so
an unknown raw material in Ghana ("Eggplant", "Raw honey", "Bio-fertilizer") resolved to the
Ghana cocoa dataset. The gate makes a candidate prove it is the same PRODUCT as the query
(controlled synonym table below) before region preference is allowed to choose among them.

How it works
  1. `detect(text)` finds controlled-vocabulary concepts in a text by whole-word matching
     (optional plural "s"/"es"), longest term first, so "cocoa butter" is the concept
     cocoa_butter (not cocoa), "urea ammonium nitrate" is UAN (not urea), "chilli" does not
     fire on "chilling" and "rape" does not fire on "grape".
  2. `query_identity(query)` returns the concepts the candidate must satisfy:
       basis "concept": specific concepts found; every one must be satisfied
       basis "proxy":   only proxy concepts (e.g. foliar fertiliser -> NPK); flagged
       basis "generic": only a generic family word ("fertiliser"); any member of the family
                        passes, flagged
       basis "token":   no concept known; the candidate must share a content word (head-noun
                        fallback, plural-insensitive)
  3. `candidate_concepts(name, reference_product)` reads the candidate's REFERENCE PRODUCT
     (ecoinvent: the product after "|"; Agribalyse: the name). For service activities
     (waste treatment, transport) the activity name carries the identity, so concepts of
     those families are also read from the name. This stops "palm oil mill operation |
     palm kernel meal" passing as crude palm oil.
  4. `passes(identity, cand_concepts, cand_text)` is the gate.

The synonym table is a controlled vocabulary for West African and Canadian crops, fuels,
fertilisers, packaging, waste and transport. Synonyms follow FAO crop nomenclature (FAOSTAT
item list / ICC 1.1) and common West African usage (MoFA Ghana: "garden egg" for African
eggplant, "pepper" for hot chilli pepper). Proxy acceptances are LCA judgement calls and are
always flagged needs_review so a human confirms them:
  - foliar fertiliser -> NPK compound datasets (foliar feeds are water-soluble NPK blends)
  - bio-fertiliser -> organic fertiliser / compost / manure datasets (no inoculant dataset)
  - biodiesel -> diesel combustion in machinery (no biodiesel-combustion dataset; the store
    has FAME production per kg only, which omits combustion and mismatches an MJ amount)
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# --------------------------------------------------------------------------------------
# Controlled vocabulary.  concept_id -> spec
#   terms:   phrases that denote the concept (singular; plural "s"/"es" is implicit)
#   family:  product family (crop, refined, fertiliser, fuel, energy, packaging, pesticide,
#            water, waste, transport, animal)
#   generic: True for a bare family word ("fertiliser"): satisfied by ANY concept of that
#            family, and the match is flagged needs_review
#   accept:  for proxy concepts, the concept ids that satisfy it (flagged needs_review)
# --------------------------------------------------------------------------------------
_C: dict[str, dict] = {
    # ---- field crops / farm-gate products (FAO crop nomenclature + West African usage) ----
    "maize": {"family": "crop", "terms": ["maize", "corn", "maize grain", "corn grain"]},
    "wheat": {"family": "crop", "terms": ["wheat", "wheat grain"]},
    "rice": {"family": "crop", "terms": ["rice", "paddy", "paddy rice"]},
    "soybean": {"family": "crop", "terms": ["soybean", "soya bean", "soy bean", "soya", "soy"]},
    "sorghum": {"family": "crop", "terms": ["sorghum", "sorghum grain", "guinea corn"]},
    "sweet_sorghum": {"family": "crop", "terms": ["sweet sorghum"]},
    "millet": {"family": "crop", "terms": ["millet", "pearl millet", "finger millet"]},
    "barley": {"family": "crop", "terms": ["barley"]},
    "oat": {"family": "crop", "terms": ["oat"]},
    "potato": {"family": "crop", "terms": ["potato", "irish potato"]},
    "sweet_potato": {"family": "crop", "terms": ["sweet potato"]},
    "cassava": {"family": "crop", "terms": ["cassava", "manioc", "tapioca root"]},
    "yam": {"family": "crop", "terms": ["yam"]},
    "plantain": {"family": "crop", "terms": ["plantain"]},
    "banana": {"family": "crop", "terms": ["banana"]},
    "cocoa": {"family": "crop", "terms": ["cocoa", "cacao", "cocoa bean"]},
    "coffee": {"family": "crop", "terms": ["coffee", "coffee bean", "green coffee"]},
    "tea": {"family": "crop", "terms": ["tea"]},
    "groundnut": {"family": "crop", "terms": ["groundnut", "peanut", "arachis", "ground nut",
                                              "peanut in shell"]},
    "oil_palm_fruit": {"family": "crop", "terms": ["oil palm", "ffb", "fresh fruit bunch",
                                                   "palm fruit bunch", "palm fruit",
                                                   "oil palm fruit", "palm bunch"]},
    "palm_kernel": {"family": "refined", "terms": ["palm kernel", "palm kernel meal",
                                                   "palm kernel oil", "palm kernel expeller"]},
    "sugarcane": {"family": "crop", "terms": ["sugarcane", "sugar cane"]},
    "sugar_beet": {"family": "crop", "terms": ["sugar beet"]},
    "sunflower": {"family": "crop", "terms": ["sunflower", "sunflower seed"]},
    "rapeseed": {"family": "crop", "terms": ["rapeseed", "rape seed", "rape", "canola"]},
    "sesame": {"family": "crop", "terms": ["sesame", "sesame seed", "benniseed", "beniseed",
                                           "simsim"]},
    "seed_cotton": {"family": "crop", "terms": ["seed cotton", "cotton", "raw cotton"]},
    "cottonseed": {"family": "crop", "terms": ["cottonseed", "cotton seed"]},
    "cotton_fibre": {"family": "refined", "terms": ["cotton fibre", "cotton fiber",
                                                    "fibre cotton", "fiber cotton",
                                                    "cotton lint", "lint cotton"]},
    "tomato": {"family": "crop", "terms": ["tomato"]},
    "onion": {"family": "crop", "terms": ["onion", "shallot"]},
    "cabbage": {"family": "crop", "terms": ["cabbage"]},
    "carrot": {"family": "crop", "terms": ["carrot"]},
    "eggplant": {"family": "crop", "terms": ["eggplant", "aubergine", "brinjal", "garden egg",
                                             "african eggplant"]},
    "cucumber": {"family": "crop", "terms": ["cucumber"]},
    # West African usage: bare "pepper" is the hot chilli pepper (MoFA Ghana crop lists).
    "chilli": {"family": "crop", "terms": ["chilli", "chili", "chile pepper", "chilli pepper",
                                           "chili pepper", "hot pepper", "pepper",
                                           "scotch bonnet", "bird eye pepper"]},
    "bell_pepper": {"family": "crop", "terms": ["bell pepper", "sweet pepper", "capsicum"]},
    "black_pepper": {"family": "crop", "terms": ["black pepper", "white pepper",
                                                 "peppercorn"]},
    "okra": {"family": "crop", "terms": ["okra", "okro", "lady finger"]},
    "fava_bean": {"family": "crop", "terms": ["fava bean", "faba bean", "broad bean"]},
    "pea": {"family": "crop", "terms": ["pea", "protein pea", "field pea", "dry pea"]},
    "cowpea": {"family": "crop", "terms": ["cowpea", "black eyed pea", "niebe"]},
    "bean": {"family": "crop", "terms": ["bean", "common bean", "kidney bean", "dry bean",
                                         "pinto bean"]},
    "orange": {"family": "crop", "terms": ["orange", "sweet orange"]},
    "lemon": {"family": "crop", "terms": ["lemon"]},
    "mandarin": {"family": "crop", "terms": ["mandarin", "tangerine", "clementine",
                                             "satsuma"]},
    "grapefruit": {"family": "crop", "terms": ["grapefruit", "pomelo"]},
    "citrus": {"family": "crop", "terms": ["citrus", "citrus fruit"],
               "accept": ["orange", "lemon", "mandarin", "grapefruit"]},
    "grape": {"family": "crop", "terms": ["grape", "table grape", "wine grape"]},
    "apple": {"family": "crop", "terms": ["apple"]},
    "pear": {"family": "crop", "terms": ["pear"]},
    "pineapple": {"family": "crop", "terms": ["pineapple"]},
    "mango": {"family": "crop", "terms": ["mango"]},
    "cashew": {"family": "crop", "terms": ["cashew", "cashew nut"]},
    "shea": {"family": "crop", "terms": ["shea", "shea nut", "shea kernel"]},
    "coconut": {"family": "crop", "terms": ["coconut", "copra"]},
    "honey": {"family": "animal", "terms": ["honey", "honeycomb", "raw honey"]},
    # ---- refined / intermediate ingredients (targets of REFINED_MATERIAL_HINTS) ----
    "wheat_flour": {"family": "refined", "terms": ["wheat flour"]},
    "maize_flour": {"family": "refined", "terms": ["maize flour", "corn flour", "maize meal",
                                                   "cornmeal", "corn meal"]},
    "soybean_flour": {"family": "refined", "terms": ["soybean flour", "soy flour",
                                                     "soya flour"]},
    "millet_flour": {"family": "refined", "terms": ["millet flour"]},
    "starch": {"family": "refined", "terms": ["starch", "maize starch", "wheat starch",
                                              "potato starch", "corn starch"]},
    "palm_oil": {"family": "refined", "terms": ["palm oil", "crude palm oil", "cpo",
                                                "palm oil crude"]},
    "soybean_oil": {"family": "refined", "terms": ["soybean oil", "soya oil", "soy oil"]},
    "rapeseed_oil": {"family": "refined", "terms": ["rape oil", "rapeseed oil",
                                                    "canola oil"]},
    "sunflower_oil": {"family": "refined", "terms": ["sunflower oil"]},
    "groundnut_oil": {"family": "refined", "terms": ["groundnut oil", "peanut oil",
                                                     "arachis oil"]},
    "cottonseed_oil": {"family": "refined", "terms": ["cottonseed oil", "cotton seed oil"]},
    "cocoa_butter": {"family": "refined", "terms": ["cocoa butter"]},
    "cocoa_powder": {"family": "refined", "terms": ["cocoa powder"]},
    "chocolate": {"family": "refined", "terms": ["chocolate", "dark chocolate"]},
    "butter": {"family": "refined", "terms": ["butter"]},
    "peanut_butter": {"family": "refined", "terms": ["peanut butter", "groundnut paste"]},
    "cheese": {"family": "refined", "terms": ["cheese"]},
    "glucose": {"family": "refined", "terms": ["glucose"]},
    "sugar": {"family": "refined", "terms": ["sugar", "cane sugar", "beet sugar"]},
    "molasses": {"family": "refined", "terms": ["molasses"]},
    "soybean_meal": {"family": "refined", "terms": ["soybean meal", "soy meal", "soya meal"]},
    "breadcrumbs": {"family": "refined", "terms": ["breadcrumbs", "breadcrumb"]},
    "margarine": {"family": "refined", "terms": ["margarine"]},
    # ---- fertilisers ----
    "fertiliser": {"family": "fertiliser", "terms": ["fertiliser", "fertilizer"],
                   "generic": True},
    "npk": {"family": "fertiliser", "terms": ["npk", "compound fertiliser",
                                              "compound fertilizer"]},
    "urea": {"family": "fertiliser", "terms": ["urea"]},
    "uan": {"family": "fertiliser", "terms": ["urea ammonium nitrate", "uan"]},
    "ammonium_nitrate": {"family": "fertiliser", "terms": ["ammonium nitrate"]},
    "can": {"family": "fertiliser", "terms": ["calcium ammonium nitrate", "can"]},
    "ammonium_sulfate": {"family": "fertiliser", "terms": ["ammonium sulfate",
                                                           "ammonium sulphate"]},
    "dap": {"family": "fertiliser", "terms": ["diammonium phosphate", "dap"]},
    "map": {"family": "fertiliser", "terms": ["monoammonium phosphate", "map"]},
    "tsp": {"family": "fertiliser", "terms": ["triple superphosphate",
                                              "triple super phosphate", "tsp"]},
    "ssp": {"family": "fertiliser", "terms": ["single superphosphate",
                                              "single super phosphate", "ssp"]},
    "mop": {"family": "fertiliser", "terms": ["muriate of potash", "potassium chloride",
                                              "potash", "mop", "potassium fertiliser",
                                              "potassium fertilizer"]},
    "sop": {"family": "fertiliser", "terms": ["potassium sulfate", "potassium sulphate",
                                              "sulphate of potash", "sulfate of potash"]},
    "organic_fertiliser": {"family": "fertiliser", "terms": ["organic fertiliser",
                                                             "organic fertilizer"]},
    "compost": {"family": "fertiliser", "terms": ["compost"]},
    "manure": {"family": "fertiliser", "terms": ["manure", "poultry litter",
                                                 "animal manure", "cow dung"]},
    "biofertiliser": {"family": "fertiliser", "terms": ["bio fertilizer", "bio fertiliser",
                                                        "biofertilizer", "biofertiliser"],
                      "accept": ["organic_fertiliser", "compost", "manure"]},
    "foliar_fertiliser": {"family": "fertiliser", "terms": ["foliar fertilizer",
                                                            "foliar fertiliser", "foliar"],
                          "accept": ["npk"]},
    # ---- pesticides ----
    "pesticide": {"family": "pesticide", "terms": ["pesticide", "herbicide", "insecticide",
                                                   "fungicide", "agrochemical",
                                                   "glyphosate"]},
    # ---- fuels and energy ----
    "diesel": {"family": "fuel", "terms": ["diesel", "gas oil", "gasoil"]},
    "biodiesel": {"family": "fuel", "terms": ["biodiesel", "fatty acid methyl ester",
                                              "fame"], "accept": ["diesel"]},
    "petrol": {"family": "fuel", "terms": ["petrol", "gasoline"]},
    "kerosene": {"family": "fuel", "terms": ["kerosene", "paraffin oil"]},
    "lpg": {"family": "fuel", "terms": ["lpg", "liquefied petroleum gas", "propane",
                                        "butane"]},
    "natural_gas": {"family": "fuel", "terms": ["natural gas"]},
    "firewood": {"family": "fuel", "terms": ["firewood", "fuelwood", "fuel wood",
                                             "wood logs", "wood chips"]},
    "charcoal": {"family": "fuel", "terms": ["charcoal"]},
    "biogas": {"family": "fuel", "terms": ["biogas"]},
    "electricity": {"family": "energy", "terms": ["electricity"]},
    "low_voltage": {"family": "energy", "terms": ["low voltage"]},
    "medium_voltage": {"family": "energy", "terms": ["medium voltage"]},
    "high_voltage": {"family": "energy", "terms": ["high voltage"]},
    # ---- qualifiers: process form / technology. They are SYMMETRIC (see passes): a
    # candidate carrying one the query lacks fails, and vice versa, so "diesel, burned in
    # machinery" never takes a diesel supply dataset, a supply query never takes a
    # combustion dataset, seed for sowing is never grain, and a grid query never takes a
    # single-technology plant. Read from the activity name as well as the product. ----
    "combustion": {"family": "process", "qualifier": True,
                   "terms": ["burned", "burnt", "combustion", "combusted"]},
    "pump_operation": {"family": "process", "qualifier": True,
                       "terms": ["water pump operation", "pump operation"]},
    "sowing_seed": {"family": "process", "qualifier": True,
                    "terms": ["for sowing", "seed for sowing", "planting material"]},
    "hydro": {"family": "technology", "qualifier": True,
              "terms": ["hydro", "hydropower", "hydroelectric", "hydroelectricity"]},
    "wind": {"family": "technology", "qualifier": True,
             "terms": ["wind", "wind turbine", "wind power"]},
    "photovoltaic": {"family": "technology", "qualifier": True,
                     "terms": ["photovoltaic", "solar pv", "pv"]},
    # ---- chemicals with metal names (copper fungicides are copper salts, not the metal) ----
    "copper_oxide": {"family": "pesticide", "terms": ["copper oxide", "cupric oxide",
                                                      "copper hydroxide", "copper oxychloride"]},
    "copper_sulfate": {"family": "pesticide", "terms": ["copper sulfate", "copper sulphate"]},
    "copper_metal": {"family": "metal", "terms": ["copper", "copper cathode", "cathode copper"]},
    # ---- by-products that share words with fuels / fertilisers ----
    "digestate": {"family": "fertiliser", "terms": ["digestate"]},
    # ---- packaging materials ----
    "packaging": {"family": "packaging", "terms": ["packaging"], "generic": True},
    "polypropylene": {"family": "packaging", "terms": ["polypropylene"]},
    "polyethylene": {"family": "packaging", "terms": ["polyethylene", "ldpe", "hdpe",
                                                      "lldpe", "polythene"]},
    "pet": {"family": "packaging", "terms": ["polyethylene terephthalate"]},
    "pvc": {"family": "packaging", "terms": ["polyvinylchloride", "polyvinyl chloride",
                                             "pvc"]},
    "pvdc": {"family": "packaging", "terms": ["polyvinylidenchloride",
                                              "polyvinylidene chloride"]},
    "kraft_paper": {"family": "packaging", "terms": ["kraft paper", "paper bag",
                                                     "paper sack"]},
    "corrugated_board": {"family": "packaging", "terms": ["corrugated board", "cardboard",
                                                          "corrugated box"]},
    "steel": {"family": "packaging", "terms": ["steel", "tinplate", "tin can"]},
    "aluminium": {"family": "packaging", "terms": ["aluminium", "aluminum"]},
    "glass": {"family": "packaging", "terms": ["glass", "packaging glass", "glass bottle"]},
    "jute": {"family": "packaging", "terms": ["jute", "jute sack", "jute bag"]},
    # ---- water and waste (service activities; identity read from the activity name) ----
    "tap_water": {"family": "water", "terms": ["tap water", "drinking water"]},
    "deionised_water": {"family": "water", "terms": ["water deionised", "deionised water",
                                                     "water deionized", "deionized water",
                                                     "demineralised water"]},
    "decarbonised_water": {"family": "water", "terms": ["water decarbonised",
                                                        "decarbonised water"]},
    "ultrapure_water": {"family": "water", "terms": ["water ultrapure", "ultrapure water"]},
    "wastewater": {"family": "waste", "terms": ["wastewater", "waste water", "effluent"]},
    "msw": {"family": "waste", "terms": ["municipal solid waste", "msw"]},
    "landfill": {"family": "waste", "terms": ["landfill"]},
    "incineration": {"family": "waste", "terms": ["incineration"]},
    "composting": {"family": "waste", "terms": ["composting"]},
    "anaerobic_digestion": {"family": "waste", "terms": ["anaerobic digestion"]},
    "biowaste": {"family": "waste", "terms": ["biowaste"]},
    "waste_paper": {"family": "waste", "terms": ["waste paper"]},
    # ---- transport ----
    "lorry": {"family": "transport", "terms": ["lorry", "truck"]},
    "train": {"family": "transport", "terms": ["train", "rail", "railway"]},
    "ship": {"family": "transport", "terms": ["container ship", "ship", "vessel",
                                              "sea freight"]},
}

# Families whose identity sits in the ACTIVITY name rather than the reference product
# (ecoinvent treatment and transport activities have the waste / service as reference).
NAME_IDENTITY_FAMILIES = frozenset({"waste", "transport", "water", "process", "technology"})

# A candidate whose reference product is a WASTE or scrap stream ("market for waste glass",
# "market for waste polyethylene") never satisfies a material / product query, even though
# it names the material. It carries this marker concept instead (no terms, set by
# candidate_concepts) and only waste-treatment queries accept it.
_C["_waste_stream"] = {"family": "waste_stream", "terms": []}
_WASTE_STREAM_PREFIXES = ("waste ", "scrap ", "used ", "spent ", "post consumer ")
QUALIFIERS = frozenset(c for c, spec in _C.items() if spec.get("qualifier"))

# Words that never identify a product: used by the token (head-noun) fallback.
_STOPWORDS = frozenset("""
a an and at as by for from in into of on or per the to with without via
production produced product products producing raw fresh dried dry sun dried
market farm gate plant mill processing processed process unspecified average mix
local imported bulk grade quality conventional organic whole shelled unshelled
peeled clean cleaned sorted harvested crude refined input inputs material materials
other none n a kg tonne tonnes ton tons per unit item items cutoff cut off u s
production mix consumption type types generic various misc miscellaneous
""".split())

# ----------------------------------------------------------------------------- helpers
_NORM_RE = re.compile(r"[^a-z0-9%]+")


def normalise(text: str | None) -> str:
    """Lower-case, strip accents, turn every non-alphanumeric run into one space."""
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
    return " " + _NORM_RE.sub(" ", t.lower()).strip() + " "


def _build_phrases() -> tuple[dict, int]:
    """Word-tuple -> concept id, with the plural forms ("s"/"es" on the last word)."""
    table: dict = {}
    longest = 1
    for cid, spec in _C.items():
        for term in spec["terms"]:
            words = tuple(normalise(term).split())
            longest = max(longest, len(words))
            for suffix in ("", "s", "es"):
                key = words[:-1] + (words[-1] + suffix,)
                table.setdefault(key, cid)
    return table, longest


_PHRASES, _MAX_WORDS = _build_phrases()


def detect(text: str | None) -> list[str]:
    """Concept ids found in `text`, in order of appearance. Whole words only; scanning left
    to right, the longest phrase starting at each position wins and its words are consumed,
    so matches never overlap."""
    words = normalise(text).split()
    out: list[str] = []
    i, n = 0, len(words)
    while i < n:
        for k in range(min(_MAX_WORDS, n - i), 0, -1):
            cid = _PHRASES.get(tuple(words[i:i + k]))
            if cid:
                if cid not in out:
                    out.append(cid)
                i += k
                break
        else:
            i += 1
    return out


def family(cid: str) -> str:
    return _C[cid]["family"]


def content_tokens(text: str | None) -> set[str]:
    """Plural-insensitive content words (head-noun fallback when no concept is known)."""
    toks = set()
    for w in normalise(text).split():
        if len(w) < 3 or w.isdigit() or w in _STOPWORDS or any(ch.isdigit() for ch in w):
            continue
        toks.add(_stem(w))
    return toks


def _stem(w: str) -> str:
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith(("ches", "shes", "sses", "xes", "oes")):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


@dataclass
class Identity:
    """What a candidate must prove to pass the gate."""
    basis: str                                  # concept | proxy | generic | token | none
    concepts: list = field(default_factory=list)  # required concept ids
    tokens: set = field(default_factory=set)      # token-basis content words

    @property
    def needs_review(self) -> bool:
        return self.basis in ("proxy", "generic", "none")

    def describe(self) -> str:
        if self.concepts:
            return ", ".join(self.concepts)
        if self.tokens:
            return "words: " + ", ".join(sorted(self.tokens))
        return "(none)"


def query_identity(query: str) -> Identity:
    """Concepts a query requires. A query written as an ecoinvent dataset name
    ("activity | product | system") is read like a candidate: concepts of the PRODUCT, plus
    service, process and technology concepts of the activity (so "anaerobic digestion of
    manure | biogas" requires biogas, not manure)."""
    parts = [p.strip() for p in (query or "").split("|")]
    if len(parts) >= 2 and parts[1]:
        found = sorted(c for c in candidate_concepts(parts[0], parts[1]) if not c.startswith("_"))
    else:
        found = detect(query)
    specific = [c for c in found if not _C[c].get("generic")]
    if specific:
        core = [c for c in specific if not _C[c].get("qualifier")]
        proxy = bool(core) and all(_C[c].get("accept") and c not in _C[c]["accept"]
                                   for c in core)
        return Identity("proxy" if proxy else "concept", specific)
    if found:
        return Identity("generic", found)
    toks = content_tokens(query)
    return Identity("token", [], toks) if toks else Identity("none")


def candidate_concepts(name: str | None, reference_product: str | None) -> frozenset:
    """Concepts a background dataset provides: those of its reference product, plus
    service-family concepts read from the activity name."""
    ref = reference_product or name or ""
    # Agribalyse copies of ecoinvent read "Product {LOC}| activity | system": the product is
    # the part before the first "|"; the activity part counts like an activity name.
    activity = name if name and name != ref else ""
    if "|" in ref:
        ref, rest = ref.split("|", 1)
        activity = f"{activity} {rest}".strip()
    got = set(detect(ref))
    if activity:
        got.update(c for c in detect(activity) if _C[c]["family"] in NAME_IDENTITY_FAMILIES)
    if normalise(ref).lstrip().startswith(_WASTE_STREAM_PREFIXES):
        got.add("_waste_stream")
    return frozenset(got)


def satisfied(cid: str, provided: frozenset) -> bool:
    """Is concept `cid` (specific, proxy or generic) provided by a candidate?"""
    spec = _C[cid]
    if spec.get("generic"):
        fam = spec["family"]
        return any(_C[p]["family"] == fam for p in provided)
    accept = spec.get("accept") or [cid]
    return any(a in provided for a in accept)


def passes(identity: Identity, provided: frozenset, cand_text: str = "") -> bool:
    """Gate: does a candidate (its provided concepts / text) carry the query's identity?"""
    if identity.basis == "none":
        return False
    wanted = set(identity.concepts)
    # symmetric qualifiers: the candidate may not add a process form / technology
    if (provided & QUALIFIERS) - wanted:
        return False
    # a waste stream only satisfies a waste-treatment query
    if "_waste_stream" in provided and not any(_C[c]["family"] == "waste" for c in wanted):
        return False
    if identity.basis in ("concept", "proxy", "generic"):
        return all(satisfied(c, provided) for c in identity.concepts)
    return bool(identity.tokens & content_tokens(cand_text))


def review_reason(identity: Identity) -> str | None:
    if identity.basis == "proxy":
        acc = sorted({a for c in identity.concepts for a in (_C[c].get("accept") or [])})
        return (f"no dataset for '{', '.join(identity.concepts)}'; matched a proxy "
                f"product ({', '.join(acc)}). Confirm the proxy.")
    if identity.basis == "generic":
        return ("input names only a product family ('" + ", ".join(identity.concepts)
                + "'), not a specific product; any dataset of that family passes. Specify "
                "the product.")
    return None
