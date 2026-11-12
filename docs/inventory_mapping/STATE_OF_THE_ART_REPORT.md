# Green Means Go LCA engine: state-of-the-art upgrade report

Branch `feat/state-of-the-art-engine`, based on `main` at 8024a2f. Not pushed.
Brief: `docs/inventory_mapping/TEAM_PROMPT_state_of_the_art.md`.

## 1. Summary

The engine now models what a cradle-to-gate crop LCA in West Africa needs at IPCC 2019 Tier 1:
- crop-residue N2O for every supported crop;
- explicit fertiliser N contents;
- climate-disaggregated soil N parameters per region;
- perennials and land-use change;
- combustion of LPG, kerosene, firewood and charcoal;
- pesticide emissions to soil;
- regionalised water scarcity (AWARE) and land use (LANCA soil quality);
- six regions: GH, NG, SN, BF, ZA, CA.

Other changes:
- **Wizard fields:** every field the wizard collects now either changes the result or is shown in the ISO report as metadata that does not change the numbers. A few fields were removed.
- **Request validation:** request models reject unknown keys, so a silently dropped field like `pesticides_used` cannot happen again.
- **Matching:** the matcher checks that a dataset is the right product before it applies region preference. It is deterministic, and a 738-row executed regression test guards it.
- **Data on disk:** every item under `data/` is either used by a named code path or documented as unused, and a test enforces this.
- **The model:** it only renames free text and breaks ties between candidate datasets. A test guarantees that no number it produces reaches a result.

Final verification is in section 9. Section 10 lists the decisions a human LCA reviewer still has to make.

## 2. How the work was done

Six agents worked in parallel, one per workstream, each in its own git worktree with a written file-ownership list and fixed interfaces where workstreams met. The lead merged the branches in this order: WS5, WS3b, WS1, WS3, WS4, WS2. The merges conflicted only in imports and service wiring (`engine/orchestrator.py`, `engine/rust_kernel.py`, `engine/service.py`, `engine/process_service.py`), and every conflict was resolved by keeping both sides.

Integration then found and fixed six cross-workstream defects. A seventh agent regenerated the PM's mapping files with the executed matcher. That run exposed matcher defects in the new regions, which the WS4 agent then fixed (section 3.4). All commits end with the brief's `Co-Authored-By: Claude Fable 5.1` trailer.

Integration fixes made by the lead:

| Defect found at integration | Fix |
|---|---|
| Irrigation water counted twice: WS2 booked evaporated water with the world AWARE CF and WS3 booked the regional AWARE flow, from two different volumes. | One volume, the farmer's measured m3 or the cited FAO crop-water-need estimate, replaces the kernel default. `water_scarcity` books the consumed share once, on the regional flow. `farm_flows` only relabels withdrawal by source, which is characterisation-neutral. Facility water uses the regional non-agri AWARE flow. Test: `engine/test_water_single_path.py`. |
| Acidification missing for ReCiPe regions (GH, NG, SN, BF, ZA) and fossil depletion missing for CA. This was a pre-existing defect: the adapter did not map "Acidification: terrestrial" or EF "Energy resources: non-renewable". | Mapped. Toxicity (freshwater, marine and terrestrial ecotoxicity; human toxicity cancer and non-cancer), ozone depletion and ionising radiation are now reported as midpoints, outside the single score. Single-score bands recalibrated (farm 930/1990 to 970/2050 uPt/kg; processed 3230/4720 to 3430/5150). |
| `grid_ef_source` was a filename in WS3b's registry but a citation string in WS3's loader. | `grid_calibration.grid_factor` accepts both, and all six regions resolve with a real citation. |
| Nigeria registry fields not set; the regional yield benchmark was Ghana-only and invented a 1200 kg/ha guide for unknown crops. | NG table and grid factor set, with citation and pedigree. The benchmark reads each region's own guide and gives no guide where none exists. |
| Conventional seed matched organic seed datasets. | Production-system qualifiers (organic, Swiss IP) rank mismatches last, in both directions. Test: `engine/test_matcher_system_qualifier.py`. |
| The classifier was not wired in. | Wired into the farm fuel fallback, which used to silently assume diesel, and the processing raw-material fallback. AGO, PMS, DPK and French terms now resolve offline through the synonym table. Test: `engine/test_classify_wiring.py`. |

## 3. What changed, per workstream

### 3.1 Foreground model (WS1)

