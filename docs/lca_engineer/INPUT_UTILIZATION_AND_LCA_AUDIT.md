# Farmer input utilization & LCI/LCIA rigor audit

Date: 2026-11-25. Scope: farm production assessment (wizard → `app/production` → `engine/` → Rust kernel), with notes on processing.

Method: five parallel investigations: (1) field tracing for Farm Profile + Crop Details, (2) field tracing for Management, Pest and Equipment/Energy, (3) LCI audit against openLCA/Brightway practice, (4) LCIA audit with numeric CF checks, (5) an **empirical one-at-a-time sensitivity sweep** (~190 perturbations each on a Ghana irrigated maize farm and a Nigeria irrigated rice farm through the real `/assess` path, offline, Rust kernel `server.exe`). Sweep scripts and raw results: `.scratch_sensitivity/` (start with `SENSITIVITY_REPORT.md`, `sanity_results.md`, `results_summary_tables.md`).

Test status at audit time: `pytest engine` gave 428 passed, 4 failed, 1 skipped (matcher golden drift: the Canada PV input now matches a Yukon dataset; two `test_economics` import-path errors; one outdated test, `test_recharacterize_from_payload_uses_stored_inventory`).

---

## 1. Verdict

**Inputs are heavily underused.** Of about 100 farmer-editable wizard fields, only about 30 change any impact number.
- About 45 fields that reach the API produce **exactly 0% change** in every impact category (proved empirically).
- About 35 more are **dropped in the browser** by `transformEnhancedAssessmentToBackend` (`african-lca-frontend/src/lib/api.ts:497-627`) and survive only in `form_snapshot`, which the engine never reads.

**The calculation core is sound. The farm field inventory is not at LCA-officer level.**
- **Rigorous:**
  - The background is a real matrix solve (`ingestion/query.py:295-372`, `T·s=f`, `g=B·s`, residual-checked, signs validated against openLCA).
  - CFs come from the ecoinvent 3.11 ReCiPe 2016 / EF 3.1 method packs; 1,070+ factors were checked with no discrepancies.
  - The IPCC 2019 N₂O Tier 1 parameters are correct.
  - AWARE and LANCA are regionalised.
- **Not rigorous:** the foreground field-emission model is a GHG-only Tier 1 model. Compared with what an LCA officer would build in openLCA or Brightway using the ecoinvent/AGRIBALYSE/WFLDB agricultural models, it is missing:
  - NH₃
  - NOx
  - P losses
  - heavy metals
  - urea and lime CO₂
  - erosion
  - soil-carbon change from management

  So acidification, eutrophication (freshwater, marine, terrestrial) and particulate matter are near-zero on the farm side and come almost entirely from background data. The benchmark basket is ecoinvent crops that *do* include these flows, so farms are biased toward "Low" bands.

---

## 2. Input utilization: what is and isn't used

Classes: **A** = drives the LCI/LCIA; **B** = report/recommendations/AI text only; **C** = sent but never read; **D** = dropped before the backend; **E** = partly used or overridden by a default.

### 2.1 Fields that actually drive results (A)

| Field | Max effect (sweep) | Notes |
|---|---|---|
| `country` → region | 52-106% | The only geography the engine sees |
| crop `name` | up to 50% | Free text with substring matching; a typo falls back to the generic residue row |
| `areaAllocated`, `annualProduction` | 50% (FU) | Production is the per-kg denominator |
| `seedRateKgPerHa` | 7-10% | |
| land-use change: previous land use, years since conversion | up to 543% | A blank years value becomes 0, which charges the full loss |
| residue removed and burnt fractions | 2-7% | |
| intercrop pattern and partners | 14% | Through the 20% legume credit, which is questionable (see 3.6) |
| compost use, source, rate | 11-50% | N₂O only |
| fertiliser type, NPK, rate, applications | 43-73% | |
| irrigation system, m³, water source | ~100% water | |
| equipment type, power, hours, L/h | 52-108% | |
| energy sources, fuel type and amount | 13-218% | |
| pesticide active ingredient, content, rate, applications | 7-24% | |
| packaging, distance to market, input transport km | 2-12% | Only in the working tree; committed HEAD drops `logistics` in `_build_farm_rust_input` |

