#!/usr/bin/env python3
"""
pesticides.py: pesticide inventory for the farm path.

Two flows per application, both in kg of ACTIVE INGREDIENT (AI):
  1. Production: the AI's chemical-class dataset (ecoinvent pesticide datasets are per kg
     AI), e.g. glyphosate -> "market for glyphosate", lambda-cyhalothrin -> "market for
     pyrethroid-compound". Unknown AIs fall back to "market for pesticide, unspecified".
  2. Field emission: 100% of the applied AI to agricultural soil as an ELEMENTARY flow
     (e.g. "Lambda-cyhalothrin", Emission to soil/agricultural), so the USEtox-based
     toxicity categories of the LCIA method pick it up.

     Source of the 100% to soil convention: Nemecek T., Kaegi T. (2007) Life Cycle
     Inventories of Swiss and European Agricultural Production Systems, ecoinvent report
     No. 15, Section 3.9 (pesticides are inventoried as emissions of the applied active
     ingredient to agricultural soil); the same convention is used by AGRIBALYSE 3 (Koch P.,
     Salou T. 2020, AGRIBALYSE v3.0 methodology report, ADEME). The PEF alternative
     (90% soil / 9% air / 1% water, EC 2018 PEFCR Guidance v6.3) is not applied.

AI mass = product rate x applications x area x AI content. AI content is the user's value,
else the typical formulation strength of that AI (the number in the product code, e.g.
"Glyphosate 360 SL" = 360 g AI per litre), else 1.0 (conservative upper bound, warned).

The flow mapping lives here (PESTICIDE_FLOWS), not in engine/flowmap.py.
"""
from __future__ import annotations

# Notes carrying this prefix are lifted into data_quality.warnings (engine/service.py).
WARNING_PREFIX = "validation warning: "

EMISSION_FRACTION_SOIL = 1.0
EMISSION_SOURCE = ("Nemecek & Kaegi (2007) ecoinvent report No. 15, s.3.9; AGRIBALYSE 3.0 "
                   "methodology (Koch & Salou 2020): 100% of applied active ingredient to "
                   "agricultural soil")
FORMULATION_SOURCE = ("typical registered formulation strength as encoded in the product code "
                      "(FAO/WHO JMPS formulation conventions, e.g. '360 SL' = 360 g AI/L); "
                      "replace with the label value")
SOIL_COMPARTMENT = "Elementary flows/Emission to soil/agricultural"

# canonical AI -> (elementary flow name in the store, production dataset, typical kg AI per
#                  kg-or-L of product, formulation label)
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
    "pendimethalin": ("Pendimethalin", "market for dinitroaniline-compound", 0.330, "330 EC"),
    "nicosulfuron": ("Nicosulfuron", "market for [sulfonyl]urea-compound", 0.040, "40 OD"),
    "lambda-cyhalothrin": ("Lambda-cyhalothrin", "market for pyrethroid-compound", 0.025, "2.5 EC"),
    "cypermethrin": ("Cypermethrin", "market for pyrethroid-compound", 0.100, "100 EC"),
    "deltamethrin": ("Deltamethrin", "market for pyrethroid-compound", 0.025, "25 EC"),
    "chlorpyrifos": ("Chlorpyrifos", "market for organophosphorus-compound, unspecified", 0.480, "480 EC"),
    "dimethoate": ("Dimethoate", "market for organophosphorus-compound, unspecified", 0.400, "400 EC"),
    "profenofos": ("Profenofos", "market for organophosphorus-compound, unspecified", 0.500, "500 EC"),
    "imidacloprid": ("Imidacloprid", "market for cyclic N-compound", 0.200, "200 SL"),
    "thiamethoxam": ("Thiamethoxam", "market for cyclic N-compound", 0.250, "25 WG"),
    "acetamiprid": ("Acetamiprid", "market for cyclic N-compound", 0.200, "20 SP"),
    "chlorantraniliprole": ("Chlorantraniliprole", "market for pesticide, unspecified", 0.200, "200 SC"),
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
    "copper": ("Copper", "market for copper oxide", 0.500, "50% metallic Cu"),
    "metalaxyl": ("Metalaxyl", "market for pesticide, unspecified", 0.350, "35 WS"),
}

_SYNONYMS = {
    "lambda cyhalothrin": "lambda-cyhalothrin", "lambdacyhalothrin": "lambda-cyhalothrin",
    "karate": "lambda-cyhalothrin", "s-metolachlor": "metolachlor", "2,4 d": "2,4-d",
    "2-4-d": "2,4-d", "24-d": "2,4-d", "roundup": "glyphosate", "gramoxone": "paraquat",
    "copper hydroxide": "copper", "copper oxychloride": "copper", "cuprous oxide": "copper",
    "emamectin": "emamectin benzoate",
}

