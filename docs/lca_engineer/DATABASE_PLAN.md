# LCA Engineer — Database Plan

> **Purpose.** Define every database the LCA Engineer needs, *why* we need it, *how* we ingest/normalise it, and *what tier* of the roadmap it belongs to. This is the data foundation that turns the current hand-coded factor tables (in `african_lca_backend/src/production/lca.rs` and `lci.rs`) into a real, auditable, ISO-14040/44-compliant inventory-and-impact engine.
>
> **Author role:** LCA Engineer • **Scope:** Ghana & Nigeria agri-food first, West/East Africa next • **Status:** Planning

---

## 1. Where we are today (baseline)

The existing Rust engine **hardcodes** emission factors and characterization factors as Rust `match` statements:

- LCI emission factors (`lci.rs::EmissionFactorsDatabase`) cite IPCC 2019, GREET 2021, ecoinvent 3.8 — but the values are *typed in by hand*, not loaded from the source databases.
- LCIA factors (`lca.rs::get_default_impact_factor`) are category-level global averages (Poore & Nemecek 2018) per food category, with African climate/seasonal multipliers.
- There is **no background database** (no electricity mix, fertiliser production, transport, packaging chains) — upstream burdens are approximated by single per-kg numbers.

**Consequence / the gap we must close:** we cannot trace a result to a dataset, we cannot regionalise systematically, we cannot do a real supply-chain (cradle-to-gate) inventory, and we cannot reproduce or defend a number to a reviewer. Every database below exists to remove one of those limitations.

---

## 2. Database catalogue (the list)

Databases are grouped into five functional roles. Each entry states **why**, **license/access**, **format**, and **roadmap tier**.

### A. Background Life-Cycle Inventory (LCI) databases — *the supply chain*

These provide the cradle-to-gate burdens of every input the user reports (fertiliser, diesel, electricity, pesticides, packaging, transport).

| # | Database | Why we need it | License / Access | Native format | Tier |
|---|----------|----------------|------------------|---------------|------|
| A1 | **ecoinvent v3.11 / v3.12** (Cutoff, APOS, Consequential system models) | The de-facto global LCI backbone — 20k+ unit processes for energy, chemicals, materials, transport. Lets us model real upstream chains instead of single proxy factors. | Commercial subscription **or perpetual**; **free academic licenses for universities in low/low-middle-income countries** (covers Ghana/Nigeria partners). Requires per-seat agreement. | EcoSpold2 (XML), also distributed as openLCA JSON-LD and Brightway packages | T2 |
| A2 | **AGRIBALYSE 3.2** (ADEME/INRAE) | 2,517 agri-food product LCIs built to ISO/LEAP/PEF; our closest methodological template for food. Free. Excellent for crops/processed foods and as a *structure* reference even where geography differs. | **Free** under ETALAB open license; *imported-product datasets depend on ecoinvent + WFLDB*, so full use needs an ecoinvent license. The Agribalyse-only foreground is open. | openLCA JSON-LD, SimaPro CSV, Brightway | **T1** |
| A3 | **World Food LCA Database (WFLDB)** | Agri-food-specific background (feed, fertiliser blends, crop production) consistent with Agribalyse; fills food chains ecoinvent generalises. | Commercial (Quantis/ecoinvent-linked). | EcoSpold2 / openLCA | T3 |
| A4 | **US LCI / Federal LCA Commons** | Free, openly-licensed cross-check and source of elementary-flow nomenclature; good for interoperability testing. | **Public domain / free** | openLCA JSON-LD, ILCD | T2 |
| A5 | **EXIOBASE 3** (environmentally-extended multi-regional input–output) | Enables **hybrid LCA** and fills "data gaps" for sectors/countries with no process data — critical for African economies where process LCI is sparse. Per-country, per-sector. | **Free** (research license) | MRIO matrices (CSV/HDF5) | T3 |
| A6 | **FAO GLEAM** (Global Livestock Environmental Assessment Model) + **GLEAM-i** | Spatial tier-2 livestock LCA (GHG, N, water, soil C, biodiversity) with **Africa coverage** — directly relevant to Ghana/Nigeria livestock & dairy where ecoinvent is weak. | **Free** (FAO) | Model + datasets (FAO portal) | T2 |