### 2.2 Fields with zero numeric effect, though they reach the API (B/C, proved by the sweep)

- **Farm profile:** `farmerName`, `farmName`, `totalFarmSize`, `farmingExperience`, `farmType`, `primaryFarmingSystem`, `certifications`, `participatesInPrograms`.
- **Crop:** `variety`/`crop_type`, `production_system`, `cropping_pattern` without partners, `post_harvest_losses` (a hidden hard-coded 10% that is printed in the report), `establishment.*` for anything other than cocoa and oil palm.
- **Soil:** `soil_type` (used only when land-use change is declared), `conservationPractices` (no-till, mulching, terracing, bunds, contour, trees), `soilTestingFrequency`.
- **Fertiliser:** `soilTestBased`, `followsNutrientPlan`, `cost`.
- **Water:** `waterConservationPractices`, including "Alternate wetting and drying".
- **Pests:** `managementApproach`, `usesIPM`, `pestMonitoringFrequency`, `pesticideType` (even when the active ingredient is unknown).
- **Equipment:** `age`, all costs.
- **Request:** `run_uncertainty` (unticking it does nothing).

### 2.3 Fields collected in the wizard but never sent (D)

- **Profile:** admin `region`, `coordinates` (no input), `localName`.
- **Seasonality:** `plantingMonths`, `harvestingMonths`, `growingPeriod`, `cropsPerYear`. `season` is always sent as `WetSeason`.
- **Rotation:** `rotationSequence`/`rotationDuration`, `intercroppingRatio`, `averageYieldPerHectare`. The backend rejects `rotation_sequence` with a 422, so the engine's legume-rotation code in `field_model.py:126` is dead.
- **Soil:** `soilpH` and `organicMatterContent` (the UI defaults them, `api.ts` never maps them), cover crops (schema only, no UI).
- **Fertiliser:** `applicationMethod`, `timingStrategy`, `brandName`.
- **Pests:** pesticide `brandName` (even though `pesticides.py:76-82` has a brand synonym table), pests, diseases, IPM practices, biological controls, `usesEconomicThresholds`.
- **Storage and access:** `storageCapacity` (a *required* field), `storageFacilities`, `roadAccess`, transport cost.
- **Water:** `drainageSystem`.
- **Assessment parameters:** the whole `assessmentParameters` block (functional unit, boundary, period, uncertainty, sensitivity, benchmark). The UI implies these change the study; they do not.

### 2.4 Places where the farmer's value is silently overwritten

1. **Yield overwritten.** `CropDetailsStep.tsx:162-168` writes a generic table yield into `annualProduction` whenever the crop name changes (every keystroke) or the area field loses focus. Yield is the most sensitive parameter (it is the functional-unit denominator and drives residue N).
2. **Whole form overwritten.** Changing `country` replaces the entire form with the example farm (`FarmProfileStep.tsx:48-69`, `reset({...current, ...example})`).
3. **Farm type overwritten.** `farmType` is reset from farm size on every mount (`FarmProfileStep.tsx:74-86`), so "Cooperative" or "Mixed livestock" never sticks.
4. **Zero applications counted as one.** `applicationsPerSeason = 0` is counted as 1 in Python (`inputs.py:221`, `pesticides.py:117`) but as 0 in Rust, so the two paths disagree.

---

## 3. LCI rigor: gaps compared with what an LCA officer would model

