# LCA Engineer — Literature Extraction Specification

> **Purpose.** Turn the sources in [`LITERATURE_WISHLIST.md`](./LITERATURE_WISHLIST.md) into **structured, machine-usable data** the engine consumes: emission factors, characterization factors, allocation rules, equations, and qualitative method requirements. This file says *exactly which sections/tables to pull from each source* and *the schema to store them in*, so extraction is consistent and auditable — and so the AI extraction subsystem has a target spec to validate against.
>
> Each extracted item must carry full provenance (source key, page/table, version) — non-negotiable for ISO 14048 + reproducibility.

---

## 0. Canonical extraction schema

Everything extracted lands in one of four record types. Store as JSON/JSONL in `references/extracted/`, then load to the canonical store (Postgres) per [`DATABASE_PLAN.md`](./DATABASE_PLAN.md §3).

```jsonc
// (1) EMISSION FACTOR  — LCI: activity → elementary flow
{
  "type": "emission_factor",
  "id": "ef.ipcc2019.n2o.direct.synthetic_n",
  "activity": "Synthetic N fertiliser application",
  "flow": "N2O",                      // normalise to EF/ILCD flow (C1)
  "value": 0.010, "unit": "kg N2O-N / kg N",
  "applicability": {"climate": "wet tropical", "crop": "any", "region": "global default"},
  "uncertainty": {"dist": "lognormal", "range_low": 0.001, "range_high": 0.018, "ci": 0.95},
  "tier": "IPCC tier 1",
  "provenance": {"source": "IPCC-2019", "vol": 4, "chapter": 11, "table": "11.1", "year": 2019}
}

// (2) CHARACTERIZATION FACTOR — LCIA: elementary flow → impact
{
  "type": "characterization_factor",
  "method": "ReCiPe-2016", "perspective": "H", "level": "midpoint",
  "impact_category": "Climate change", "indicator_unit": "kg CO2-eq",
  "flow": "Methane, fossil", "cf": 29.8, "cf_unit": "kg CO2-eq / kg",
  "geography": "GLO",
  "provenance": {"source": "ReCiPe-2016", "report": "I", "sheet": "midpoint", "version": "1.1"}
}

// (3) METHOD RULE — qualitative requirement that drives engine logic / validation
{
  "type": "method_rule",
  "id": "rule.iso14044.allocation.hierarchy",
  "topic": "allocation",
  "statement": "Avoid allocation by subdivision/system expansion; else partition by physical then economic relationship.",
  "engine_hook": "allocation_resolver",
  "provenance": {"source": "ISO-14044", "clause": "4.3.4.2"}
}

// (4) BENCHMARK — reference value for sanity checks / comparative analysis
{
  "type": "benchmark",
  "product": "Bovine meat (beef herd)", "indicator": "Climate change",
  "value_p50": 99.5, "value_p10": 20.0, "value_p90": 105.0, "unit": "kg CO2-eq / kg",
  "provenance": {"source": "POORE-2018", "asset": "supplementary dataset"}
}
```

---

## 1. IPCC 2019 Refinement, Vol 4 (AFOLU) — `IPCC-2019` → **emission_factor** records  ⟶ P0

Replaces the single hand-typed values in `lci.rs` with the full factor set + uncertainty.

**Extract:**
- **Ch 11 (N₂O from managed soils):** EF1 (direct, synthetic & organic N), the disaggregated wet-vs-dry EF1, EF2 (organic soils), EF3 (manure management), **FracGASF / FracGASM** (volatilisation), **FracLEACH** (leaching), EF4 (atmospheric deposition), EF5 (leaching/runoff). Pull each with its uncertainty range.
- **Ch 10 (Livestock):** enteric CH₄ EFs by species/region (tier 1 + tier 2 equation inputs), manure-management CH₄ (MCF by system + climate), Nex (N excretion) defaults.
- **Ch 5 (Cropland) / rice:** CH₄ baseline emission factor for rice paddies + scaling factors (water regime, organic amendment) — current code has one `ch4_from_rice_paddies` value.
- **Ch 11 liming & urea:** CO₂ EFs for limestone/dolomite and urea application.