GENERIC_DATASET = "market for pesticide, unspecified"


def canonical_ai(text: str | None) -> str | None:
    low = (text or "").strip().lower()
    if not low:
        return None
    for syn, key in sorted(_SYNONYMS.items(), key=lambda kv: -len(kv[0])):
        if syn in low:
            return key
    for key in sorted(PESTICIDE_FLOWS, key=len, reverse=True):
        if key in low:
            return key
    return None


def applications(assessment: dict, total_area: float) -> tuple[list[dict], list[str]]:
    """Resolve every pesticide application to AI mass. Returns (rows, notes); each row:
    {ai_text, ai_key, kg_product, kg_ai, content, content_source, dataset, flow_name}."""
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
        kg_product = rate * n * total_area
        if kg_product <= 0:
            if rate and not total_area:
                notes.append(f"{WARNING_PREFIX}pesticide '{label}' reported but no crop area: "
                             "cannot scale it, so it is NOT counted")
            continue
        ai_text = (p.get("active_ingredient") or p.get("pesticide_type") or "pesticide").strip()
        key = canonical_ai(ai_text)
        spec = PESTICIDE_FLOWS.get(key) if key else None
        content = p.get("active_ingredient_content")
        if content is not None and 0 < content <= 1.0:
            csrc = "farmer (label)"
        elif spec:
            content, csrc = spec[2], f"{FORMULATION_SOURCE}: {spec[3]}"
        else:
            content, csrc = 1.0, "unknown formulation: product mass counted as AI (conservative upper bound)"
            notes.append(f"pesticide '{ai_text}': active-ingredient content unknown; product mass "
                         "counted as active ingredient (conservative). Enter the label strength.")
        rows.append({
            "ai_text": ai_text, "ai_key": key, "kg_product": kg_product,
            "kg_ai": kg_product * content, "content": content, "content_source": csrc,
            "dataset": spec[1] if spec else GENERIC_DATASET,
            "flow_name": spec[0] if spec else None,
            "pesticide_type": p.get("pesticide_type"),
        })
        if not spec:
            notes.append(f"pesticide '{ai_text}' not in the active-ingredient table: production "
                         "modelled with 'pesticide, unspecified' and no soil emission flow, so its "
                         "toxicity is not characterised")
    return rows, notes


def purchased_inputs(rows: list[dict]) -> list[dict]:
    """Production of each AI (kg AI) for the supply-chain solver."""
    out = []
    for r in rows:
        out.append({"name": r["ai_text"], "match_as": r["dataset"], "amount": r["kg_ai"],
                    "unit": "kg", "kind": "pesticide", "active_ingredient": r["ai_key"],
                    "ai_content": r["content"], "ai_content_source": r["content_source"]})
    return out


def resolve_soil_flow(conn, flow_name: str) -> tuple[str, str] | None:
    """(uid, name) of the agricultural-soil emission flow for an AI, preferring the flow
    with the most characterisation factors (the ecoinvent 3.11 flow in the store)."""
    row = conn.execute(
        "SELECT f.uid, f.name, (SELECT COUNT(*) FROM characterization_factors cf "
        "WHERE cf.flow_uid = f.uid) AS n FROM flows f WHERE f.flow_type = 'ELEMENTARY_FLOW' "
        "AND lower(f.name) = lower(?) AND f.category = ? ORDER BY n DESC LIMIT 1",
        (flow_name, SOIL_COMPARTMENT)).fetchone()
    if not row:
        return None
    return row[0], row[1]


def field_emission_flows(conn, rows: list[dict]) -> tuple[list[dict], list[str]]:
    """Elementary flows {uid, name, unit, amount} for the AI emitted to agricultural soil."""
    flows, notes = [], []
    for r in rows:
        if not r["flow_name"]:
            continue
        hit = resolve_soil_flow(conn, r["flow_name"])
        if not hit:
            notes.append(f"no agricultural-soil flow for '{r['flow_name']}' in the store; its "
                         "field emission is not characterised")
            continue
        flows.append({"uid": hit[0], "name": f"{hit[1]} (soil, agricultural)", "unit": "kg",
                      "amount": r["kg_ai"] * EMISSION_FRACTION_SOIL, "source": EMISSION_SOURCE})
    return flows, notes