| # | Area | Status | Evidence | Reference |
|---|---|---|---|---|
| 3.1 | **Field NH₃ / NOx** | Missing | `rust_kernel.py:29-41` `SUBSTANCE_MAP` has no Ammonia/NOx. `lci.rs:494-497` computes volatilised N only to derive indirect N₂O. The `flowmap.py:34-35` entries are never produced. The sweep's N balance is missing ~50 kg NH₃-N | EMEP/EEA 2019 3.D; Nemecek & Schnetzer 2011 |
| 3.2 | **Urea / lime CO₂** | Missing | No IPCC Eq 11.12/11.13. Rust books urea CO₂ as "production" (`lci.rs:160`) and `rust_kernel.py:59,109` drops all "production" CO₂. The Canada wheat case misses ~42 t CO₂ | IPCC 2019 Vol 4 Ch 11 |
| 3.3 | **Rice CH₄** | Incorrect | Flat `200.0` kg/ha/season (`lci.rs:197`) for any name containing "rice" (`lci.rs:673-676`), including upland rice, which the N₂O code treats as non-flooded. The sweep found AWD vs flooded ratio = 1.000 | IPCC 2019 Vol 4 Ch 5 Eq 5.1-5.3 (EFc 1.19 kg/ha/day × days × SFw × SFp × SFo) |
| 3.4 | **P losses, heavy metals, erosion** | Missing | No SALCA-P or SALCA-SM; freshwater eutrophication has no field term | Prasuhn 2006; ecoinvent agri guideline |
| 3.5 | **Soil carbon from management** | Missing | Tillage factor fixed at 1.0 (`land_use_change.py:140-142`); conservation practices never read | IPCC 2019 Vol 4 Ch 5 Table 5.5 (F_MG, F_I) |
| 3.6 | **Legume intercrop credit** | Incorrect | `field_model.py:49` `LEGUME_N2O_CREDIT = 0.20` reduces N₂O from fertiliser the farmer *actually applied*. That double counts: any N saving is already in the declared rate. It also does not reduce fertiliser production burden, so it is internally inconsistent | IPCC 2019 Eq 11.1 |
| 3.7 | **Fertiliser dataset basis** | Incorrect | Amounts are kg of *product*, but the matcher picks *nutrient-basis* datasets: Muriate of Potash → "inorganic potassium fertiliser, as K₂O" (`golden/matcher_golden.json:186-188`), ~1.67× too high. Foliar → "NPK as P₂O₅", ~6.7× too high. "None" → "as N" / "as K₂O" phantom burden. There is no product→nutrient conversion anywhere in `engine/`. Every NPK grade matches 15-15-15 | ecoinvent dataset reference units |
| 3.8 | **Energy double counts** | Incorrect | `activity_defaults.has_measured_fuel` (`:231-233`) ignores *estimated* machinery diesel, so regional default diesel is added on top of the ASABE tractor estimate. Pumped irrigation defaults stack on `_irrigation_inputs`. Bucket/manual irrigation gets motor-pump energy. Reproduced in the sweep |, |
| 3.9 | **Multi-crop attribution** | Incorrect | `service.py:114-135` gives every crop the whole farm's fertiliser and pesticide rate per ha (in the Ghana maize-cowpea case, cowpea gets maize's NPK and urea) | ISO 14044 §4.3.4 (subdivision first) |
| 3.10 | **Crops per year** | Missing | Not sent, so double-cropped farms count inputs and CH₄ once against two seasons of production (per-kg impact likely ~50% low) | IPCC Eq 5.1 sums seasons |
| 3.11 | **Climate zone** | Weak | National wet/dry only. Kano (dry) gets EF1 0.016 and FracLEACH 0.24 instead of 0.005 and 0. `regions.with_climate()` exists but is only called in tests | IPCC 2019 Table 11.1 fn. 4 |
| 3.12 | **FracGASF by fertiliser type** | Weak | Aggregate 0.11 used. Urea 0.15, ammonium 0.08 and nitrate 0.01 are documented in `regions.py:24-25` but unused | IPCC 2019 Table 11.3 |
| 3.13 | **Organic N** | Weak | Compost and manure get N₂O only; no NO₃ or NH₃. Possible double entry when manure is listed both as a fertiliser and as compost | |
| 3.14 | **Functional unit** | Weak | Fresh mass with no moisture standard. The multi-crop headline divides the farm total by summed kg of different crops | ISO 14044 §4.2.3.2 |
| 3.15 | **Co-products** | Missing | No straw/stover allocation | ISO 14044 §4.3.4.2; AGRIBALYSE/WFLDB economic allocation |
| 3.16 | **Boundary text vs code** | Inconsistent | `iso_report.py:370-372` says input transport is excluded; `inputs.py:421-436` adds 230 km, on top of `market for` datasets that already include transport. The report also claims machinery is included, which is only true via the diesel dataset | |
| 3.17 | **Background dataset selection** | Weak (reproducibility) | `orchestrator.py:367` auto-commits the top embedding match; `needs_review` inputs still enter results; the golden test has drifted | openLCA product system = frozen choice |
| 3.18 | **Uncertainty** | Screening | All field flows share one lognormal multiplier; no CF or parameter uncertainty; the pedigree GSD convention may be squared twice | Ciroth et al. 2016 |
| 3.19 | **Diesel LHV** | Minor | 38.7 MJ/L vs ~36 MJ/L (43 MJ/kg × 0.84 kg/L), so ~7% high | IPCC 2006 Vol 2 |
| 3.20 | **dLUC default** | Weak | Unknown history defaults to "no conversion" | PAS 2050-1 / Blonk dLUC tool statistical default |