**Store as:** `emission_factor` keyed `ef.ipcc2019.*`. Capture the **equations** (e.g. N₂O = (F_SN+F_ON)·EF1·44/28) as `method_rule` with an `engine_hook` to the LCI calculator.

## 2. IPCC AR6 WG1 — `IPCC-AR6` → **characterization_factor**  ⟶ P0

**Extract:** GWP100 and GWP20 for CO₂, CH₄ (fossil vs biogenic), N₂O, and major refrigerants/F-gases from the AR6 Ch7 metric tables; note GWP* for methane (for optional reporting). Store as `characterization_factor` with `method:"IPCC-AR6"`, `impact_category:"Climate change"`. These override any AR5/AR4 numbers currently mixed in.

## 3. ReCiPe 2016 v1.1 — `ReCiPe-2016` → **characterization_factor** (bulk)  ⟶ P0

The biggest extraction. Source = RIVM report + official CF spreadsheets.

**Extract — midpoint (17 categories), for each H/I/E perspective:**
Climate change, Ozone depletion, Ionising radiation, Photochemical ozone formation (human/eco), Fine PM formation, Terrestrial acidification, Freshwater/Marine eutrophication, Terrestrial/Freshwater/Marine ecotoxicity, Human toxicity (cancer/non-cancer), Land use, Water consumption, Mineral resource scarcity, Fossil resource scarcity.
- Pull the **full per-flow CF column** (thousands of rows) per category × perspective; normalise flow names to C1.
- **Endpoint:** midpoint→endpoint factors for Human Health (DALY), Ecosystem (species·yr), Resources (USD2013), plus the **damage pathway constants** so we can re-derive, not just copy, the endpoint values.
- **Normalisation & weighting** reference sets (global) — clearly tag as value-choices.

**Store as:** `characterization_factor` keyed `cf.recipe2016.<persp>.<level>.<category>.<flowUUID>`. This *replaces* the approximate endpoint math in `lca.rs::calculate_enhanced_endpoint_impacts`.

## 4. AWARE — `AWARE` → **characterization_factor**  ⟶ P0

**Extract:** country-level and (where used) monthly/annual, agri-vs-non-agri AWARE water-scarcity CFs for **Ghana and Nigeria (by basin/region) + global**. Store as `characterization_factor` method `AWARE`, `impact_category:"Water scarcity"`. Replace hardcoded `Ghana_water_scarcity=20`, `Nigeria_north=30`, `Nigeria_south=15` in `lca.rs::apply_regional_adjustments`.

## 5. EF 3.1 — `EF31-CF` → **characterization_factor**  ⟶ P1
**Extract:** the 16 EF impact-category CF tables + normalisation/weighting factors (JRC130796 spreadsheets). Store parallel to ReCiPe so users can switch method. Note AR6-aligned climate CFs.

## 6. USEtox / LANCA — `USEtox`, `LANCA` → **characterization_factor**  ⟶ P1
**Extract:** USEtox human-tox (cancer/non-cancer, CTUh) + ecotox (CTUe) CFs; LANCA land-use & soil-quality CFs (erosion resistance, mechanical filtration, groundwater regeneration, biotic production). Targets our weakest categories (`data_sources.md` "low confidence").

## 7. FAO LEAP + GLEAM — `LEAP-CROP`, `GLEAM-DOC` → **method_rule** + **emission_factor**  ⟶ P0/P1
**Extract:**
- LEAP **allocation** conventions for co-products (meat/milk, crop residues), **system boundaries** for feed, **soil-carbon** accounting rules, **nutrient-flow** balance method → `method_rule` with engine hooks.
- Developing-country / **smallholder defaults** and tier guidance (directly addresses our African data-scarcity gap).
- GLEAM regional **enteric/manure EFs** for Africa → `emission_factor`.