### B. Life-Cycle Impact Assessment (LCIA) methods — *burden → impact*

These convert elementary flows (kg CO₂, kg N, m³ water…) into midpoint and endpoint impacts via characterization factors (CFs).

| # | Method | Why we need it | License / Access | Tier |
|---|--------|----------------|------------------|------|
| B1 | **ReCiPe 2016 v1.1** (midpoint + endpoint, H/I/E perspectives) | Our current methodology *mimics* ReCiPe — we must replace approximations with the **real CF tables** (17 midpoint categories, 3 endpoints, global + some country/continental CFs). | **Free** (RIVM report 2016-0104 + spreadsheets) | **T1** |
| B2 | **Environmental Footprint (EF) 3.1** (EC/JRC) | The EU regulatory standard (PEF). Needed for export-facing/eco-labelling credibility; AR6-aligned climate CFs, updated tox/acidification. | **Free** (JRC/EPLCA) | T2 |
| B3 | **IPCC GWP (AR6, 2021)** — GWP100/GWP20, GWP* for methane | Authoritative climate CFs; align our CO₂-eq with AR6 (current code mixes references). | **Free** (IPCC) | **T1** |
| B4 | **AWARE 1.2** (Available WAter REmaining) | Water scarcity CFs by watershed/country/month — our code hardcodes Ghana=20, Nigeria N=30/S=15; replace with the **real AWARE country/monthly factors**. | **Free** (WULCA) | **T1** |
| B5 | **USEtox 2.x** | Scientifically-recommended human + eco **toxicity** CFs (our weakest category per `data_sources.md`). | **Free** | T3 |
| B6 | **LANCA / land-use & soil-quality CFs** | Soil degradation, erosion, biodiversity-from-land-use — central to agri-food and currently approximated. | **Free** (JRC) | T2 |

### C. Reference / nomenclature & interoperability — *the glue*

Without a shared flow list, A-databases and B-methods cannot be linked. This is the single biggest source of "silent" matching errors.

| # | Resource | Why we need it | Access | Tier |
|---|----------|----------------|--------|------|
| C1 | **EF / ILCD elementary flow list** | Canonical names + UUIDs for elementary flows; the target nomenclature we normalise everything to. | Free (EPLCA) | **T1** |
| C2 | **Federal LCA Commons Elementary Flow List (FEDEFL)** | Mature, openly-licensed flow list + mapping files; proven interoperability backbone. | Free | T2 |
| C3 | **GLAD (Global LCA Data Access) mappings / GLAD Mapper** | Pre-built flow mappings (85–98% coverage between major flow lists) — bootstrap our cross-database matching instead of building it from zero. | Free (UNEP) | T2 |
| C4 | **ILCD / ISO 14048 data documentation format** | The metadata schema (provenance, review, validity) we store per dataset so results are auditable. | Free (standard) | **T1** |

### D. Foreground / activity & food-reference data — *the user's world*

These translate what a farmer/company *reports* into modelable activities and link to nutrition/labelling.

| # | Resource | Why we need it | Access | Tier |
|---|----------|----------------|--------|------|
| D1 | **FAOSTAT** (production, yields, fertiliser use, land, livestock by country) | Country-level activity & yield data to build Ghana/Nigeria foreground + regional defaults; fills the "smallholder under-representation" gap. | **Free** | **T1** |
| D2 | **IPCC EFDB (Emission Factor Database)** | Tier-1/2 EFs for N₂O, CH₄ (enteric, rice, manure), liming, urea — the agricultural-emissions core. | **Free** | **T1** |
| D3 | **FoodEx2 (EFSA) + Open Food Facts** | Standardised food classification & barcode→product mapping for the matching subsystem (user free-text → canonical food). | **Free** | T2 |
| D4 | **National sources** (Ghana EPA, MOFA, CSIR; Nigeria FME, IITA, NASS) per `data_sources.md` | Primary regionalisation: grid emission factors, irrigation, crop practices. | **Free / partnership** | T2 |

### E. AI-subsystem support data — *for the ML layer*

