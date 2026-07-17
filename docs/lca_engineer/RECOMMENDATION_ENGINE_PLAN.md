# Recommendation Engine - Plan

> **Purpose.** Turn the engine's hotspot attribution into **practical, costed, sequenced actions** a Ghanaian farmer or processor can actually take - surfaced in the results chat and on the dashboard. The ISO report answers *"what is my footprint and is it defensible?"*. This answers *"what do I do on Monday, what does it cost, and when does it pay back?"*
>
> **Status:** Planning · **Scope:** Ghana first (GH region), farm + processing · **Depends on:** [`DATABASE_PLAN.md`](./DATABASE_PLAN.md) (E3 corpus), [`LITERATURE_EXTRACTION.md`](./LITERATURE_EXTRACTION.md) (record schema)

---

## 1. The central architectural claim

**Do not build RAG over PDFs and let the model report numbers from retrieved prose.**

A recommendation like *"split your urea application - cuts field N₂O ~25%, costs ₵X, pays back in 14 months"* is **entirely numbers**. Vector similarity retrieves passages that *look* relevant; it cannot tell a 2019 fertiliser price from a 2026 one (embeddings do not encode recency), it cannot tell a UK measure from a Ghanaian one, and it silently flattens the table structure that made the number meaningful.

This is not a hypothetical. The evidence:

- **LCA-specific:** an expert-grounded benchmark of general-purpose LLMs on LCA tasks (arXiv:2510.19886 - 17 expert practitioners, 168 reviews) found experts judged **37% of responses inaccurate or misleading, with citation hallucination up to 40%**.
- **Aggregation:** GlobalQA (arXiv:2510.26205) shows RAG fails badly on counting / top-k / sorting / extremum queries - which is *precisely* our core query shape ("which three measures are cheapest?"). Chunk retrieval structurally cannot answer this. SQL can.
- **Tables:** flattening tables into prose chunks destroys the structure that makes numbers trustworthy (arXiv:2504.01346, 2506.10380).
- **Domain precedent:** Amazon's **Parakeet** (emission-factor recommendation for LCA) does exactly what we should - retrieve top-k from a *curated structured repository*, have the LLM rank and explain, and **never invent a factor**.

This also happens to be the pattern **this repo already established**. [`LITERATURE_EXTRACTION.md`](./LITERATURE_EXTRACTION.md) defines four typed JSONL record types with mandatory provenance - not free-text chunks. The recommendation layer should be **a fifth record type**, not a departure.

### The resulting shape

```
 assessment ──▶ Rust/engine attribution ──▶ [contribution_by_source: which input drives which impact]
                                                        │
                                                        ▼
                          ┌──────────── deterministic measure matcher (SQL) ────────────┐
                          │  hard filters FIRST: region · crop · system · scale         │
                          │  then: does this measure target a source in MY top hotspots?│
                          └────────────────────────────┬───────────────────────────────┘
                                                        ▼
                              Measure library (typed records, provenance non-null)
                                                        │
                                                        ▼
                          ┌──────── economic + feasibility screen (plain code) ─────────┐
                          │  capex vs revenue · payback · finance access · prerequisites│
                          └────────────────────────────┬───────────────────────────────┘
                                                        ▼
                                      ranked, sequenced candidate actions
                                                        │
                                                        ▼
      Claude ── explains, personalises, answers follow-ups. Numbers arrive ALREADY CORRECT.
               RAG (prose only) supplies the "why does this work" narrative + citations.
```

**Division of labour - the load-bearing rule:**

| Layer | Owns | Never does |
|---|---|---|
| Rust / engine | All arithmetic, including summing effects across a bundle | - |
| Measure library (SQL) | Effect sizes, costs, applicability, provenance, freshness | Free text as a number source |
| Screen (plain Python) | Ranking, affordability, sequencing | - |
| RAG | *Prose only* - "why does reduced tillage lower N₂O" | Touch a number |
| Claude | Choosing which query to run, composing, explaining, chatting | Arithmetic. Stating an unretrieved number. |

Under this design the model is **structurally incapable** of drifting a number, because no number passes through free generation.

---

## 2. Where we actually stand

### 2.1 What already exists (better than expected)