---

## 4. LCIA rigor

**Rigorous:**
- Characterisation is effectively `h = C·g` on the merged inventory (`query.py:442-522`).
- These CFs were verified against published values:
  - EF 3.1: N₂O 273, CH₄ fossil 29.8 / non-fossil 27.0, NH₃ acidification 3.02 mol H⁺, NO₃ marine 0.226, PO₄ 0.33.
  - ReCiPe 2016 H: N₂O 298, CH₄ 34/36, NH₃ 1.96.
- N₂O-N→N₂O (44/28) and NO₃-N→NO₃ (62/14) conversions are correct.
- Biogenic CO₂ is treated consistently as 0/0.
- AWARE (Boulay 2018, country agri CFs on *consumption*) and LANCA soil quality (De Laurentiis 2019) are keyed off the region.

**Problems:**
1. **Categories computed but discarded.** `adapter.py:14-46` `MIDPOINT_MAP` drops EF terrestrial eutrophication and ReCiPe terrestrial photochemical ozone. EF toxicity, ozone depletion and ionising radiation have no normalisation factors, so they don't reach the single score.
2. **Equal weighting.** The single score is equal-weighted (`adapter.py:239`). EF 3.1 has official weighting factors (CC 21.06%, PM 8.96%, WU 8.51%, …). The ReCiPe "equal-weight midpoint sum" is not an official ReCiPe score.
3. **Score bands.** Bands are calibrated on ReCiPe only and reused for EF. The benchmark basket includes NH₃, P and heavy metals that farms omit, so farm results are biased low. ISO 14044 §4.4.5 forbids weighting in public comparative assertions.
4. **Wrong refrigerant GWPs** (`refrigerants.py:34-38`), labelled AR6:

   | Blend | Code | AR6 |
   |---|---|---|
   | R-404A | 3728 | ≈ 4728 (likely a 1000 typo) |
   | R-507A | 3985 | ≈ 4775 |
   | R-448A | 1387 | ≈ 1494 |
   | R-449A | 1397 | ≈ 1504 |
   | R-513A | 631 | ≈ 672 |

5. **Pesticide emission split.** 100% to soil (ecoinvent convention) is used even when EF 3.1 is selected, while PEF specifies 90/9/1.
6. **Grid calibration.** `grid_calibration.py:23-26` adds only fossil CO₂ to hit the official grid EF. SO₂, NOx, PM and fossil resource use don't scale with it.
7. **Duplicate water row.** The same AWARE number is shown twice under EF ("Water consumption" and "Water scarcity").
8. **Legacy Rust LCIA.** `lca.rs`, `lci_extended.rs` and `processing/lca.rs` are served when `USE_LEGACY_RUST_LCIA=1`. They mix AR5 and AR6 (CH₄ 28 labelled "AR6"), use NOx 0.70 SO₂-eq vs ReCiPe 0.36, AWARE Ghana 20 vs 16.84, and invent endpoint factors. Quarantine or delete them.
9. **No openLCA/Brightway export.** `research_export.py:45` exports the top-30 display table (sorted by raw amount across mixed units), not `engine_inventory`. Flows lack compartment and CAS. There is no JSON-LD, ILCD or EcoSpold export, so an LCA officer cannot reproduce the study.
10. **No sensitivity analysis.** `sensitivity_analysis` is only the on-farm vs supply-chain split.

---

## 5. Empirical sanity checks (sweep, working tree)

