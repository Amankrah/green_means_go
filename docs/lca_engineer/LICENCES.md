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
| `internal-data-quality` | Green Means Go data-quality policy | Internal | **clean** | Own content. |

## Price / feasibility feeds (Phase 2)

| Feed | Source | Licence | `use` | Notes |
|---|---|---|---|---|
| `price.ghs.*` commodities | MoFA SRID commodity prices (`data/recommendations/Tier1/Commodity prices _04.11.25.csv`) | Ghana govt open data | **cite** | Biweekly; 10,780 rows, 75 commodities, 14 regions, Jul–Oct 2025. Revenue side only - no fertiliser/fuel input prices. |
| `ef.grid.gh` | ✅ **RESOLVED** | Ghana govt publication | **cite** | **Gap closed.** Official Ghana grid EF extracted from `2025 Energy Statistics.pdf` (Energy Commission), Table 6.3: **0.35 kgCO2e/kWh** (2024, all-other-projects), 0.32 for displacement projects. Recorded with provenance in [`engine/recommend/reference/ghana_grid_ef.json`](../../engine/recommend/reference/ghana_grid_ef.json). Supersedes the stale IEA-2011/Climatiq 0.2629. Caveat: column alignment inferred from a flattened extraction; verify the 2024 cell visually before publishing figures. Still to do: wire it into the LCA engine's electricity characterization (engine task, not recommendation layer). |

## FAO EX-ACT (methodological spine)

| File | Licence | `use` | Notes |
|---|---|---|---|
| `EX-ACT_V9.4.2.xlsb`, `EX-ACT VC_v3.5.xlsx`, `B-INTACT_v.1.9.xlsx` | FAO, free/unrestricted | **clean** | The clean anchor. Modelled effect sizes derived here carry `basis: modelled`. |

## Standing rules

1. **No measure ships with `provenance.reviewed_by == null`** in production, regardless of licence - that gate is separate (agronomic sign-off, not legal).
2. A measure whose `use` is `nc` or `permission` **must be excluded from a commercial build** until resolved. The decision hinges on an open product question: *is Green Means Go commercial?* (RECOMMENDATION_ENGINE_PLAN.md §10).
3. When a new source is added, add its row here **before** the measure that cites it loads.