| Brief item | Status | Where |
|---|---|---|
| IPCC 2019 crop-residue N2O (Eq 11.6, 11.7, Table 11.1A) | Done. Table 11.1A rows: maize, rice, millet, sorghum, wheat, barley, oats, groundnut, soybean, cowpea and pulses, potato and tubers. Crops with no IPCC row use the generic "crops not indicated" row, flagged as proxies: cassava, yam, tomato, pepper, chilli, eggplant, cucumber, onion, okra, sesame, cotton, cocoa, oil palm (dry matter from USDA FoodData Central). Sugarcane uses Hassuani et al. 2005. Optional residue removal and burning (2006 Vol 4 Table 2.5, 2019 Table 2.6). Flooded rice EF1FR 0.004. | `african_lca_backend/src/production/field.rs` |
| BNF on the legume itself | Done. BNF is not an N input (IPCC 2019 Ch 11, footnote 1); legumes contribute residue N. The intercrop credit applies only to the partner's synthetic-fertiliser N2O, and a legume never credits itself. | `field.rs`, `engine/field_model.py` |
| Perennials | Done. Cocoa: 3 + 22 years (IITA/ICCO). Oil palm: 25-year cycle with 3 immature years (RSPO PalmGHG). Establishment amortised. "Occupation, permanent crop". | `engine/perennials.py` |
| dLUC | Done. Tier 1 stock difference, 20-year linear amortisation (PAS 2050-1, IPCC Vol 4 Ch 2/5). Applied only when `foods[].land_use_change` is declared with fewer than 20 years. GH uses `ipcc_stock_change_factors_gh.json`; other regions use IPCC climate-zone defaults, flagged. SOC loss adds F_SOM N2O. | `engine/land_use_change.py` |
| Fertiliser N | Done. Explicit lookup (FAO & IFA 2000): urea 0.46, CAN 0.27, AS 0.21, AN 0.335, DAP 0.18, MAP 0.11; SSP, TSP and MOP 0. A declared grade wins. Unknown types get 0 N plus a validation warning; the 10% fallback is gone. | `field.rs` |
| Fuels and units | Done. LPG, kerosene, firewood and charcoal: production in kg plus direct combustion CO2/CH4/N2O (IPCC 2006 Vol 2 Table 2.5); biogenic CO2 is not counted. The kerosene MJ-against-kg mismatch is fixed. `engine/units.py` converts any amount to the matched dataset's reference unit, or excludes the input with a validation warning. | `engine/fuels.py`, `engine/units.py`, `engine/orchestrator.py` |
| Honey | Rejected on the farm path with HTTP 422 and a clear message. No West African apiculture inventory exists to build a defensible foreground. In processing, raw honey is steered to the WFLDB small-scale honey dataset (CH) and flagged as a proxy. | `engine/commodities.py`, `app/production/routes.py` |
| Region soil-N parameters end to end | Done. EF1 synthetic and other, EF4, EF5, FracGASF, FracGASM and FracLEACH are passed into the kernel from the region registry. Dry climates set FracLEACH to 0, except under irrigation other than drip (p 11.25). | `engine/field_params.py` |

### 3.2 Inputs collected but ignored (WS2)

- The `pesticides_used` / `pesticides` contract is fixed. Every request model is now strict (`extra="forbid"`): legacy aliases are mapped, deliberately removed keys are dropped so archived requests still re-run, and any other unknown key returns 422 (`app/test_request_schema.py`).
- Pesticides are counted twice over, as intended: production by active-ingredient class dataset, and 100% of the active ingredient emitted to agricultural soil (Nemecek & Kaegi 2007; AGRIBALYSE 3.0). `engine/pesticides.py` holds 31 active ingredients.
- Processing accepts several fuel streams.
- Default conversion ratios carry sources (`engine/conversion_ratios.py`): FFB to CPO 0.20 (MPOB, FAO TCF), cocoa bean to liquor 0.80, maize flour 0.80 (FAO 1992), wheat 0.75, paddy 0.67, cassava flour 0.25.
- The dead fallback chains in `engine/process_inputs.py` are removed. The orchestrator's are now live (WS4).
- The full field-by-field list is in section 6.

### 3.3 Data on disk (WS3)

- **Store writes:** additive only. 7 `gmg_*` tables with a provenance table, one `sources` row, and 104 regionalised elementary flows with their characterisation factors. No existing row was changed. Rebuild with `python -m ingestion.gmg_reference all`, then `python -m ingestion.reconcile_lcia`.
- **Biogenic carbon bridge fixed:** FEDEFL merges fossil and biogenic CO2 and CH4, so biogenic CO2 was characterised as fossil. It now gets 0, and non-fossil methane gets the method's biogenic factor (ReCiPe 34, EF 3.1 27.0). On-farm flows now resolve to ground-level ecoinvent flows, which both methods characterise by exact flow id. Test: `ingestion/test_biogenic_bridge.py`.
- **AWARE 2.0** gives a water scarcity midpoint for every method and every region.
- **LANCA** gives country soil-quality CFs for on-farm land under EF 3.1.
- **GWP basis** is stated in both ISO reports (`engine/gwp_basis.py`).
- **Normalisation factors** load from a derived file. The ReCiPe values are reconciled to the spreadsheet; the EF values are cited from JRC 2024, because the spreadsheet on disk has none.
- **CF reconciliation:** ReCiPe, 53 CFs compared, none differ by more than 1%. EF 3.1, 1070 compared, 13 differ by more than 1%, all explained as artefacts of the comparison (`engine/lcia_reference/cf_reconciliation.json`).
- **Nigeria** activity defaults and grid factor added.