| Asset | Location | Note |
|---|---|---|
| **Per-input attribution across every impact category** | `engine/orchestrator.py:158-159`, `179` | `contribution_by_source` keys on the **declared input name** - can say "Urea 46-0-0 = 45% of climate impact" |
| Climate hotspot ranking with shares | `engine/iso_report.py:206-215` | `by_source: [{source, per_kg, share}]`, sorted desc |
| Input `kind` taxonomy | `engine/orchestrator.py:170` | `fertiliser`/`fuel`/`electricity`/`pesticide`/`compost`/`packaging`/`waste`/… |
| **RAG seam - already stubbed and wired** | `app/chat/routes.py:82-89`, `112-114` | `retrieve_context(query) -> List[str]`; snippets flow into the cached system block. **No chat plumbing needed.** |
| **Working vector-search stack** | `ingestion/matching.py:63-93`, `170-234` | Offline numpy embedder + npz cache + cosine top-k. **Zero new deps** - no vector DB needed at this corpus size |
| Strict grounding discipline | `app/services/report_grounding.py:13-17` | *"You are an interpreter, not an LCA author."* Already the right instinct |
| Practice detail | `app/production/models.py:78-147` | Rates, applications, IPM flag, equipment age, conservation practices |
| Persistence + migrations | `app/models.py:120-147`, Alembic | `payload_json` holds the full result; SQLite→Postgres-portable |

### 2.2 What does not exist (the honest list)

| Gap | Evidence | Severity |
|---|---|---|
| **No economic data on the farm side** | Exhaustive grep of both request models: 5 financial fields, **only `economic_value` ever read** (for co-product allocation, `engine/process_adapter.py:65`). The three farm `cost` fields are captured and consumed by nothing. No revenue, crop price, capital, or labour. | **Blocker** for "economic sense" |
| **No location below region** | 3 regions total (`GH`/`NG`/`CA`, `engine/regions.py:34-54`). No district, no GPS. `Farm.location` is unstructured free text, never fed to the engine. | **Blocker** for "location sense" |
| **No farmer-guide corpus** | `docs/` is engineering docs; `data/` is LCIA method factors. Nothing agronomic. | **Critical path** |
| **N content never parsed** | `npc_ratio` is a **free-text display string** used only to build a name (`engine/inputs.py:53`). Never converted to kg N. | Blocks any N recommendation |
| No measure/abatement corpus in the wishlist | [`LITERATURE_WISHLIST.md`](./LITERATURE_WISHLIST.md) is LCA-method literature only | New corpus needed |
| Recommendations are hardcoded keyword rules | `engine/iso_report.py:536-556` → flat `List[str]` | Replace |
| `Recommendation` model never instantiated on live path | `app/production/models.py:251-258`; populated only under `USE_LEGACY_RUST_LCIA=1` | Wire up |
| Frontend discards `results.recommendations` | `results/page.tsx:352-362` renders a hardcoded `BAND_MAP` instead | Fix |
| `management_analysis` / `benchmarking` are empty shells | `TODO` in `african_lca_backend/src/production/lca.rs:150-151` | Deferred |
| Bands compare to a **static ecoinvent basket**, not peers | `engine/single_score_bands.json` (20 products) | Don't claim peer benchmarking |
| No livestock/herd/feed/manure modelling | No animal-count field anywhere | Scope limit - crops only |
| `anthropic==0.42.0` (Dec-2024 SDK); no tool use anywhere | `requirements.txt:2` | Blocks structured output |
| No rate limiting on `/chat/stream` | grep: no `slowapi`/`limiter` | Cost exposure |
| `/inventory/match` + `/reindex` unauthenticated **and billable** | `app/inventory/routes.py:148, 154` | **Security - fix now** |

### 2.3 The market gap (this is the opportunity)

No existing tool combines **(a)** farm-level data entry, **(b)** automated cost-effectiveness ranking, and **(c)** tropical smallholder coverage. The four archetypes all miss:

| Archetype | Example | Why it doesn't do this |
|---|---|---|
| Footprint-only | Farm Carbon Toolkit | No recommender at all |
| Manual what-if | Cool Farm Tool, CarbonCloud | User duplicates the assessment and changes one input by hand. Not a ranked list |
| Human consultant | Agrecalc | Recommendations come from a paid adviser audit |
| Policy-level MACC | GAINS, UK CCC/ADAS | Unit = country, not farm |

**That gap is global, not just African.** Meanwhile the one methodological spine built *for* developing-country AFOLU - **FAO EX-ACT** - is free, fully documented, covers agroforestry/perennials/irrigated rice, publishes explicit guidance on *building MACCs from its outputs*, and is what Ghana's own CSAIP used to compute its 7.31 MtCO₂ figure. It is an Excel tool for analysts with no farmer UX. **That is the thing to stand on and put a farmer front-end onto.**

---

## 3. The measure library - record type 5

Append to [`LITERATURE_EXTRACTION.md`](./LITERATURE_EXTRACTION.md) §0 as a fifth canonical record. Every field below exists to defeat a specific, documented failure mode.

