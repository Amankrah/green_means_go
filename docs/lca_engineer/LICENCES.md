# Source Licences - recommendation corpus

> **Purpose.** One row per source feeding the abatement-measure library
> ([`engine/recommend/measures.jsonl`](../../engine/recommend/measures.jsonl)) and the
> price/feasibility feeds. The recommendation layer must check the `use` column before
> quoting a source's text, and **must not ship a measure whose licence is `blocked` or
> `unconfirmed` in a commercial deployment** until that status is resolved.
>
> This mirrors the per-dataset licence discipline [`DATABASE_PLAN.md` §5](./DATABASE_PLAN.md)
> already mandates for the LCI/LCIA data. Status verified 17 July 2026.

Legend - `use`: **clean** (reuse incl. commercial) · **cite** (derive numbers, attribute, don't redistribute text) · **nc** (non-commercial only - blocks a commercial Green Means Go) · **permission** (written permission needed first) · **unconfirmed** (verify before ingest).

## Measure-library sources

| `provenance.source` key | Source | Licence | `use` | Notes |
|---|---|---|---|---|
| `IPCC-2019` | IPCC 2019 Refinement, Vol 4 (AFOLU) | Not CC; non-commercial only | **permission** | Product use needs written permission from copyright@ipcc.ch (~4wk). Measures citing this are **not cleared for a commercial launch** until granted. Numbers used here are Tier-method-level, but confirm. |
| `Ecological-Processes-EastGonja` | *Ecological Processes* (Springer), East Gonja N-inhibitor study | Journal copyright | **cite** | Effect size (N₂O −30%) is a fact; quote span attributes it. Do not redistribute the article. |
| `Ghana-CSAIP` | World Bank, Climate-Smart Agriculture Investment Plan for Ghana | CC BY 3.0 IGO **not confirmed on this copy** (served from `documents1`, not OKR) | **unconfirmed** | Very likely CC BY 3.0 IGO; verify before commercial use. Figures are portfolio-level. |
| `CCAFS-CSA-Ghana` | CCAFS, CSA Practices in Ghana (Botchway et al. 2016) | **CC BY-NC 4.0** (confirmed) | **nc** | ⚠️ The NC clause **blocks commercial use**. If Green Means Go is commercial, either drop these measures or source the practice elsewhere. Qualitative only - no effect sizes taken. |
| `SNV-Ahotor` | SNV / ScienceDirect S2949824424000417, Ahotor oven | Mixed (SNV + journal) | **cite** | Efficiency figure attributed; article not redistributed. |
| `SNV-gari` | SNV, Productive Use of Thermal Energy in Agro-processing | No open licence stated | **cite** | Confirm with SNV before republishing their figures verbatim in a product. |
| `UNDP-CleanerPalmOil` | UNDP Ghana, cleaner palm oil production | UN, journalistic article | **cite** | Diesel-cost figures attributed. Not a technical spec. |
| `IFC-EHS-FoodBeverage` | IFC EHS Guidelines, Food & Beverage Processing | Reuse terms unconfirmed | **unconfirmed** | Used as generic engine/refrigeration/waste guidance. Industrial-scale - flagged as low-confidence for smallholder context. |
| `UNIDO-RECP` | UNIDO Resource-Efficient & Cleaner Production | Reuse terms unconfirmed | **unconfirmed** | Solar-drying guidance is generic; verify. |
| `COCOBOD-CSCocoa` | COCOBOD, Climate-Smart Cocoa / Cocoa Rehabilitation Programme (OCR'd) | Ghana govt agency | **cite** | Backs the cocoa rehabilitation + hybrid replanting measure. Gathered file was scanned; OCR'd 2026-07. |
| `CS-Cocoa-ForestLandscapes` | Climate-smart cocoa in forest landscapes (institutional lessons) | Journal | **cite** | Backs the cocoa disease-management measure (CSSVD). |
| `Cocoa-CSA-DecisionMaking` | Cocoa sector climate-smart awareness and decision-making | Report | **cite** | Backs the zone-specific shade-management measure. |
| `Ghana-CleanCooking-CAP` | Ghana National Clean Cooking Action Plan | Ghana govt | **cite** | Corroborates cookstove cost/payback; qualitative strategy doc, no new effect sizes. |
| `FAO-EXACT-v9.4.2-IPCC-Table5.5` | FAO EX-ACT v9.4.2 (embeds IPCC 2019 Table 5.5) | FAO free/unrestricted | **clean** | Tropical stock-change factors ([`reference/ipcc_stock_change_factors_gh.json`](../../engine/recommend/reference/ipcc_stock_change_factors_gh.json)); firms the conservation-tillage measure. |
| `PURC-2026-nonresidential` | PURC non-residential tariff (research) | Ghana govt | **cite** | Screening electricity price; see the price-feeds table. |
| `internal-data-quality` | Green Means Go data-quality policy | Internal | **clean** | Own content. |

## Price / feasibility feeds (Phase 2)

| Feed | Source | Licence | `use` | Notes |
|---|---|---|---|---|
| `price.ghs.*` commodities | MoFA SRID commodity prices (`data/recommendations/Tier1/Commodity prices _04.11.25.csv`) | Ghana govt open data | **cite** | Biweekly; 10,780 rows, 75 commodities, 14 regions, Jul–Oct 2025. Revenue side only - no fertiliser/fuel input prices. |
| `price.ghs.electricity.gh` | PURC non-residential tariff (research) + ECG tariff proposal (gathered) | Ghana govt | **cite** | Screening electricity price GHS 2.16/kWh for processor opex ([`reference/ghana_electricity_tariff.json`](../../engine/recommend/reference/ghana_electricity_tariff.json)). ⚠️ The gathered ECG file is a **proposal** whose end-user rate tables did not extract; the billed rate is PURC's. Acquire the gazetted PURC decision to make this primary-sourced. |
| `ef.grid.gh` | ✅ **RESOLVED** | Ghana govt publication | **cite** | **Gap closed.** Official Ghana grid EF extracted from `2025 Energy Statistics.pdf` (Energy Commission), Table 6.3: **0.35 kgCO2e/kWh** (2024, all-other-projects), 0.32 for displacement projects. Recorded with provenance in [`engine/recommend/reference/ghana_grid_ef.json`](../../engine/recommend/reference/ghana_grid_ef.json). Supersedes the stale IEA-2011/Climatiq 0.2629. Caveat: column alignment inferred from a flattened extraction; verify the 2024 cell visually before publishing figures. Now wired into the engine via `engine/grid_calibration.py` (climate-only, inventory-level, toggle `USE_OFFICIAL_GRID_EF`). |
| `activity.defaults.farm.gh` | Screening activity defaults (diesel L/ha, grid kWh/ha, yield guides) | Synthesis citing IPCC 2019 method, Ghana CSAIP/MoFA context, FAO/MoFA yield guides, WA mechanization/SSI literature | **cite** | Static table [`ghana_farm_activity_defaults.json`](../../engine/recommend/reference/ghana_farm_activity_defaults.json); applied by `engine/activity_defaults.py`. Wide uncertainty (×2); pedigree estimated. Replaces the retired Rust flat 80 L + 200 kWh/ha fallback for rainfed/manual. |

## FAO EX-ACT (methodological spine)

| File | Licence | `use` | Notes |
|---|---|---|---|
| `EX-ACT_V9.4.2.xlsb`, `EX-ACT VC_v3.5.xlsx`, `B-INTACT_v.1.9.xlsx` | FAO, free/unrestricted | **clean** | The clean anchor. Modelled effect sizes derived here carry `basis: modelled`. |

## Product status: FREE / NON-COMMERCIAL (decided 2026-07-17)

Green Means Go is a free tool. That resolves the licensing question in the library's favour:

- **CC BY-NC sources (CCAFS)** permit non-commercial use with attribution: cleanly in scope.
- **IPCC and other IGO/government sources** allow non-commercial reproduction with attribution; their "written permission" language targets commercial/redistribution use, which does not apply here. Low risk for a free tool, attribution being the obligation.
- **The one hard requirement is attribution.** The UI already shows `Source: ...` on every measure, so this is met. Keep it that way.
- `RECOMMENDATIONS_COMMERCIAL` stays **off** (its default). The gate remains available: if the product ever charges, flip it on and pursue IPCC written permission + the World Bank CC-BY-3.0-IGO confirmation to rebuild the full library for commercial use.

## Standing rules

1. **No measure ships with `provenance.reviewed_by == null`** in production, regardless of licence - that gate is separate (agronomic sign-off, not legal).
2. As a free tool, `nc` and `permission` sources are used under non-commercial terms with attribution (see above). The commercial gate (`RECOMMENDATIONS_COMMERCIAL=1`) is the switch to enforce exclusion **only if** the product becomes commercial.
3. When a new source is added, add its row here **before** the measure that cites it loads.