| # | Resource | Why we need it | Access | Tier |
|---|----------|----------------|--------|------|
| E1 | **Vector store of process/flow embeddings** (built from A1–A4 names + descriptions) | Powers semantic matching of user inputs → datasets (see Developer Guide §AI). | Built in-house | T2 |
| E2 | **Curated matching gold-set** (verified user-term → dataset links) | Train/evaluate the matching subsystem; measure top-1/top-5 accuracy. | Built in-house | T2 |
| E3 | **Provenance/citation corpus** (the literature in `LITERATURE_WISHLIST.md`) | RAG knowledge base so the AI can cite methods/factors instead of hallucinating. | Built in-house | T1 |

---

## 3. How we ingest & normalise (architecture)

**Principle: one canonical internal schema, many importers.** Never let a database's native quirks leak into the engine.

```
 ┌────────────┐   importers    ┌──────────────────────┐   normalise   ┌─────────────────┐
 │ ecoinvent  │ ──EcoSpold2──▶ │                      │ ──flow map──▶ │ Canonical LCI   │
 │ Agribalyse │ ──JSON-LD───▶ │  Staging (raw, by    │   (→ C1/C2)   │ store (Postgres │
 │ ReCiPe/EF  │ ──CSV/XML──▶  │  source + version)   │               │ + Parquet +     │
 │ FAOSTAT…   │ ──API/CSV──▶  │                      │               │ vector index)   │
 └────────────┘                └──────────────────────┘               └─────────────────┘
```

1. **Acquire** under correct license (track license per dataset — see §5).
2. **Stage raw** with full provenance (source, version, download date, hash). Never mutate raw.
3. **Parse** with format-specific importers. Reuse the ecosystem rather than writing parsers from scratch:
   - **Brightway2 / `bw2io`** (Python) — reads EcoSpold2 + ecoinvent, exposes matrices.
   - **`olca-schema` / openLCA IPC** — for JSON-LD datasets (Agribalyse, US LCI).
   - Custom CSV/XLSX readers for ReCiPe/EF/AWARE CF spreadsheets.
4. **Normalise flows to C1 (EF/ILCD list)** using C2/C3 mappings; log every unmapped flow as a data-quality event (feeds anomaly detection).
5. **Persist** to the canonical store:
   - **PostgreSQL** for structured datasets, flows, CFs, provenance, pedigree.
   - **Parquet/Arrow** for the technosphere/biosphere matrices (fast linear-algebra in Rust).
   - **Vector DB** (FAISS/Qdrant) for E1 embeddings.
6. **Version everything** (database version + import run id) so any result is reproducible and re-runnable when a source updates (ecoinvent ~yearly, Agribalyse, EF).
7. **Expose to the Rust core** as read-only matrices + CF tables; the Rust engine solves the inventory (`A·s = f`, `g = B·s`) and applies CFs — replacing the hand-coded `match` tables.

---

## 4. Roadmap tiers (sequencing)

- **Tier 0 — now:** hardcoded factors (keep as fallback + sanity check).
- **Tier 1 — foundation (free, no ecoinvent license needed):**
  AGRIBALYSE 3.2 foreground (A2) · ReCiPe 2016 (B1) · IPCC AR6 (B3) · AWARE (B4) · EF/ILCD flow list (C1) · ISO 14048 schema (C4) · FAOSTAT (D1) · IPCC EFDB (D2) · RAG corpus (E3).
  → *Outcome: real CF tables + real agricultural EFs + auditable provenance, with zero licensing cost.*
- **Tier 2 — supply chain & regionalisation:**
  ecoinvent (A1, via free LMIC academic license) · US LCI (A4) · GLEAM (A6) · EF 3.1 (B2) · LANCA (B6) · flow mapping (C2/C3) · FoodEx2/OFF (D3) · national data (D4) · matching vector store + gold-set (E1/E2).
- **Tier 3 — advanced coverage:**
  WFLDB (A3) · EXIOBASE hybrid (A5) · USEtox (B5).

---

## 5. Licensing & compliance guardrails (must-read before ingesting)

