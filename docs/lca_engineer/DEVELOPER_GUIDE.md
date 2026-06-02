# LCA Engineer — Developer Guide

> **What we are building.** A backend **LCA Engineer**: a system that takes a user's reported activity data, builds a real Life-Cycle Inventory, runs ISO-14040/14044-compliant impact assessment against authoritative databases (Agribalyse, ecoinvent, ReCiPe, EF, AWARE, IPCC), and uses AI subsystems (OpenAI + Claude) for matching, retrieval (RAG), decomposition, and anomaly detection — all with full provenance and human-in-the-loop oversight.
>
> It starts where the current code is strong (Ghana/Nigeria agri-food, Rust performance core, pedigree/uncertainty) and removes its core limitation: hand-coded, non-auditable, single-number factors.
>
> Read alongside: [`DATABASE_PLAN.md`](./DATABASE_PLAN.md) · [`LITERATURE_WISHLIST.md`](./LITERATURE_WISHLIST.md) · [`LITERATURE_EXTRACTION.md`](./LITERATURE_EXTRACTION.md)

---

## 1. Mission & breakthrough thesis

**Mission:** make rigorous, defensible LCA *accessible and fast* for African agri-food actors who today are under-served by data and tooling.

**The breakthrough we're chasing:** LCA today is slow, expensive, expert-bound, geographically biased toward industrialised countries, and hard to reproduce. The literature names the bottlenecks plainly (see §2). Our thesis: **a hybrid system — a deterministic, provenance-tracked LCA core wrapped in AI subsystems for the human-bottleneck steps (matching, data-gap filling, extraction, QA) — can cut an LCA from weeks to minutes without sacrificing auditability**, while *regionalising* for Africa where global databases are silent.

The non-negotiable: **AI augments, never replaces, the deterministic computation and expert judgement.** Every number the engine outputs is traceable to a loaded dataset or a flagged estimate. The AI's job is to *propose, retrieve, and flag* — the engine *computes*, and a human *can review*.

---

## 2. The bottlenecks we exist to unlock (grounded in research)

| # | Bottleneck (from the literature) | How the LCA Engineer addresses it |
|---|----------------------------------|-----------------------------------|
| B1 | **LCI data scarcity** — robust inventory data is "the cornerstone… and the central bottleneck." | Background DBs (ecoinvent/Agribalyse/WFLDB) + KG-embedding gap-filling + EXIOBASE hybrid for un-modelled sectors. |
| B2 | **Inventory collection & matching is manual and slow** — mapping a user's inputs to database processes is the top time sink. | AI **matching subsystem**: LLM-generated process descriptions + embedding/FAISS retrieval + top-5 human confirm. |
| B3 | **Geographic representativeness** — using a European mix for an African facility "misrepresents water stress, land use, and more." | Regionalisation layer: country grid factors, AWARE water CFs, GLEAM/FAOSTAT African activity data, climate adjustments. |
| B4 | **Uncertainty is poorly quantified & communicated.** | Proper pedigree→lognormal mapping (Weidema 2013) + Monte Carlo + always-on confidence intervals + data-quality scoring. |
| B5 | **Reproducibility / auditability** — results can't be traced or re-run. | Versioned canonical store + ISO 14048 provenance on every factor + deterministic core + recompute-on-source-update. |
| B6 | **Report generation is laborious.** | RAG-grounded AI reporting (already prototyped in `app/services/ai_report_generator.py`) extended to cite loaded factors. |
| B7 | **LLM hallucination / opacity** when AI is naively applied to LCA. | Hard rules: AI never writes computed values; cites provenance; validated against ranges; human-in-loop on low-confidence. |
| B8 | **Geographical inequality** — LCA capacity concentrated in industrialised countries; Nigeria/smallholder systems under-represented. | Africa-first scope, LEAP smallholder methods, free-tier (Tier-1) build needing no paid database. |

---

## 3. Objectives (what "done" means per phase)

**O1 — Real inventory.** Replace hand-coded factors with loaded, provenance-tracked LCI + LCIA databases; solve the inventory as `g = B · A⁻¹ · f`, not per-kg proxies.
**O2 — ISO compliance.** Implement the four phases (Goal&Scope, LCI, LCIA, Interpretation) with 14044 allocation/cut-off/data-quality rules enforced and checkable.
**O3 — Method fidelity.** Real ReCiPe 2016 (+ EF 3.1) CF tables; real AWARE/IPCC factors; correct uncertainty propagation.
**O4 — AI augmentation.** Ship the four subsystems (§5) with measured accuracy and human-in-the-loop gates.
**O5 — Regionalisation.** Ghana/Nigeria-resolved electricity, water, crop, and livestock data; graceful fallback hierarchy with confidence labels.
**O6 — Auditability.** Any result reproducible from stored inputs + database versions; every factor cites a source.

---

## 4. Architecture