```jsonc
// (5) ABATEMENT MEASURE - hotspot → action
{
  "type": "abatement_measure",
  "id": "meas.n.split_application.ghana",
  "title": "Split the urea dose across the season",
  "targets": {
    "driver_kind": "fertiliser",              // joins to input_matches.kind
    "driver_match": ["urea", "npk", "ammonium"], // substring match vs contribution_by_source keys
    "impact_category": "Climate change"
  },

  // --- APPLICABILITY: hard SQL filters, evaluated BEFORE any similarity ranking.
  // Multi-Meta-RAG (arXiv:2406.13213): metadata folded into embedded text gets
  // diluted; explicit filtering lifted MRR@5 ~0.12 -> ~0.68. Structural elimination,
  // not probabilistic. This is what stops a UK measure reaching a Ghanaian farm.
  "applicability": {
    "regions": ["GH"],
    "climate_zones": ["wet tropical"],
    "crops": ["maize", "rice"],
    "systems": ["conventional", "intensive"],
    "scale_ha": {"min": 0.5, "max": 50},
    "prerequisites": ["uses_fertilizers == true"]
  },

  // --- EFFECT: never a bare number. Unit is a typed enum; conversion happens in Rust.
  "effect": {
    "value": -0.25, "unit": "fraction_of_driver_impact",
    "uncertainty_range": {"low": -0.40, "high": -0.10, "ci": 0.95},
    "yield_effect": {"value": 0.0, "unit": "fraction", "note": "no significant yield loss"},
    "basis": "measured"                        // measured | modelled | expert_judgement
  },

  // --- ECONOMICS: currency + as_of are mandatory. A cost without a date is a lie.
  "economics": {
    "capex": {"value": 0, "currency": "GHS"},
    "opex_delta": {"value": -120, "currency": "GHS", "per": "ha/season"},
    "labour_delta_days_ha": 0.5,
    "as_of": "2026-07-01",
    "price_refs": ["price.ghs.urea.mofa_srid"]  // dereferenced live, never inlined
  },

  // --- SEQUENCING: answers "over months or years?"
  "horizon": {
    "band": "quick_win",                       // quick_win (<3mo) | medium (3-12mo) | strategic (1-3yr)
    "time_to_first_effect_months": 3,
    "requires_finance": false,
    "reversible": true
  },

  // --- PROVENANCE: NON-NULL. Evidence-gated extraction (arXiv:2601.14267) - the
  // extractor must point at an exact source span, or the field is null, NOT guessed.
  "provenance": {
    "source": "IPCC-2019", "vol": 4, "chapter": 11, "table": "11.1",
    "span": "exact quoted sentence or cell",
    "publication_date": "2019-05-12",
    "licence": "see LICENCES.md",
    "extraction_confidence": 0.9,
    "reviewed_by": null                        // human sign-off before a measure goes live
  },

  // --- FRESHNESS: embeddings do NOT encode recency. Hard filter, not a ranking hint.
  "valid_from": "2026-07-01",
  "valid_until": "2027-07-01",
  "staleness_policy": "annual"                 // biweekly | quarterly | seasonal | annual | assessment_cycle
}
```

### Why each guard exists