### 3.3b New regions SN, BF, ZA (WS3b)

- **Registry fields:** IPCC climate parameters with a citation per field and pedigree scores. `ghana_inherited` flags (NG only: EF1, EF4 and FracLEACH mirror Ghana's wet assumption). AWARE keys checked against the xlsx. `location_prefer` built from location strings that actually exist in the store.

| Region | Climate class | EF1 | FracLEACH | Grid factor (kg CO2e/kWh) | Grid source | Electricity dataset |
|---|---|---|---|---|---|---|
| SN | dry tropical | 0.005 | 0 | 0.744 | GIZ PED Senegal 2021, Tableau 5 (operating margin); SENELEC/CRSE publish none | SN LV/MV in store |
| BF | dry tropical | 0.005 | 0 | 0.569 | Nana et al. 2023, Clean Air Journal (CC BY); SONABEL/ARSE publish none | no BF grid; falls to the RAF "Africa" market group |
| ZA | warm temperate dry | 0.005 | 0 | 1.04 | Eskom Integrated Report 2024, p 122 | ZA HV/MV/LV |
| NG | wet/dry tropical (wet default) | 0.016 | 0.24 | 0.496 | Ember 2024 lifecycle intensity; no official national factor | NG LV |

- **Reference tables:** activity defaults, FAOSTAT yield guides and producer prices per country.
- **Recommendation measures:** 11, from the CIAT/USAID Senegal CSA profile, the Burkina Faso CDN 2021-2025 and the DAFF Draft CSA Strategic Framework. All licences permit non-commercial reuse.
- **Frontend:** region picker, common crops by region, XOF/ZAR currency (`african-lca-frontend/src/lib/regions.ts`).
- **Case studies:** three new ones, each with a `.sources.md`.
- **Data-quality report:** the ISO report's data-quality section lists any field still at a Ghana value.

### 3.4 Matching (WS4)

- **Product-identity gate.** Implemented in `engine/product_identity.py`, a controlled synonym table that matches whole words, ignores plurals and lets the longest phrase win.
  - The ranking order is: identity gate, then production system, then region tier, then similarity, then uid.
  - If no retrieved candidate passes the gate, every store dataset that passes is scored.
  - If nothing passes at all, the best global match is returned with `needs_review` set, rather than a wrong-crop regional match.
  - Symmetric qualifiers are read from both the activity name and the product: combustion, pump operation, seed for sowing, voltage level, hydro, wind and PV. Waste-stream products are rejected unless the query is a treatment query.
- **Region step-down:** BF electricity now reaches the RAF market group instead of a South African activity.
- **Unit preference:** candidates whose reference unit is reachable are preferred, which cut the mapping's UNIT MISMATCH rows from 31 to 0.
- **Deterministic location ranking:**
  - An exact location string outranks a sub-national prefix such as "Canada, Ontario".
  - A bare substring no longer counts, so "Africa" never matches "South Africa".
  - Ties are broken by score, then uid.
- **Adjudication hook:**
  - It is called on near ties between different products (gap below 0.01, calibrated on 174 rows), when the identity gate overruled the most similar dataset, or when a match needs review.
  - Every call is recorded in the input match report.
- **Regression test:** `engine/test_matcher_regression.py` checks 738 rows (farm, processing and raw material across the six regions) against `engine/golden/matcher_golden.json`. Query vectors are pinned, so it runs offline in about 20 s.

### 3.5 Intelligence layer (WS5)

- **Client and model:** `engine/llm/` uses `claude-opus-5-5` at low effort, with timeouts and retries. The key is read only from the environment or `app/.env`, and errors are reduced to a class name and HTTP status.
- **`classify(kind, text)`** works in this order: exact match, synonym table, label found inside the text, committed cache, then the model. The model's answer is constrained to the vocabulary by a JSON-schema enum, and anything below 0.8 confidence is marked `needs_confirmation`.
- **`adjudicate(query, context, candidates)`** may only return one of the given uids, or abstain.
- **`POST /reports/narrative`** writes plain-language and ISO narrative grounded in `report_grounding.py`. Any sentence with an untraceable number is stripped, and the template is used if more than 35% of the text is stripped.
- **Classification endpoints:** `POST /classify`, `/classify/batch` and `GET /classify/vocabulary/{kind}`.
- **Switches:** `GMG_LLM=0` and `GMG_LLM_ADJUDICATE=0` turn the model off. Tests always run with it off.
- **No-invented-numbers test:** `engine/test_llm_no_invented_numbers.py` uses adversarial fakes and checks three things:
  - classification and adjudication never change an amount; every amount is a user number times a cited constant;
  - narrative numbers trace to the grounding payload;
  - case-study impacts rebuild from the store and the user's amounts.

## 4. What was left out, and why

- **Apiculture foreground:** honey is rejected on the farm path. Building one would need hive materials, sugar feed and extraction-energy data for West Africa that we do not have. The WFLDB datasets are Swiss and US.
- **Producer prices for SN, BF and ZA:** on disk and registered, but not read. The recommendation economics code is denominated in Ghana cedis end to end (`price_ghs_per_kg`, `total_ghs`), so feeding it XOF or ZAR would mislabel the currency. It must be made currency-aware first.
- **Toxicity in the single score:** reported as midpoints, but not in the normalised single score. Adding them is a weighting choice (section 10).
- **Background water and land regionalisation:** ecoinvent elementary flows carry no location, so background water and land keep world CFs. Only foreground flows are regionalised.
- **Ghana electricity tariff JSON:** documented as unused, because the economics screen does not read it.
- **Production-system qualifier for fertilisers:** the identity gate deliberately treats "organic fertiliser" as a product, not a system.
- **No farm-gate dataset in the store:** cassava, yam and plantain. Their matches are flagged.
- **Classifier in the wizard UI:** the `/classify` endpoint exists, but the "did you mean X? confirm" prompt is not built. WS5's handoff describes the hook: call on blur of free-text fields.

## 5. Before and after: case studies

Baseline: `main` at 8024a2f. After: this branch at its final merge. Both runs used `scripts/run_case_studies.py` with the model off (`GMG_LLM=0`). Values are per kg of product. "new" means the category was not reported before:
- acidification for ReCiPe regions, and fossil depletion for CA, were silently dropped by the adapter;
- toxicity, ozone depletion and ionising radiation were not mapped;
- AWARE did not exist.

The single score now includes terrestrial acidification for ReCiPe regions, so single scores are not directly comparable with the baseline.

**Why the baseline cases moved**

- **Ghana maize/cowpea:**
  - **Global warming −6.1%.** Compost N now uses IPCC 2019 EF1 for "other N inputs" in wet climates (0.006 instead of 0.016), and biogenic CO2 in background datasets is no longer counted as fossil. These outweigh the additions: crop-residue N2O, purchased seed, transport of inputs, and pesticides counted as active ingredient.
  - **Marine eutrophication +19%.** Leaching of residue N.
  - **Water consumption.** Up, probably from the seed and pesticide supply chains (the inference is from the Canada breakdown; Ghana was not decomposed). The case is rainfed, so no field water is added.
- **Nigeria irrigated rice:**
  - **Global warming −3.2%.** EF1 for flooded rice (0.004, Table 11.1) replaces 0.016 on the fertiliser N. This outweighs the added residue N2O (R_AG 1.4), seed and transport. The biogenic fix contributes about −0.4%.
  - **Marine eutrophication +67%.** Leaching of residue N.
  - **Water consumption from 0.00016 to 1.38 m3/kg, and AWARE 11.3 m3 world-eq/kg.** Irrigation water was characterised as zero before. It is now the FAO crop-water-need estimate (no measured volume in the case): withdrawal times the 0.75 sprinkler application efficiency is consumed, characterised with Nigeria's AWARE agricultural factor of 8.0.
  - **Single score from 1263 to 6651.** Water consumption dominates it. **Biodiversity loss +62%:** ReCiPe endpoint damage from the same water.
- **Canada wheat (EF 3.1):**
  - **Global warming +24%.** Residue N2O from about 4.5 t/ha of straw (temperate aggregated EF1 0.010), purchased seed, pesticides counted as active ingredient, and transport of inputs.
  - **Land use −42%.** Canada's LANCA soil-quality factor (26.7) replaces the world average (50.2) for on-farm land.
  - **Water use from 0.009 to 0.32 m3 world-eq/kg.** Almost all from 40 t of wheat seed matched to the ecoinvent GLO "market for wheat seed, for sowing", whose global, partly irrigated supply chain carries about 8.9 m3 world-eq per kg of seed. This is a modelling choice the reviewer should confirm (section 10, item 21).
  - **Eutrophication, acidification and particulate matter up.** Residue N, plus the seed and transport supply chains.
  - **Fossil depletion.** Now reported; the EF name was previously unmapped.

**New regions**
- **Senegal groundnut, rainfed:**
  - **Climate 0.40.** Groundnut residue N2O at dry EF1 0.005, 6-20-10 NPK production, a seed rate typical of groundnut, and transport.
  - **Land use 8.4 m2a/kg.** National yield of about 1.3 t/ha.
- **Burkina Faso maize with compost:**
  - **Climate 1.02.** About 0.63 of this is farm-composting CH4 and N2O: 10 t of compost at IPCC 2006 Vol 5 Table 4.1, applied to compost mass (section 10, item 9).
  - The rest is NPK and urea, plus field N2O at dry EF1.
- **South Africa irrigated maize:**
  - **Climate 0.31.** Made up of:
    - pivot electricity: 82,500 kWh at Eskom's 1.04 kg CO2e/kWh, about 0.14;
    - urea and MAP production, about 0.1;
    - field N2O at dry EF1 with irrigated FracLEACH 0.24;
    - diesel combustion.
  - **AWARE 11 m3 world-eq/kg.** Estimated sprinkler water at South Africa's AWARE agricultural factor (40.8).

**ghana_maize_cowpea_intercrop** (single score 3582 -> 3886 uPt/kg)

| Category | Unit (per kg) | Before | After | Change |
|---|---|---|---|---|
| Terrestrial acidification | kg SO2-eq |  | 0.00374 | new |
| Global warming | kg CO2-eq | 1.8 | 1.69 | -6.1% |
| Freshwater ecotoxicity | kg 1,4-DCB-eq |  | 0.0402 | new |
| Marine ecotoxicity | kg 1,4-DCB-eq |  | 0.0573 | new |
| Terrestrial ecotoxicity | kg 1,4-DCB-eq |  | 3.66 | new |
| Fossil depletion | kg oil-eq | 0.268 | 0.276 | +3.2% |
| Freshwater eutrophication | kg P-eq | 0.000133 | 0.000142 | +7.1% |
| Marine eutrophication | kg N-eq | 0.0045 | 0.00535 | +18.7% |
| Human toxicity, cancer | kg 1,4-DCB-eq |  | 0.0596 | new |
| Human toxicity, non-cancer | kg 1,4-DCB-eq |  | 2.61 | new |
| Ionising radiation | kBq Co-60-eq |  | 0.0203 | new |
| Land use | m2a crop-eq | 9.73 | 9.79 | +0.6% |
| Mineral depletion | kg Cu-eq | 0.0192 | 0.0197 | +2.7% |
| Ozone depletion | kg CFC-11-eq |  | 3.01e-05 | new |
| Particulate matter formation | kg PM2.5-eq | 0.00171 | 0.00177 | +3.5% |
| Photochemical oxidation | kg NOx-eq | 0.00536 | 0.0055 | +2.7% |
| Water consumption | m3 | 8.58e-05 | 0.000742 | +764.8% |
| Water scarcity (AWARE) | m3 world-eq deprived |  | 0.0319 | new |
| Biodiversity loss | species.yr | 1e-07 | 1e-07 | +0.4% |

**nigeria_irrigated_rice** (single score 1263 -> 6651 uPt/kg)

| Category | Unit (per kg) | Before | After | Change |
|---|---|---|---|---|
| Terrestrial acidification | kg SO2-eq |  | 0.00145 | new |
| Global warming | kg CO2-eq | 2.16 | 2.09 | -3.2% |
| Freshwater ecotoxicity | kg 1,4-DCB-eq |  | 0.0146 | new |
| Marine ecotoxicity | kg 1,4-DCB-eq |  | 0.0189 | new |
| Terrestrial ecotoxicity | kg 1,4-DCB-eq |  | 1.31 | new |
| Fossil depletion | kg oil-eq | 0.102 | 0.103 | +0.5% |
| Freshwater eutrophication | kg P-eq | 5.02e-05 | 5.36e-05 | +6.9% |
| Marine eutrophication | kg N-eq | 0.00131 | 0.00219 | +66.8% |
| Human toxicity, cancer | kg 1,4-DCB-eq |  | 0.0222 | new |
| Human toxicity, non-cancer | kg 1,4-DCB-eq |  | 1.05 | new |
| Ionising radiation | kBq Co-60-eq |  | 0.00652 | new |
| Land use | m2a crop-eq | 2.41 | 2.43 | +0.7% |
| Mineral depletion | kg Cu-eq | 0.0083 | 0.00776 | -6.5% |
| Ozone depletion | kg CFC-11-eq |  | 4.88e-06 | new |
| Particulate matter formation | kg PM2.5-eq | 0.000704 | 0.000706 | +0.3% |
| Photochemical oxidation | kg NOx-eq | 0.00222 | 0.00225 | +1.1% |
| Water consumption | m3 | 0.000161 | 1.38 | +855904.9% |
| Water scarcity (AWARE) | m3 world-eq deprived |  | 11.3 | new |
| Biodiversity loss | species.yr | 3.01e-08 | 4.87e-08 | +61.8% |

**canada_wheat_conventional** (single score 743 -> 954 uPt/kg)

| Category | Unit (per kg) | Before | After | Change |
|---|---|---|---|---|
| Terrestrial acidification | mol H+-eq | 0.00179 | 0.00219 | +22.6% |
| Global warming | kg CO2-eq | 0.378 | 0.467 | +23.7% |
| Freshwater ecotoxicity | CTUe |  | 7.04 | new |
| Fossil depletion | MJ, net calorific value |  | 3.63 | new |
| Freshwater eutrophication | kg P-eq | 4.47e-05 | 6.36e-05 | +42.3% |
| Marine eutrophication | kg N-eq | 0.00718 | 0.0104 | +44.2% |
| Human toxicity, cancer | CTUh |  | 3.86e-10 | new |
| Human toxicity, non-cancer | CTUh |  | 6.63e-09 | new |
| Ionising radiation | kBq U235-eq |  | 0.00781 | new |
| Land use | dimensionless | 148 | 85.4 | -42.3% |
| Mineral depletion | kg Sb-eq | 1.92e-06 | 2.08e-06 | +8.6% |
| Ozone depletion | kg CFC-11-eq |  | 6.5e-09 | new |
| Particulate matter formation | disease incidence | 9.7e-09 | 1.28e-08 | +32.0% |
| Photochemical oxidation | kg NMVOC-eq | 0.00151 | 0.00163 | +7.8% |
| Water consumption | m3 world Eq deprived | 0.00903 | 0.322 | +3471.7% |
| Water scarcity (AWARE) | m3 world-eq deprived |  | 0.322 | new |

**New regions** (no baseline: regions did not exist)

| Category | Unit (per kg) | senegal_groundnut_rainfed | burkina_faso_maize_compost | south_africa_irrigated_maize |
|---|---|---|---|---|
| Global warming | kg CO2-eq | 0.4 | 1.02 | 0.307 |
| Marine eutrophication | kg N-eq | 0.000722 | 0.000103 | 0.00164 |
| Freshwater eutrophication | kg P-eq | 0.000122 | 4.52e-05 | 4.8e-05 |
| Terrestrial acidification | kg SO2-eq | 0.00294 | 0.000732 | 0.000694 |
| Land use | m2a crop-eq | 8.4 | 5.59 | 0.843 |
| Water consumption | m3 | 0.00104 | 0.000182 | 0.271 |
| Water scarcity (AWARE) | m3 world-eq deprived | 0.0447 | 0.0078 | 11 |
| Freshwater ecotoxicity | kg 1,4-DCB-eq | 0.0135 | 0.00973 | 0.00735 |
| Fossil depletion | kg oil-eq | 0.0643 | 0.0656 | 0.0444 |
| Single score | uPt/kg | 1973 | 1247 | 1717 |

## 6. Inputs now live, report-only, or removed

"Report-only" fields appear verbatim in `iso_report.scope.reported_metadata` and are labelled in the wizard as "for the report, does not change the numbers".

**Farm wizard**

| Field | Status | How it changes the result |
|---|---|---|
| pesticides (type, active ingredient, rate, applications) | live | AI-class production dataset, plus 100% of the AI to agricultural soil |
| target_pests, management_approach, uses_ipm, monitoring | report-only | |
| seeds (`seed_rate_kg_per_ha`) | live | FAO 2010 default by crop or category; vegetative and perennial crops excluded with a note |
| irrigation water (`irrigation_water_m3`) | live | measured, else FAO crop water need divided by application efficiency; withdrawal by source; consumed share on the regional AWARE flow |
| LPG | live | was modelled as diesel; now LPG production plus combustion |
| energy_sources (grid, diesel generator, solar, biogas, firewood, charcoal) | live | carrier-specific dataset; generator diesel de-duplicated |
| equipment power_source, fuel_efficiency, hours_per_year | live | for equipment without metered fuel (ASABE D497.7 default); manual, animal and solar burn nothing |
| equipment age | report-only | |
| packaging | live | logistics block, default 2 kg/t |
| transport of inputs | live | default 230 km by lorry (PEFCR v6.3 s.7.14) |
| transport to market | live | boundary becomes first point of sale |
| ammonium sulfate, CAN | live | own datasets and own N content |
| compost and manure source | live | purchased compost to the market dataset; farm-made compost adds composting CH4/N2O (IPCC 2006 Vol 5 Table 4.1); manure and residues are cut off |
| water_conservation_practices | report-only | |
| food.category | live | selects the default seed rate and crop water need when the crop name is unknown |
| foods[].land_use_change, residue_management, establishment | live (new) | dLUC, residue removal and burning, perennial amortisation |

**Processing request**

| Field | Status |
|---|---|
| facility_type, product_type | live (default conversion ratios) |
| processing_capacity, operational_hours_per_day, location_type | report-only (capacity check added to the data-quality warnings) |
| primary_energy_source, renewable_energy_percentage | live |
| secondary_energy_sources, backup_generator, energy_efficiency_measures | removed (use `fuel_streams`, which now accepts several) |
| water_source, water_treatment | live |
| water_conservation_measures | removed |
| wastewater_treatment | live ("None" means no treatment dataset plus a data-gap warning) |
| organic_waste_percentage | live |
| recycling_programs | removed |
| byproduct_utilization | live (the utilised share is cut off, burden-free) |
| local_sourcing_percentage | live (default inbound distance: local x 50 km + rest x 230 km) |
| supplier_sustainability_practices, seasonal_variation | removed |
| storage_practices | storage_loss_percentage live (applies to default ratios only); the rest removed |
| equipment_efficiency.* | removed |
| processing_steps[].duration, yield_efficiency, emissions_factor | removed |
| raw_material_inputs[].source_location | report-only |
| quality_requirements, seasonal_availability | removed |
| packaging.recyclable, quality_grade, market_destination | report-only (end-of-life is outside a cradle-to-gate boundary) |

## 7. Datasets: ingested and used, or documented as unused

The registry is `engine/lcia_reference/data_usage.json`, and `engine/test_reference_data_usage.py` fails on any unregistered item.

| Data | Status | Code path |
|---|---|---|
| `data/canonical/lca_engineer.sqlite` | used | every solve and characterisation |
| `data/AWARE2.0/` (WULCA corrected country file, AWARE 1.2c values, World 42.95 = EF pack) | ingested and used | `engine/water_scarcity.py`, `engine/lcia_reference/aware_country_cfs.json` |
| `data/LANCA/` (De Laurentiis 2019 mmc2) | ingested and used | `engine/land_use_regional.py`; the store's EF 3.1 land-use CFs equal the world SQI, checked by a test |
| `data/USEtox_2.14/` | ingested as reference (`gmg_usetox_cfs`, `usetox_pesticide_cfs.json`) | toxicity is characterised with the method pack so background and foreground use one model |
| `data/IPCC GWP/` | used as reference | `engine/gwp_basis.py` reads the factors in the store; the ISO reports state the basis |
| `data/ReCipe2016/` | used | ReCiPe normalisation factors; CF reconciliation |
| `data/EVvinronmental_Footprint_EF3.1/` | used for CF reconciliation | no normalisation factors on disk (JRC 2024 cited instead) |
| `data/References_C/` FEDEFL, GLAD, ILCD | used for flow QA | `engine/test_flowmap_qa.py`; the FEDEFL and GLAD folders on disk are empty, so identity is checked through the store's `fed_id` |
| `data/recommendations/Tier1`, `Tier2` | used, or documented per file | SRID price CSV loaded by `engine/recommend/prices.py` and a test |
| `engine/case_studies/*.json` (6) | used | `scripts/run_case_studies.py`; extraction exercised by a test |
| `ghana_*`, `nigeria_*`, `senegal_*`, `burkina_faso_*`, `south_africa_*` activity defaults, grid EF, yield guides | used | `activity_defaults.py`, `grid_calibration.py`, `regional_benchmark.py` |
| `ipcc_stock_change_factors_gh.json` | used | `engine/land_use_change.py` |
| `*_producer_prices.json` (SN, BF, ZA) | documented unused | economics is GHS-only (section 4) |
| `ghana_electricity_tariff.json` | documented unused | not read by the economics screen |
| `data/canonical/lca_engineer.sqlite.gz` | documented unused | compressed transport copy |

## 8. PM mapping files

`docs/inventory_mapping/GMG_inventory_database_mapping.json` and `GMG_inventory_mapping_summary.json` were regenerated with the executed matcher (adjudication off) for all six regions.
- **Rows:** 50 farm inputs, 44 shared processing inputs and 29 raw materials per region, 738 in total.
- **History:** each row keeps `matched_process_at_45ad6b6`. Of the 174 rows that existed then, 75 now match a different dataset.
- **Flagged rows:** 18 rows need review: Bio-fertilizer, Foliar and "None" fertiliser in every region.
- **Citation checks:** 45 of the 295 file:line references were opened and checked; all 115 matched uids exist in the store.
- **Regenerating:** `.venv/Scripts/python.exe scripts/regenerate_inventory_mapping.py`. The executed sections regenerate; the prose is hand-maintained.

## 9. Verification

All runs on the final branch head, with `GMG_LLM=0` and `GMG_LLM_ADJUDICATE=0` (no model calls).

| Check | Baseline (`main`) | Final |
|---|---|---|
| `pytest engine app ingestion` | 126 passed, 1 skipped, 3 failed | 522 passed, 1 skipped, 3 failed (the same 3 baseline failures) |
| Rust `cargo test --release` | 4 passed | 18 passed |
| Case studies end to end | 3 of 3 | 6 of 6 |
| Matcher regression (738 rows, offline) | n/a | passes |
| Frontend `npx tsc --noEmit` | n/a | clean |
| Added lines containing U+2014 since `main` | n/a | 0 |
| Control characters in changed files | n/a | 0 |
| Committed API keys | n/a | none (one deliberately fake test key in `engine/test_llm_classify.py`) |

WS5 ran its live smoke test once (`GMG_LLM_LIVE=1`), and it passed. Everything else runs offline.

## 10. Open items for a human LCA reviewer

**Value choices the engine makes by default, to confirm or override**

1. **Allocation:**
   - Processing by-products: the utilised share is cut off (burden-free), not allocated. Economic or mass allocation is the usual alternative for palm kernel, cocoa shell and bran.
   - Manure and crop residues used as inputs are cut off.
   - Intercrops are split into product systems by area share.
2. **GWP basis:**
   - Each method keeps its native basis: ReCiPe 2016 uses AR5 with climate-carbon feedbacks (N2O 298, CH4 34 non-fossil and 36 fossil); EF 3.1 uses AR6 (N2O 273, CH4 27.0 and 29.8).
   - Refrigerants use AR6 even under ReCiPe.
   - Switching ReCiPe to AR6 would lower N2O-dominated results by about 8%.
3. **Cut-off rules:**
   - capital goods follow the background datasets;
   - manure and residues are cut off;
   - end-of-life of packaging is outside the cradle-to-gate boundary;
   - dLUC is 0 unless declared;
   - no carbon gains are credited.
4. **Single score:**
   - 10 categories, equal weighting.
   - Toxicity, ozone depletion and ionising radiation are reported but not included.
   - The bands are tertiles of 20 ecoinvent crops under ReCiPe and are only indicative for EF 3.1.

**IPCC Tier 1 judgement calls**

5. **EF1 for irrigated land in dry climates:**
   - Irrigation other than drip moves FracLEACH to the wet value (p 11.25), but EF1 stays at the dry value (0.005).
   - Confirm whether Table 11.1's footnotes require the wet EF1 for irrigated dry-climate land.
   - This mainly affects the South Africa irrigated maize case.
6. **Nigeria climate:** wet nationally (0.016). The Sudan and Sahel north is dry. `regions.with_climate(NG, "dry")` exists, but the API does not yet pick it by state.
7. **South Africa climate:** dry by default (Highveld P:PET below 1). Wet provinces (for example KwaZulu-Natal) need `with_climate(ZA, "wet")`.
8. **Crop-residue proxies:**
   - Crops with no Table 11.1A row (vegetables, cassava, sesame, cotton, cocoa, oil palm) use the generic row, with dry matter from USDA.
   - Sugarcane uses Hassuani 2005.
9. **Farm composting factors:** IPCC 2006 Vol 5 Table 4.1 gives them per kg of waste treated (wet). The code applies them per kg of compost spread, which probably understates the emissions. It drives most of the Burkina Faso maize climate result.

**Screening defaults with medium or low pedigree**

10. Inbound transport of 230 km (PEFCR v6.3, cited at medium confidence; verify the section).
11. The wet-season irrigation share of 0.5 is a GMG assumption.
12. Wastewater share 0.8 (legacy).
13. Firewood moisture 15% has no source.
14. The kerosene and biodiesel densities were cited from memory (UK DESNZ) and need checking against the document.
15. Perennial establishment input share of 1.
16. Vegetable seed uses a carrot-seed proxy.
17. Nigeria's pump diesel is inherited from the Ghana table and flagged.
18. **Grid factors:**
    - Senegal uses an operating margin, not an average.
    - Burkina Faso's is generation-only (no imports or T&D losses).
    - Nigeria's is lifecycle at generation, with no T&D.
    - Ghana's is a CDM-style factor; see `engine/grid_calibration.py` for why it is accepted.
19. The flooded-rice water figure for Nigeria is a FAO crop-water-need estimate with sprinkler efficiency. A measured volume should replace it in real assessments.
20. **Data defects outside the code:**
    - The ReCiPe natural gas normalisation row (0.40 kg oil-eq per person per year) looks like a unit slip in the published file.
    - The store's FEDEFL id for "Phosphorus" to water is "orthophosphate".
    - PM2.5 has no FEDEFL id.
    - None of these affect the on-farm path any more.
21. **Seed datasets:**
    - Purchased seed matches the ecoinvent GLO seed markets, whose global, partly irrigated supply chains dominate water use for rainfed farms (Canada wheat).
    - Own-saved or local seed could instead be modelled as the crop's own regional production.
    - Vegetable seed uses a carrot-seed proxy.
22. **Pre-existing test failures (3) on `main`, unchanged:**
    - two `engine/recommend/test_economics.py` tests (the module imports `matcher` as a top-level name);
    - `engine/test_method_toggle.py::test_recharacterize_from_payload_uses_stored_inventory`.

## 11. Housekeeping

- **Workstream branches and worktrees:** the branches (`ws1-foreground`, `ws2-inputs`, `ws3-data`, `ws3b-regions`, `ws4-matching`, `ws5-intelligence`) are merged and remain locally. Their worktrees in `C:\Users\Windows\Desktop\Dev_Projects\gmg_wt\` contain directory junctions to the shared `data/` and `node_modules` and a hard link to `app/.env`.
- **Removing the worktrees safely:**
  1. Delete each junction with `cmd /c rmdir <path>`. That removes the link only.
  2. Delete each `app\.env` hard link.
  3. Only then run `git worktree remove`.
  
  A recursive delete through a junction could delete the shared data.
- **Push status:** nothing has been pushed.