```
            ┌──────────────────────────────────────────────────────────────┐
            │  Frontend (Next.js)  — assessment forms, results, reports     │
            └───────────────────────────┬──────────────────────────────────┘
                                         │ HTTP/JSON
            ┌───────────────────────────▼──────────────────────────────────┐
            │  Python API + AI Orchestration (FastAPI)                      │
            │  • request handling, auth                                     │
            │  • AI subsystems (OpenAI + Claude): matching, RAG, decompose, │
            │    anomaly detection, report generation                       │
            │  • Brightway/olca importers (DB ingestion & validation)       │
            └───────────────┬───────────────────────────┬──────────────────┘
              compute call   │                           │ read-only
            ┌───────────────▼─────────────┐   ┌──────────▼───────────────────┐
            │  Rust LCA Core (deterministic)│  │  Canonical Data Store        │
            │  • LCI assembly & matrix solve│◀─│  • Postgres (datasets, CFs,  │
            │  • LCIA characterization      │   │    flows, provenance,        │
            │  • normalisation/weighting    │   │    pedigree)                 │
            │  • uncertainty / Monte Carlo  │   │  • Parquet (A,B matrices)    │
            │  • pedigree data quality      │   │  • Vector DB (embeddings)    │
            └───────────────────────────────┘   └──────────────────────────────┘
```

**Why this split:**
- **Rust core = trust & speed.** Pure, deterministic, no network — the part a reviewer audits. Evolves the existing `african_lca_backend` engine (keep its strengths: pedigree, uncertainty, African adjustments) but feed it loaded matrices/CFs instead of `match` tables.
- **Python = orchestration & AI.** Where probabilistic/LLM work lives, isolated from computation. Extends the existing `app/` (which already calls Claude/OpenAI for reports).
- **Canonical store = single source of truth**, versioned, provenance-complete.
- **Hard boundary:** AI outputs enter the Rust core only as *typed, validated, provenance-tagged inputs* (a chosen dataset id, a flagged estimate) — never as free text or unvalidated numbers.

---

## 5. The AI subsystems (OpenAI + Claude)

Each subsystem has: a **job**, a **guardrail**, and a **success metric.** All are designed from the cited research (`LITERATURE_EXTRACTION.md §12`).

### 5.1 Matching subsystem (the #1 time-saver)
- **Job:** map free-text user inputs ("NPK 15-15-15, 50 kg/acre", "diesel for ploughing", "local maize") → canonical activities / background datasets.
- **How:** hybrid pipeline — LLM (Claude/OpenAI) generates a normalised process description from the user term + context → embed → cosine search over the **process/flow vector store** (FAISS/Qdrant) → return **top-5 candidates with scores**.
- **Guardrail:** *semantic similarity alone scores ~5% top-5; LLM+context ~48% (ENTITY-LINK)* → always show ranked candidates, require user/expert confirmation for low-margin matches, log confirmed matches to the **gold-set** (DB E2) to improve over time.
- **Metric:** top-1 / top-5 match accuracy vs gold-set; % matches auto-accepted vs escalated.

### 5.2 Retrieval-Augmented Generation (RAG) over the literature/method corpus
- **Job:** ground every methodological answer, factor explanation, and report sentence in the real sources (corpus E3) — no hallucinated factors.
- **How:** chunk + embed the literature (`LITERATURE_WISHLIST.md`), retrieve on query, generate with citations. Used by the report generator and the "explain this number" feature.
- **Guardrail:** answers must cite a source chunk; if retrieval confidence is low, say "insufficient grounding" rather than invent.
- **Metric:** citation-faithfulness (sampled), groundedness score, hallucination rate on a held-out method-QA set.

### 5.3 Decomposition subsystem
- **Job:** break complex/ambiguous user submissions into modelable unit processes ("cassava gari processing" → harvest → transport → peeling → grating → pressing → frying → packaging), and decompose extraction queries (LLM-EST pattern).
- **How:** LLM planner proposes a process tree against process templates (from Agribalyse structure) → each leaf goes to the matching subsystem → assembled into the LCI graph for the Rust core.
- **Guardrail:** proposed trees are templates a human can edit; mass/energy balance checked before solving.
- **Metric:** % of decompositions accepted without edit; balance-check pass rate.

### 5.4 Anomaly detection / data-quality QA
- **Job:** catch bad inputs and implausible results before they reach a user — implausible quantities (e.g. existing `lca.rs` already warns on >20 kg meat), unit errors, factors outside plausible ranges, results far from Poore&Nemecek benchmarks.
- **How:** range/physics checks + statistical outlier detection against `benchmark` records + pedigree-weighted confidence; contextual anomalies (e.g. yield-per-hectare impossible for region) flagged.
- **Guardrail:** anomalies *flag and explain*, they don't silently correct; high-severity blocks the result pending review.
- **Metric:** precision/recall on a labelled anomaly set; false-block rate.

**Cross-cutting AI rules (from LLM-OCR risks):**
1. AI never authors a computed impact value. 2. Every AI assertion carries provenance or an explicit "estimate/low-confidence" tag. 3. Low-confidence → human-in-the-loop. 4. Model + prompt + version logged per call (reproducibility). 5. Validated against deterministic ranges before use.

---

## 6. The computation pipeline (ISO 14040/44)