| Check | Result |
|---|---|
| Synthetic N ×2 → direct N₂O ×2 (Tier 1 linear) | **PASS**: 6.115 → 12.229 kg, matching the hand calculation |
| Yield ×2 → per-kg impact ≈ ½ | **PASS**: ×0.514 (residue N scales with yield) |
| Area ×2 with same per-ha inputs → per-kg impact unchanged | **PASS**: 0.000% |
| Region switch changes grid EF and AWARE | **PASS**: grid 0.35 (GH) to 1.04 (ZA) kg CO₂e/kWh; AWARE 8.0 (NG) to 80.8 (SN) |
| Irrigation volume ×2 → AWARE ×2 | **PASS**: +99.8% |
| Rice flooded → AWD lowers CH₄ | **FAIL**: ratio 1.000; "Upland Rice" still gets 2,400 kg CH₄ |
| Legume BNF not counted as an N₂O source | **PASS** |
| N balance closes | **FAIL**: no NH₃ flow (~50 kg NH₃-N missing); compost N never leached (90.0 vs 109.2 kg NO₃-N) |

Other bugs found by the sweep:
- **Transport mode:** "Pickup truck" is modelled as a lorry, because `"truck"` matches before `"pickup"` in `inputs.py`.
- **Generator de-duplication:** it only works on an exact string match (+136% to +271% when the text differs).
- **Fuel suppression:** a metered fuel suppresses every equipment estimate on the same fuel (−83%).
- **Wrong units:** grid electricity entered in L is silently excluded.
- **Missing fuel unit in HEAD:** LPG in kg was read as litres.

---

## 6. Recommendations, prioritised

Effort: S = under 1 day, M = 1-3 days, L = 1-2 weeks.

### P0: correctness (results are wrong today)

1. **Stop overwriting the farmer's yield** (S). In `CropDetailsStep.calculateYield`, only write `annualProduction` when it is empty or 0; otherwise show the estimate as a hint. *Why:* yield is the functional-unit denominator; a silent overwrite invalidates every per-kg result.
2. **Fix the fertiliser dataset basis** (S-M). In `inputs._fertiliser_inputs`, convert kg product → kg nutrient when the matched dataset name contains `as N` / `as P2O5` / `as K2O`, using the NPK grade or type defaults (KCl 60% K₂O). Skip "None" rows, and scale NPK burden by grade. *Why:* potash is currently ~1.67× too high and foliar ~6.7× too high (proof: `matcher_golden.json:186-188`; no conversion exists in `engine/`).
3. **Remove the energy double counts** (S). In `has_measured_fuel`, treat diesel derived from declared equipment as covering field operations. Make `_irrigation_inputs` return nothing for bucket/manual systems, and skip pumped activity-default rows when pumping was already added.
4. **Replace the flat rice CH₄** (M) with IPCC 2019 Eq 5.1-5.3:
   - send `growingPeriod`;
   - map the water regime from `production_system`, `irrigationSystem` and the AWD practice (which is already collected and currently ignored);
   - set SFo from compost and straw;
   - give upland rice zero CH₄.
5. **Remove the 20% legume intercrop N₂O credit** (S). `field_model.py:49` conflicts with IPCC Eq 11.1 and double counts.
6. **Attribute inputs per crop** (M). Add per-crop fertiliser, pesticide and compost assignment instead of copying farm rates to every crop (`service.py:114-135`).
7. **Send `cropsPerYear` and multiply seasonal inputs by it** (S-M), in both `inputs.py:222` and `lci.rs:369`, and for seed, pesticides and CH₄. Relabel the fertiliser rate as "per application" or stop multiplying by applications.
8. **Fix the perennial crash path** (S). `perennials.py:76-79` calls `float(None)` when `input_share` is blank. Extend `PERENNIALS` beyond cocoa and oil palm (mango, citrus, cashew, coffee, plantain).

### P1: missing field emissions (needed for ecoinvent/AGRIBALYSE parity)

9. **Emit NH₃ and NOx** (M):
   - NH₃ = N × FracGASF (type-specific, IPCC 2019 Table 11.3) × 17/14 for synthetic N, and FracGASM for organic N, including compost and manure.
   - Add `"Ammonia": "NH3"` to `SUBSTANCE_MAP`.
   - Later: EMEP/EEA Tier 2, which needs `soilpH` and `applicationMethod` (both already collected; just send them).
   - NOx = 0.21 × N₂O (ecoinvent convention).