## 8. AGRIBALYSE 3.x methodology — `AGB-METH` → **method_rule**  ⟶ P0
**Extract:** production-vs-consumption modelling, transport/processing/packaging/cooking stage defaults, allocation choices, and the data-quality/pedigree approach. We mirror this structure for food products; capture as `method_rule` + a process-template spec.

## 9. ISO 14040/14044 + ILCD Handbook — `ISO-14040/44`, `ILCD-HB` → **method_rule**  ⟶ P0
**Extract (as `method_rule` with `engine_hook`):**
- Goal & scope content requirements (functional unit, system boundary, cut-off criteria).
- **Allocation hierarchy** (14044 §4.3.4.2): avoid → physical → economic.
- Data-quality requirements (time/geography/technology coverage, completeness, consistency).
- LCIA mandatory vs optional steps (classification, characterization | normalisation, weighting).
- Interpretation: completeness, sensitivity, consistency checks → drive our automated QA + anomaly checks.

## 10. Poore & Nemecek 2018 SI — `POORE-2018` → **benchmark**  ⟶ P0
**Extract:** per-product impact distributions (P10/P50/P90) for GHG, land, water, eutrophication, acidification across the ~40 food products. Store as `benchmark`; powers (a) sanity-check ranges for anomaly detection and (b) comparative analysis replacing the magic numbers in `lca.rs::generate_*_comparative_analysis` (e.g. `benchmark_value: 2000.0`).

## 11. Pedigree matrix — `PEDIGREE` → **method_rule** + factor table  ⟶ P0
**Extract:** the 5-indicator × 5-score matrix and the **uncertainty-factor (lognormal σ²) lookup** (Weidema et al. 2013). Our `PedigreeScore::calculate_uncertainty_factor` must implement *these* values, not ad-hoc weights. Store the lookup table as a small reference dataset.

## 12. AI-method papers — `LLM-EST`, `ENTITY-LINK`, `KG-EMB`, `LLM-OCR` → **method_rule** (design constraints)  ⟶ P0
Not factor data — extract **design requirements** for our subsystems:
- **ENTITY-LINK:** hybrid pipeline (LLM generates a process description → embed → cosine match in FAISS); the empirical finding *semantic-only ≈5% top-5 vs LLM+context ≈48%* ⇒ **require** LLM-augmented matching + human confirmation + show top-5 with scores.
- **LLM-EST:** decompose query → retrieve passages → extract value+unit+context → validate against ranges ⇒ our RAG extraction loop design + mandatory validation step.
- **KG-EMB:** KG-embedding extrapolation for missing LCI ⇒ data-gap-filling subsystem with reported-accuracy disclosure.
- **LLM-OCR:** hallucination/transparency risks ⇒ every AI-asserted value must cite provenance and never overwrite a measured/loaded factor silently.
Store as `method_rule` with `engine_hook` to the relevant subsystem; these become acceptance tests.

---

## Extraction pipeline (how the AI subsystem does this, with guardrails)

```
PDF/spreadsheet ──▶ layout parse (tables/eqs) ──▶ LLM extract → schema-typed records
                                                       │
                                                       ▼
                                   VALIDATE: unit check · range check vs known
                                   physics · cross-source agreement · provenance present
                                                       │
                          pass ──▶ canonical store        fail ──▶ human review queue
```

- **Never** ingest an unvalidated extracted value into computation. Validation = unit consistency, plausibility range, and (where two sources overlap, e.g. IPCC vs ecoinvent N₂O) cross-source agreement within tolerance.
- Every record is **provenance-complete or rejected.**
- Spreadsheet CF tables (ReCiPe/EF/AWARE) are extracted **deterministically** (parsers), not via LLM — LLM extraction is for prose/PDF tables only, where it must be double-checked.
- Maintain an **extraction gold-set** (hand-verified records) to measure extraction precision/recall before trusting the automated path.

### Priority order
P0 extraction unblocks Tier 1: **IPCC-2019 → ReCiPe-2016 → AWARE → IPCC-AR6 → Pedigree → Poore&Nemecek → ISO/ILCD rules → LEAP/Agribalyse rules → AI design rules.**