- **ecoinvent is not redistributable.** We store it for *internal computation only*; never expose raw datasets via API or reports. Pursue the **free academic license for low/low-middle-income-country institutions** through a Ghana/Nigeria university partner.
- **Agribalyse (ETALAB) is open**, but its imported-product datasets embed ecoinvent — the ecoinvent-derived parts inherit ecoinvent's terms. Keep the open foreground separable from licensed background.
- **ReCiPe, EF, AWARE, USEtox, IPCC, FAOSTAT** are free to use; still record citation + version in provenance.
- Maintain a **`LICENSES.md` / license field per dataset** in the canonical store; the AI subsystems must check this flag before quoting raw data in outputs.
- Results derived from licensed background data can be published (aggregated impacts), but **underlying unit-process data cannot** — design the report layer accordingly.

---

## 6. What each database unlocks (traceability to project goals)

| Project gap (from `data_sources.md` / research) | Database(s) that closes it |
|---|---|
| No real supply-chain inventory | ecoinvent (A1), WFLDB (A3), EXIOBASE (A5) |
| Approximated, non-auditable CFs | ReCiPe (B1), EF (B2), AWARE (B4), USEtox (B5) |
| Weak toxicity/biodiversity categories | USEtox (B5), LANCA (B6) |
| Hardcoded water-scarcity factors | AWARE (B4) |
| Smallholder / African under-representation | FAOSTAT (D1), GLEAM (A6), IPCC EFDB (D2), national data (D4), EXIOBASE (A5) |
| Silent matching/nomenclature errors | EF/ILCD flow list (C1), FEDEFL (C2), GLAD (C3) |
| Non-reproducible results | ISO 14048 provenance (C4) + versioned canonical store |
| AI hallucination in matching/reports | embedding store (E1), gold-set (E2), RAG corpus (E3) |

---

## 7. Open decisions (need product/eng sign-off)

1. **Primary LCIA method**: lead with **ReCiPe 2016** (matches current design + global scope) and add **EF 3.1** for EU-export users — confirm.
2. **ecoinvent procurement path**: academic LMIC license via partner vs. commercial — depends on whether output is commercial.
3. **Canonical store engine**: PostgreSQL + Parquet (recommended) vs. full Brightway-as-store. Brightway is faster to bootstrap; Postgres is better for the API/AI stack we already run.
4. **Where matrices are solved**: keep heavy linear algebra in Rust (perf) and use Python (Brightway) only as importer/validator — confirm the boundary.

---

### Sources
- [ecoinvent v3.11 / v3.12 release & system models](https://ecoinvent.org/blog/version-3-11-is-now-available/) · [Licenses & LMIC free access](https://ecoinvent.org/licenses/) · [openLCA ecoinvent 3.11](https://www.openlca.org/ecoinvent-3-11-available-for-openlca/)
- [AGRIBALYSE 3.2 data access (ETALAB, ecoinvent dependency)](https://doc.agribalyse.fr/documentation-en/agribalyse-data/data-access) · [openLCA Agribalyse 3.2](https://www.openlca.org/agribalyse-3-2-now-available-for-openlca/)
- [ReCiPe 2016 RIVM report 2016-0104](https://www.rivm.nl/bibliotheek/rapporten/2016-0104.pdf)
- [EF 3.1 method — EC/JRC EPLCA](https://eplca.jrc.ec.europa.eu/EnvironmentalFootprint.html) · [Updated EF 3.1 CFs (JRC130796)](https://publications.jrc.ec.europa.eu/repository/bitstream/JRC130796/JRC130796_01.pdf)
- [FAO LEAP / GLEAM](https://www.fao.org/gleam/en) · [LEAP partnership](https://www.fao.org/partnerships/leap/en)
- [Federal LCA Commons elementary flows interoperability](https://pmc.ncbi.nlm.nih.gov/articles/PMC9628124/) · [GLAD flow mapping](https://www.researchgate.net/figure/Share-of-elementary-flows-in-the-mapped-methods-to-ecoinvent-LCI-nomenclature-by-mapping_fig3_360717536)
- [Addressing critical challenges towards a robust data system for LCA (Nature Reviews Clean Technology, 2025)](https://www.nature.com/articles/s44359-025-00107-4)
- [LCA research and application in Nigeria (Int J LCA, 2024)](https://link.springer.com/article/10.1007/s11367-024-02423-6)