10. **Add urea and lime CO₂** (S). Use IPCC Eq 11.13 and 11.12 under a distinct substance key so the "production" filter can't drop them. Add a liming input to the wizard.
11. **Add SALCA-P (runoff, erosion, leaching) and erosion** (L). Drive them from P₂O₅ in the NPK grade, `soil_type`, and terracing/bunds/contour from `conservationPractices` (already collected).
12. **Add nitrate leaching for compost and manure N, and close the N balance** (S). Add an N-budget test.
13. **Add residue-burning pollutants** (S): PM2.5, CO, NOx, NMVOC (EMEP/EEA 3.F).

### P2: use the data already collected

14. **Climate zone from admin region** (S-M). Send `farmProfile.region` as `study_meta.admin_region` and apply `regions.with_climate()` through an admin-region → wet/dry table. Use the same table for the land-use-change forest zone.
15. **Soil carbon from management** (M-L), reported separately per ISO 14067. Use IPCC Tier 1 F_MG and F_I from `conservationPractices` (no-till, min-till, mulching), residue removal, compost and cover crops (add the UI field), over 20 years with a "practice adopted N years ago" field. *Why:* these are the practices farmers are asked to change, yet today they move nothing.
16. **Season from months** (S). Derive wet or dry season from `plantingMonths`/`harvestingMonths`; today it is always `WetSeason`, which halves dry-season irrigation estimates (`crop_defaults.py:80`). Later: monthly AWARE.
17. **Pesticides** (S). Send `brandName`, which feeds the existing synonym table. Use `pesticideType` for class-level datasets when the active ingredient is unknown. Don't treat bio-pesticide product mass as synthetic active ingredient.
18. **Rotation** (S). Add `rotation_sequence` to the `FoodItem` model and the UI so `field_model._has_legume_partner` can work, applied as residue-N carry-over, not as a credit.
19. **Storage** (S-M). Use `storageFacilities`: cold storage brings electricity plus refrigerant leakage; hermetic bags and silos are materials. Make `storageCapacity` optional unless it is used.
20. **Remove or wire `assessmentParameters`** (S). Today the UI implies choices that do nothing. At minimum, honour `run_uncertainty`.
21. **Make the country change prefill only an empty form, and stop the `farmType` override** (S).

### P3: LCIA, reporting, reproducibility

22. **Report all 16 EF 3.1 categories** plus ReCiPe terrestrial photochemical ozone (S). Use the official EF 3.1 weighting factors for the EF single score, or rename the score "equal-weighted normalised sum". Calibrate bands per method against a basket modelled with the same field-emission model.
23. **Fix the refrigerant GWPs to AR6 values** (S).
24. **Use the EF/PEF 90/9/1 pesticide split when EF is selected** (S). Scale the whole grid inventory, not just CO₂, during calibration. Remove the duplicate AWARE row.
25. **Quarantine the legacy Rust LCIA** (S-M). Rust should only be the emission-inventory kernel, with no CO₂-eq aggregation and no source-string merging (`lci.rs:793-802`) that Python then filters on.
26. **Export the full elementary-flow inventory** per functional unit (UUID, name, compartment, CAS, unit, amount) as openLCA JSON-LD or Brightway-compatible CSV, from `research_export.py` (M). *Why:* this is the single biggest step toward "reproducible by an LCA officer".
27. **Freeze background dataset choices** in a versioned input→dataset table (the equivalent of an openLCA product system). Block publication while any input is `needs_review`, and fix the golden-test drift (M).
28. **Functional unit** (M). Use a moisture-standardised reference flow per crop; never show a mixed-crop per-kg headline. Allocate straw and stover co-products economically when they are removed or sold.
29. **Boundary text** (S). Generate it from the input list actually used, and apply the 230 km default only to production, not `market for`, datasets.
30. **Uncertainty and sensitivity** (M). Give field parameters their own distributions (IPCC ranges for EF1, FracLEACH, EF4, EF5). Package one-at-a-time sensitivity (the `.scratch_sensitivity` harness is a ready starting point) and a method sensitivity (ReCiPe vs EF vs IPCC 2021) in the report.

### Quick wins (all S, high value)

#1 yield overwrite, #2 fertiliser basis, #3 energy double counts, #5 legume credit, #8 perennial crash, #10 urea CO₂, #12 compost NO₃, #23 refrigerant GWPs. After these, #9 (NH₃) is the most important modelling addition.