1. **Goal & Scope** — functional unit (e.g. "1 kg maize at farm gate, Ghana, 2024"), system boundary, cut-off, chosen LCIA method. AI helps draft; user/engine confirms.
2. **LCI** — user inputs → (decomposition) → process tree → (matching) → datasets/EFs → assemble technosphere `A` + biosphere `B` → solve `s = A⁻¹·f`, `g = B·s`. Agricultural field emissions (N₂O, CH₄, etc.) via IPCC 2019 equations. *(Evolves `lci.rs`.)*
3. **LCIA** — classify + characterize (`g·CF` per ReCiPe/EF) → optional normalise + weight → midpoint, endpoint, single score. *(Evolves `lca.rs`; replaces approximate endpoint math with loaded CFs.)*
4. **Interpretation** — contribution analysis, uncertainty (Monte Carlo over pedigree-derived distributions), sensitivity, data-quality report, anomaly flags, benchmark comparison, AI-generated narrative (RAG-grounded).

---

## 7. Data quality, uncertainty, provenance (the credibility layer)

- **Pedigree matrix** implemented to Weidema 2013 (lognormal σ² lookup) — fix the ad-hoc factors in current `PedigreeScore`.
- **Monte Carlo** over correlated lognormal distributions for impact CIs; report P10/P50/P90.
- **Provenance** (ISO 14048) attached to every factor and propagated to results; a result can be expanded to "which datasets, which versions, which assumptions."
- **Confidence labels** on every output: Country-specific > Regional > Global-adjusted > Estimated (extends current `DataQuality` logic).
- **Reproducibility:** store inputs + all database versions + AI model/prompt versions per assessment; re-run yields the same result (deterministic core) and can be refreshed when a source updates.

---

## 8. Roadmap & milestones

| Phase | Goal | Key deliverables | Depends on |
|-------|------|------------------|------------|
| **P0 (now)** | Baseline preserved | Keep current engine as fallback + sanity checker | — |
| **P1 — Foundation (free)** | Real factors, no paid DB | Load Agribalyse foreground, ReCiPe 2016, IPCC AR6/2019, AWARE, FAOSTAT, IPCC EFDB; canonical store + provenance; pedigree fix; RAG corpus | Tier-1 DBs; P0 extraction |
| **P2 — Supply chain + AI** | Cradle-to-gate + subsystems | ecoinvent (LMIC license), GLEAM, EF 3.1, flow mapping; matching + decomposition + anomaly subsystems; matrix solver in Rust | Tier-2 DBs; vector store; gold-set |
| **P3 — Advanced** | Coverage + hybrid | WFLDB, EXIOBASE hybrid, USEtox/LANCA; KG-embedding gap-filling; multi-method switching; critical-review export | Tier-3 DBs |

---

## 9. Success metrics

- **Accuracy:** engine results within published ranges (Poore&Nemecek/Agribalyse) for validated reference products.
- **Speed:** assessment in minutes, not weeks (B2 bottleneck).
- **Coverage:** % of user inputs auto-matched with confidence; # Ghana/Nigeria-resolved datasets.
- **Auditability:** 100% of output values trace to a provenance record; reproducible re-run.
- **AI quality:** match top-5 accuracy, RAG groundedness, anomaly precision/recall, hallucination rate ≈ 0 on computed values.
- **Trust:** results survive a critical review (ISO 14071) by an external LCA expert.

---

## 10. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| ecoinvent license/redistribution | LMIC academic license via partner; never expose raw data; aggregate-only outputs |
| AI hallucinates factors | AI never writes computed values; provenance-or-reject; validation gate; human-in-loop |
| African data gaps persist | Tiered fallback w/ confidence labels; GLEAM/FAOSTAT/EXIOBASE; KG-embedding extrapolation with disclosed uncertainty |
| Flow nomenclature mismatch (silent errors) | Normalise to EF/ILCD list; log unmapped flows as anomalies; GLAD mappings |
| Over-trust in single score | Always show midpoints + uncertainty; flag single score as value-choice (ISO) |
| Reproducibility drift | Version DBs + AI prompts/models; deterministic core; recompute-on-update |

---

## 11. How this maps onto the existing code

- `african_lca_backend/src/production/lci.rs` → **LCI assembly + IPCC-2019 equations**, fed by loaded EFs instead of hardcoded `EmissionFactorsDatabase`.
- `african_lca_backend/src/production/lca.rs` → **LCIA** with loaded ReCiPe/EF CFs; replace `get_default_impact_factor` (keep as last-resort fallback) and the approximate endpoint/benchmark constants.
- `app/services/ai_report_generator.py` → extend into the **RAG report subsystem**; add matching/decomposition/anomaly services alongside.
- New: `ingestion/` (Brightway/olca importers + validators), `canonical store` (Postgres + Parquet + vector DB), `references/` (literature + extracted records).

---

*This guide is the contract: deterministic, auditable computation at the core; AI to remove the human bottlenecks around it; Africa-first data to fix the representativeness gap. Build Tier-1 first — it proves the whole thesis with zero licensing cost.*