| Guard | Defeats | Evidence |
|---|---|---|
| `applicability` as **SQL filter, pre-ranking** | A Scottish MACC measure surfacing for a Ghanaian smallholder | arXiv:2406.13213 |
| `unit` as typed enum; conversion in Rust | Silent wrong-unit propagation | arXiv:2603.03332, NUMCoT arXiv:2406.02864 |
| `provenance.span` non-null | Citation hallucination (up to **40%** in LCA tasks) | arXiv:2510.19886 |
| `valid_from` + `staleness_policy` | Serving a 2019 price as current | Temporal-RAG (arXiv:2510.13590) |
| `economics.as_of` + `price_refs` | Frozen prices in a 20%-inflation economy | - |
| `effect.uncertainty_range` | False precision (Drawdown's single global average) | - |
| `basis` field | Presenting a modelled figure as measured | - |

### Bundling is not additive - a named trap

**OECD (2015), "Cost-Effectiveness of GHG Mitigation Measures for Agriculture"** finds that **measure interactions reduce potential and worsen cost-efficiency when stacked**. If we recommend three N measures, their effects do **not** sum. Two rules:

1. Ship **one measure per hotspot** in v1. Do not bundle.
2. When bundling arrives, model interactions explicitly (`conflicts_with` / `diminishes` edges) - never `sum()`.

Read **Eory et al. (2018)**, *J. Cleaner Production* 182:705–716 (DOI 10.1016/j.jclepro.2018.01.252) **before** designing the ranking engine. Its central finding: farmers' non-adoption of apparently "cost-saving" measures reflects **risk aversion and transaction costs the MACC omits**. A naive ranked list will confidently recommend things farmers have rational reasons to refuse. Corroborated at farm level by the FarmDyn study - *"no two farm-level MACC curves are the same"*, which is empirical support for our per-farm premise.

---

## 4. The economic layer - the real blocker

The request *"suggestions should make economic, availability and feasibility sense based on revenue and location"* currently has **neither revenue nor location**. Three options, in preference order:

| Option | How | Cost | Honesty |
|---|---|---|---|
| **A. Ask** (recommended) | Add an optional economics block to the questionnaire: farmgate price or annual revenue, capital available, finance access, labour availability | ~1 questionnaire section + migration | Accurate, user-owned |
| **B. Derive** | `revenue ≈ Σ(quantity_kg × price)` using **MoFA SRID biweekly prices** / COCOBOD producer price | Price pipeline only - no UX change | Reasonable proxy; wrong for contract/export |
| **C. Band** | Ask one question: *"roughly, what does this farm earn a year?"* with 4 bands | One field | Crude but sufficient for affordability screening |

**Recommendation: B as the default, C as the one-question override, A for processors** (who already have `economic_value` and `employee_count`). This gets an affordability screen with minimal UX cost and degrades honestly.

**Do not skip the `cost` fields already captured.** `FertilizerApplication.cost`, `EnergyUsage.cost` (+`currency`), and `FuelUsage.cost` are collected today and read by nothing. Wiring those in is nearly free and gives real, farm-specific opex.

**Location:** `Region.currency` is stored and never used (`engine/regions.py:20-30`). GHS is already there. District-level resolution needs a new field - defer; region + `LocationType` (Urban/PeriUrban/Rural/Industrial, already captured for processors) is enough for v1 grid/market proximity heuristics.

---

## 5. Phasing

### Phase 0 - Foundations & fixes (days, not weeks)

Independent of any corpus work. Several are outright bugs.

1. **Security - do first.** Gate `/inventory/match` and `/inventory/reindex` behind `get_current_user` (`app/inventory/routes.py:148, 154`). `/reindex` triggers a full re-embed of ~46k processes; with `OPENAI_API_KEY` set that is an **unauthenticated, billable, repeatable** operation. Add rate limiting to `/chat/stream`.
2. **Rotate the keys in `app/.env`.** Correctly gitignored and never committed - but they are live secrets in the working tree and surfaced in plaintext during this investigation.
3. **Verify the prompt cache is real.** `cache_control` is set on the grounding block (`chat/routes.py:112-117`), but the minimum cacheable prefix on **Haiku 4.5 is 4096 tokens**. Below that it silently no-ops (`cache_creation_input_tokens: 0`). Measure with `count_tokens`; if the grounding is short, the marker is decorative.
4. **Bump `anthropic`.** 0.42.0 predates `output_config.format` / `messages.parse()` / tool use. Required for structured output.
5. **Fix `requirements.txt` encoding** - it is UTF-16, a `pip install -r` footgun. Add the undeclared `numpy`/`openai` deps.
6. **Render `results.recommendations`** when present, falling back to `BAND_MAP` (`results/page.tsx:497`). The type already exists.
7. **Parse `npk_ratio` into kg N.** Prerequisite for every fertiliser measure. Currently a display string (`engine/inputs.py:53`).
8. **Aggregate `contribution_by_source` by `kind`.** Re-join on `input_matches` so "synthetic N" exists as a class, not just per-product names.

### Phase 1 - Measure library v1 (the critical path) - ✅ DELIVERED

Built in `engine/recommend/`: [`schema.py`](../../engine/recommend/schema.py) (record type 5 + validating loader), [`measures.jsonl`](../../engine/recommend/measures.jsonl) (16 Ghana measures, all `reviewed_by: null`), [`matcher.py`](../../engine/recommend/matcher.py) (deterministic hotspot→measure funnel with hard filters + freshness + reviewed gate), [`test_recommend.py`](../../engine/recommend/test_recommend.py) (11 tests). Licences tracked in [`LICENCES.md`](./LICENCES.md). Verified against the live engine on `ghana_maize_cowpea_intercrop.json`.

**Scope hard: ~20–40 measures, Ghana only, hand-curated, provenance mandatory, human-reviewed.** Cover only the hotspots the engine actually surfaces:

| Farm | Processing |
|---|---|
| Field N₂O (rate/timing/split/type) | Fuelwood → efficient stove (gari, fish smoking) |
| Synthetic N → compost/legume | Grid electricity efficiency |
| Diesel / machinery efficiency | Solar drying |
| Rice paddy CH₄ (AWD) | Refrigerant leakage |
| Pesticide → IPM | Waste → byproduct utilisation |

Build order: OCR pipeline → extract → **human review** → load → matcher → screen. Ship *without* the LLM layer first: a deterministic ranked list is already better than today's five hardcoded strings, and it lets us validate the library before adding a generation layer on top.

### Phase 2 - Economic + feasibility screen - ✅ DELIVERED

Built: [`prices.py`](../../engine/recommend/prices.py) (`PriceBook` over the MoFA SRID CSV - 10,779 rows, wholesale-preferred medians, explicit GHS/kg unit assumption, hard staleness flag) and [`economics.py`](../../engine/recommend/economics.py) (revenue derivation, per-measure opex annualisation + payback + affordability tier, and `build_action_plan` sequencing into start-now / this-year / plan-ahead). Top-level `recommend()` runs the whole deterministic pipeline. [`test_economics.py`](../../engine/recommend/test_economics.py): 9 tests against the real CSV. Verified end-to-end: the Ghana maize+cowpea case yields ~38.5k GHS/yr revenue and a 7-measure phased plan with per-measure GHS savings/costs.

**Known limits (honest):** revenue uses wholesale as a farmgate proxy (overstates); prices are Oct-2025 (flagged stale, not refreshed); input-cost side (fertiliser/fuel prices) still comes from the questionnaire `cost` fields, not the CSV (which is output prices only); cocoa has no price (COCOBOD series, absent from the MoFA feed) and is reported as a gap, never guessed.

### Phase 3 - Surfacing layer (endpoints, chat RAG, results UI) - ✅ DELIVERED

Built:

- **Serializer** [`serialize.py`](../../engine/recommend/serialize.py) - one canonical JSON shape (revenue + phased plan + per-measure economics + **provenance + `reviewed` flag**), used by both the endpoint and the chat.
- **Service** [`app/recommendations/service.py`](../../app/recommendations/service.py) - pulls farm/facility context (size, production system, practice flags) out of the archived *request*, runs the deterministic pipeline, caches the price book. `RECOMMENDATIONS_REVIEWED_ONLY` env gates draft vs signed-off (default draft, badged).
- **Endpoints** `GET /assess/{id}/recommendations` + `GET /processing/assess/{id}/recommendations` - owner-scoped, run in a threadpool, fully deterministic (no LLM).
- **Chat RAG seam** - [`chat/routes.py`](../../app/chat/routes.py) `retrieve_context()` now returns grounded, cited measure guidance matched to the farm's hotspots (read from structured records - nothing to hallucinate). Guidance is assessment-driven so the cached grounding block stays byte-stable across turns, and it's labelled distinctly from the farm's measured results.
- **Results UI** - [`RecommendationsPanel.tsx`](../../african-lca-frontend/src/components/RecommendationsPanel.tsx) renders the phased plan with per-measure cost/saving/payback and a draft badge, mounted on the results page above the ISO report.

Tests: [`test_recommendations_api.py`](../../app/test_recommendations_api.py) (3, incl. owner-scoping + auth), plus `tsc`/lint/`next build` clean. The LLM still never produces a number - it explains the deterministic output.

**Not yet done (was in the original Phase 3 scope):** a dashboard "recommended actions" card (the results page is the surface today); persisting the recommendation blob (it's recomputed on GET - cheap, deterministic, so caching is deferred).

### Phase 3 (original planning notes) - LLM layer

1. Implement `retrieve_context()` over the **prose** corpus using the existing `matching.py` pattern (no new deps). Chat gets grounded narrative with **zero route changes**.
2. Add `POST /assess/{id}/recommendations` - non-streaming, structured output (tool-shaped schema), returning the **existing `Recommendation` model** so it unifies with the engine's field. **Persist it** (Alembic revision, or fold into `payload_json`); recommendations are stable per assessment and there is no rate limiting.
3. Dashboard card module - the overview page is a flat `space-y-8` stack; the slot between the StatCard grid (`dashboard/page.tsx:109`) and the Recent-assessments section is the natural home. Note the dashboard only holds `AssessmentSummary` rows (no `payload_json`), so it needs the new endpoint.
4. Extend the grounding prompt to **distinguish "this farm's measured data" from "general guidance"**, with provenance. The current `ADDITIONAL GUIDANCE:` framing (`chat/routes.py:114`) carries no citation.

**Model choice.** Chat is on Haiku 4.5 ($1/$5) - a reasonable fit for "explain these numbers plainly." The **recommendation** path reasons about feasibility trade-offs and should start on a stronger tier (`claude-opus-4-8`, $5/$25, or `claude-sonnet-5`, $3/$15 - intro $2/$10 through 2026-08-31). It runs **once per assessment and is cached**, so tier cost is near-irrelevant; the chat path is the volume driver. Haiku 4.5 does support structured outputs, so this is a quality call, not a capability one.

### Review gate + acquisition - ✅ DELIVERED

The go-live blockers, addressed:

- **Review gate.** An append-only sign-off ledger [`reviews.jsonl`](../../engine/recommend/reviews.jsonl) plus a loader overlay: an `approved` decision stamps `provenance.reviewed_by` and flips `is_reviewed`, so the measure passes the production `reviewed_only` gate. Last decision per measure wins (a re-review supersedes). [`review.py`](../../engine/recommend/review.py) prints a per-measure worksheet (every claim + the exact source span) and exposes `record_review()`. Still 0 approved: the library is draft until an agronomist fills the ledger.
- **Licence enforcement.** [`licences.py`](../../engine/recommend/licences.py) makes `LICENCES.md` an enforceable runtime gate. `match_measures(..., commercial=True)` (env `RECOMMENDATIONS_COMMERCIAL`) drops CC-BY-NC, IPCC-permission-pending, and unconfirmed sources. **Finding: in commercial mode a Ghana maize farm drops from 7 measures to 2** (only the cite-licensed inhibitor and the clean data-quality measure survive), so the "is Green Means Go commercial?" decision materially shrinks the library until licences are resolved.
- **Grid EF acquired.** Extracted the official Ghana grid emission factor from the Energy Commission's 2025 Energy Statistics (Table 6.3): **0.35 kgCO2e/kWh** (2024, all-other-projects), 0.32 for displacement projects. Recorded with provenance in [`reference/ghana_grid_ef.json`](../../engine/recommend/reference/ghana_grid_ef.json); supersedes the stale IEA-2011 0.2629. Electricity measures updated; the LCA engine's electricity characterization can now be wired to it (a separate engine task).

Tests: [`test_review.py`](../../engine/recommend/test_review.py) (8, covering the overlay + licence gate). Full engine suite 28/28.

### Phase 4 - Later

Peer benchmarking (fills the `BenchmarkingResults` shell honestly - needs a cohort), measure bundling with interaction modelling, adoption feedback ("did you do it? did it work?"), the passive SMS/satellite layer from the brief.

---

## 6. Acquisition list - what I need you to fetch

I verified every URL live. These are the ones I **could not** get, ranked. Items marked ⛔ are hard blockers.

### Tier 1 - unblocks everything

| # | What | Where | Why you, not me |
|---|---|---|---|
| 1 | **OCR/PDF pipeline** (pdftotext + OCR fallback + pdfplumber/camelot for tables) | build | **Every Ghana government PDF below returns HTTP 200 and fails text extraction** - they are scanned. This is a prerequisite, not a nice-to-have. PURC's PDFs are FlateDecode binaries that fail **silently** - test for that explicitly |
| 2 | **MoFA SRID price CSV** | https://srid.mofa.gov.gh/node/18 | The single best structured Ghana feed found - retail + wholesale for **commodities and inputs**, **biweekly** (`accrualPeriodicity: R/P2W`), CSV confirmed. Backbone of the whole economic layer. Pull it and inspect the schema |
| 3 | **FAO EX-ACT** + Technical Guidelines V4 + **the MACC-from-EX-ACT guidance** (openknowledge.fao.org bitstream `33830c17-609f-4f0f-a034-b471818ecb59`) + EX-ACT VC Guidelines (bitstream `7b7533d7-7264-48a5-ab4f-cb4a367af714`) | exact.apps.fao.org | **The methodological spine.** Free, unrestricted, developing-country-vetted, and what Ghana's own CSAIP used. Also confirm whether EX-ACT VC is being deprecated into the main app (2025) |
| 4 | **IPCC written permission** - start now | copyright@ipcc.ch | ⛔ **AR6 is NOT CC.** Product use needs written permission, **~4 week turnaround**. Needed if Fig 7.11 (cost-potential bins per measure) is wanted. Start this week or it gates Phase 1 |
| 5 | **Ghana CSAIP annex tables** | https://documents1.worldbank.org/curated/en/300161592374973849/txt/Climate-Smart-Agriculture-Investment-Plan-for-Ghana.txt | A **.txt mirror exists** and extracts cleanly (rare). Quantification is portfolio-level (NPV $28.5M–$231M across 9 programmes; 7.31 MtCO₂), but per-practice numbers may hide in the annexes I couldn't reach |

### Tier 2 - closes named gaps

| # | What | Where | Note |
|---|---|---|---|
| 6 | ⛔ **Ghana grid emission factor** | Energy Commission *National Energy Statistical Bulletin 2025* / *Energy Outlook 2025* (energycom.gov.gh); or the NID energy chapter | **Confirmed gap.** No official Ghana EF verified from any Ghanaian institution. The only figure locatable - 0.2629 kgCO₂e/kWh - is a Climatiq estimate traceable to **IEA 2011, 15 years stale**. IGES's list 403s. **Do not ship electricity advice to processors without this.** |
| 7 | Ghana **NDC + BUR4 + BTR1 + NID** | unfccc.int (URLs in research notes) | All reachable, **all text-extraction-failed**. Every Ghana government figure I quoted came from *secondary* corroboration, not the primary PDF |
| 8 | **PURC** current tariff, non-residential bands | https://www.purc.com.gh/ | PDF-only, FlateDecode. Tariffs changed **3× in 7 months** despite being "quarterly" |
| 9 | **COCOBOD** CSC standard + GS ARS 1000 Part 2 | Both **403** - likely bot-blocking; docs are real | Retry with a browser/different UA |
| 10 | Clean Cooking Alliance Ghana CAP + ESMAP baseline | https://cleancooking.org/investor-resources/countries/ghana/ | Need **per-unit stove prices**; snippets gave only market context |
| 11 | **IITA Ghana SIMFS baseline CSV** | https://data.iita.org/dataset/ghana-simfs-baseline-data | **CC BY 4.0, CSV, embargo lifted Nov 2024.** Free structured Ghana farm-structure data - cheap win |
| 12 | CGSpace OAI-PMH/REST probe | https://cgspace.cgiar.org/ | Confirm `/oai/request` + `/server/api/`; harvest Ghana CSA items **recording licence per item** (varies: CC BY vs CC BY-NC) |

### Tier 3 - worth it, not blocking

13. **AfricaFertilizer.org** - JS SPA, returned nothing. Probe for a JSON endpoint with a headless browser before concluding PDF-only. Genuinely Ghana-specific retail fertiliser prices.
14. **GIRSAL / Ghana EXIM / ADB Ghana** - contact directly for agri-SME rate sheets. Nothing queryable is published; GIRSAL's site is a programme description (70% credit guarantee), not a rate table.
15. **Eory et al. 2018 + OECD 2015** - read in full before building the ranking engine.
16. **Cool Farm Alliance** - ask for membership/API pricing (unpublished; API key carries an *additional* licensing fee) to make a build-vs-buy call.

### Verified down / blocked

`mofa.gov.gh` (**TLS cert expired**, both schemes) · `recpnet.org` (HTTP 522) · both COCOBOD CSC PDFs (403) · UNIDO Resource Productivity Guide (403) · IGES grid-EF list (403) · AfricaFertilizer Ghana dashboard (SPA) · NPA download links (didn't render - fuel figures came from news re-reporting, **transcription risk**).

---

## 7. Licensing - read before ingesting

| Source | Status | Action |
|---|---|---|
| **FAOSTAT** | ✅ **CC BY 4.0** - confirmed on the terms page | Clean. Use freely |
| **FAO EX-ACT** | ✅ Free, unrestricted, direct download | Clean. The spine |
| **IITA SIMFS**, some CGSpace items | ✅ CC BY 4.0 | Clean; record per item |
| **IPCC AR6 / EFDB** | ⛔ **NOT CC.** Personal/non-commercial only; product use needs written permission | Request now (~4wk) |
| **Project Drawdown** | ⚠️ **Contradictory.** Live terms = reserved copyright; old GitHub repo reported CC-BY-NC-2.0. The AI-crawl permission it grants is **revocable** and narrower than a data licence | **Legal review.** Also: single global average per solution - would mislead for Ghana anyway |
| **CGSpace** | ⚠️ **Varies per item** (CC BY *and* CC BY-NC both seen) | Record licence per document. **The NC clause bites if Green Means Go is commercial** |
| **CCAFS CSA-in-Ghana** | ⚠️ CC BY-**NC** 4.0 | Same NC caveat. And it's qualitative - zero effect sizes |
| **Cool Farm Tool** | 💰 Freemium; org use needs paid CFA membership; **API key has an additional undisclosed fee** | Build-vs-buy call |
| GHG Protocol, IFC EHS, World Bank docs | ❓ Not confirmed | Verify before ingesting |

**Maintain `LICENCES.md` with a licence field per source**, and have the recommendation layer check that flag before quoting source text - the pattern [`DATABASE_PLAN.md` §5](./DATABASE_PLAN.md) already mandates for ecoinvent.

---

## 8. Where Global-North data would actively mislead

Ingesting these uncritically produces confident, wrong advice for a Ghanaian smallholder. Each is **usable only when explicitly labelled non-local context**:

1. **IRENA $/kW** - global averages dominated by utility-scale China/OECD. Will **systematically underestimate** what a Ghanaian SME pays for a solar dryer (import duty, Tema freight, small-lot markup, diesel backup). IRENA itself flags Africa cost-of-capital ~12% vs Europe ~3.8%. **No Ghana-specific small-scale $/kW exists publicly.**
2. **UK CCC / ADAS MACCs** - £, large mechanised temperate N-intensive farms. Not adjustable.
3. **Project Drawdown** - one global average per solution, presented with false precision.
4. **IFC EHS food & beverage** - excellent kWh/tonne benchmarks (steam peeling 3.5, drum blanching 0.5–1.3), but for **industrial plants**, not a gari processor or a Chorkor smoker.
5. **Energypedia biogas $50–75/m³** - the Ghana-specific source explicitly says local fixed-dome costs *more*, and it's from 2014.
6. **Generic LCA databases for cocoa** - the MDPI *AgriEngineering* 7(12):419 cocoa-LCA review indicts exactly this: scarce socio-economic integration despite 80–90% smallholder production, geographically biased scope, heavy reliance on generic secondary databases.

**Conversely, these are real, Ghana-specific, and quantified** - the seed of the v1 library:

| Measure | Effect | Source |
|---|---|---|
| N-inhibitor, East Gonja | **N₂O −30.0%**, CO₂ −7.9%, **no significant yield loss** (350-farmer survey) | *Ecological Processes* (Springer) |
| Ahotor oven (fish smoking) | **+32% efficiency** vs Chorkor; ~12% lower CO/PM2.5; oil collector cuts PAH to near-zero | SNV / ScienceDirect S2949824424000417 |
| SNV gari cookstoves | **−30% fuelwood**, GHS 62.4/mo saved, **payback <11 months** | SNV |
| Cleaner palm oil (UNDP) | 2wk→5hrs processing; 4→20 t/day; diesel 6,000→1,500 GHS/mo via electrification | UNDP Ghana |
| Ghana Cocoa Forest REDD+ | 972,000 tCO₂ first monitoring period; yield 400→600 kg/ha since 2019; 69% of payments to farmer groups | World Bank |
| IFDC OFRA Ghana | Zone/crop fertiliser recs (rice NPK 15-20-20 4 bags/ha + 3 urea) | IFDC - **usable substitute while MoFA is down** |

---

## 9. Freshness policy - the highest-probability failure mode

Source volatility spans **four orders of magnitude**. A single static corpus will silently serve 2019 prices as current, and *vector similarity cannot detect this* - embeddings do not encode recency.

| Source | Refresh | Rots in |
|---|---|---|
| NPA fuel (petrol GH¢13.28/L, diesel GH¢14.35/L) | Bi-weekly windows | **2 weeks** |
| MoFA SRID prices | Biweekly | 2 weeks |
| PURC tariffs | Nominally quarterly - **3 changes in 7 months** | ~1 quarter |
| COCOBOD producer price | ≥2× per season | A season |
| Bank of Ghana MPR (14%, May 2026) | ~Bi-monthly | Months |
| FWSC minimum wage (**GH¢21.77/day**, 2026) | Annual | A year |
| IPCC factors | Per assessment cycle | Years |

Every record carries `valid_from` + `staleness_policy`, and the matcher applies a **hard freshness filter**. A stale record is **excluded**, not down-ranked.

### A named trap

COCOBOD's **main-crop** (US$5,040/t, GH¢3,228.75/64kg bag, eff. 7 Aug 2025) and **light-crop** (GH¢2,587/bag, from 18 Jun 2026) prices are **both official and both current-season**. Naive date-sorting produces a confidently wrong "current cocoa price." **Season and crop-type must be schema fields**, not inferred.

---

## 10. Open decisions (need product sign-off)

1. **Economics capture** - derive from prices (B), one banded question (C), or a full questionnaire block (A)? Recommendation: B + C now, A for processors.
2. **Commercial status.** This decides whether CC-BY-**NC** sources (CCAFS, much of CGSpace) are usable at all. Answer before ingesting.
3. **Recommendation model tier** - Opus 4.8 vs Sonnet 5 for the once-per-assessment recommendation path (chat stays Haiku 4.5).
4. **Scope of v1** - Ghana-only, crops + the two processing archetypes we have real data for (gari, fish smoking)? Or wider and thinner?
5. **Human review gate** - who signs off a measure before it goes live? The schema has `reviewed_by`; someone must fill it.
6. **How we present uncertainty to a farmer.** Every effect size has a range; a smallholder deciding whether to spend GH¢500 deserves the honest range, not a point estimate. This is a design problem, not a modelling one.

---

### Sources

Verified live 17 July 2026 unless flagged. Method/architecture: Parakeet (Amazon Science, ES&T/NeurIPS 2024 CCAI) · expert-grounded LLM-in-LCA benchmark arXiv:2510.19886 · GlobalQA arXiv:2510.26205 · Multi-Meta-RAG arXiv:2406.13213 · table-RAG arXiv:2504.01346, 2506.10380 · Program-of-Thoughts arXiv:2211.12588 · FinQA arXiv:2109.00122 · DocMath-Eval arXiv:2311.09805 · schema-constrained extraction arXiv:2601.14267 · Anthropic *Building Effective Agents*, *Advanced tool use*, *Contextual Retrieval*.
MACC critique: Eory et al. 2018 (DOI 10.1016/j.jclepro.2018.01.252) · OECD 2015 (5jrvvkq900vj-en) · FarmDyn (ageconsearch 334541) · cocoa-LCA review MDPI *AgriEngineering* 7(12):419.
Ghana: World Bank CSAIP · GCFRP · MoFA SRID · COCOBOD · PURC · NPA · FWSC · Bank of Ghana · IFDC OFRA · SNV · UNDP Ghana · IITA SIMFS · CCAFS/CGSpace.
