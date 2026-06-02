# LCA Engineer — Literature Wishlist

> **Purpose.** The reading + acquisition list to build a defensible, ISO-compliant, AI-augmented LCA Engineer. For each item: **what it is**, **why we need it**, **how to obtain it** (open vs. paywalled), and **priority** (P0 = blocking, P1 = important, P2 = enriching). Items feed two things: (1) the structured factor/method extraction in [`LITERATURE_EXTRACTION.md`](./LITERATURE_EXTRACTION.md), and (2) the RAG citation corpus (database E3 in [`DATABASE_PLAN.md`](./DATABASE_PLAN.md)).
>
> Acquire P0 first — they are the methodological backbone. Store every PDF with a citation key in a `references/` folder so the RAG layer can ground answers in real sources.

Legend: 🟢 open/free · 🟡 free report but large/spreadsheet · 🔴 paywalled (need library/partner access)

---

## 1. Core standards & guidelines (the rulebook) — mostly P0

| Key | Title | Why we need it | Access | Priority |
|-----|-------|----------------|--------|----------|
| ISO-14040 | ISO 14040:2006 *Environmental management — LCA — Principles and framework* | The four-phase structure (Goal&Scope → LCI → LCIA → Interpretation) the engine must implement and name. | 🔴 ISO store / national standards body | **P0** |
| ISO-14044 | ISO 14044:2006(+A1/A2) *Requirements and guidelines* | Allocation rules, cut-off criteria, data-quality requirements, the *normative* requirements a reviewer checks us against. | 🔴 ISO store | **P0** |
| ISO-14067 | ISO 14067:2018 *Carbon footprint of products* | Product carbon-footprint rules — our headline metric for users. | 🔴 ISO | P1 |
| ISO-14048 | ISO 14048 *Data documentation format* | Schema for dataset provenance/metadata (drives our canonical store). | 🔴 ISO | P1 |
| ISO-14071 | ISO 14071 *Critical review processes* | Defines review/verification — informs our QA + "AI must be reviewable" stance. | 🔴 ISO | P2 |
| ILCD-HB | ILCD Handbook (EC/JRC) *General guide for LCA — Detailed guidance* | The most operational free interpretation of ISO; concrete on LCI modelling, allocation, nomenclature. | 🟢 EPLCA | **P0** |
| EF-METH | EC Recommendation 2021 + EF 3.1 method docs (PEF/OEF) | EU regulatory method; CF set; PEFCR structure for food. | 🟢 EPLCA / JRC | P1 |
| GHGP-PROD | GHG Protocol *Product Life Cycle Accounting & Reporting Standard* | Widely-required corporate carbon accounting rules; aligns us to client reporting. | 🟢 ghgprotocol.org | P1 |
| PAS2050 | PAS 2050:2011 (BSI) | Pragmatic product carbon-footprint spec, still referenced in agri-food. | 🟡 BSI (free w/ registration) | P2 |

## 2. Agri-food & livestock method guidance — P0/P1 (this is our domain)

| Key | Title | Why | Access | Priority |
|-----|-------|-----|--------|----------|
| LEAP-CROP | FAO LEAP *Environmental performance of large ruminant / crop supply chains* + **Soil carbon**, **Nutrient flows**, **Water use**, **Feed** guidelines | The harmonised agri-food LCA methods with explicit smallholder/developing-country guidance. Directly governs how we model N₂O, manure, feed, soil C in Ghana/Nigeria. | 🟢 FAO | **P0** |
| GLEAM-DOC | FAO GLEAM model documentation | Spatial tier-2 livestock emission modelling with Africa coverage. | 🟢 FAO | P1 |
| AGB-METH | AGRIBALYSE 3.x methodology report (ADEME/INRAE, Revalim) | Our template for food-product LCI construction, allocation, and consumption-vs-production modelling. | 🟢 doc.agribalyse.fr | **P0** |
| WFLDB-GL | World Food LCA Database guidelines (Quantis) | Agri-food background modelling conventions consistent with Agribalyse. | 🟢 (guidelines free) | P1 |
| IPCC-2019 | IPCC 2019 Refinement to 2006 Guidelines, **Vol 4 (AFOLU)** Ch 10–11 | EF1/EF2/EF3 N₂O factors, FracLEACH/FracGASF, enteric CH₄, rice CH₄, manure, liming, urea. Already cited in `lci.rs` — we must extract the *full* tables, not single values. | 🟢 IPCC | **P0** |
| IPCC-AR6 | IPCC AR6 WG1 Ch7 + Annex (GWP/GTP tables) | Authoritative GWP100/GWP20 and GWP* for CH₄. | 🟢 IPCC | **P0** |

## 3. LCIA method source documents (characterization factors) — P0/P1

| Key | Title | Why | Access | Priority |
|-----|-------|-----|--------|----------|
| ReCiPe-2016 | ReCiPe 2016 v1.1 *Report I: Characterization* (RIVM 2016-0104) **+ CF spreadsheets** | The actual midpoint+endpoint CFs (17 categories, H/I/E) we will load to replace approximations in `lca.rs`. | 🟡 RIVM (report 🟢, spreadsheets 🟡) | **P0** |
| ReCiPe-PAPER | Huijbregts et al. 2017, *ReCiPe2016: a harmonised LCIA method…* (Int J LCA) | Peer-reviewed rationale + endpoint derivation; RAG-citable. | 🔴 Springer (preprint 🟢 on ResearchGate) | P1 |
| EF31-CF | JRC *Updated characterisation & normalisation factors for EF 3.1* (JRC130796) | The EF CF/NF spreadsheets. | 🟢 JRC | P1 |
| AWARE | Boulay et al. 2018, *The WULCA consensus… AWARE* (Int J LCA) **+ country/monthly CF files** | Real water-scarcity CFs to replace hardcoded Ghana=20/Nigeria values. | 🟡 paper 🔴 / CFs 🟢 (WULCA) | **P0** |
| USEtox | Rosenbaum et al. 2008 + USEtox 2.x docs & factor files | Toxicity CFs (our weakest categories). | 🟢 usetox.org | P1 |
| LANCA | Bos et al. / JRC LANCA CFs for land use & soil quality | Soil/land/erosion CFs for agri-food. | 🟢 JRC | P1 |

## 4. Foundational & benchmark science — P0/P1

| Key | Title | Why | Access | Priority |
|-----|-------|-----|--------|----------|
| POORE-2018 | Poore & Nemecek 2018, *Reducing food's environmental impacts through producers and consumers* (Science) **+ supplementary dataset** | The global food-LCA benchmark already used as our default factors; SI has per-product distributions for sanity checks & benchmarking. | 🔴 Science (SI dataset 🟢) | **P0** |
| WATER-FP | Mekonnen & Hoekstra 2011, *The green, blue and grey water footprint of crops* | Crop water footprints, country-resolved — feeds water modelling & validation. | 🟢 HESS (open) | P1 |
| PEDIGREE | Weidema & Wesnæs 1996 + Weidema et al. 2013 (ecoinvent data quality guideline) | The pedigree-matrix → uncertainty-factor mapping our `PedigreeScore` should implement *correctly* (lognormal variance). | 🟢/🟡 | **P0** |
| MC-LCA | Heijungs & Lenzen, uncertainty/Monte-Carlo in LCA (methodological) | Correct uncertainty propagation & sensitivity (our current code is simplified). | 🔴/🟢 mix | P1 |

## 5. AI / ML in LCA — the differentiator — P0/P1

| Key | Title | Why | Access | Priority |
|-----|-------|-----|--------|----------|
| LLM-OCR | *Large language models for life cycle assessments: opportunities, challenges, and risks* (J. Cleaner Prod., 2024) | Frames the three domain-specialisation strategies (external augmentation/RAG, prompt-crafting, PEFT) and the hallucination/transparency risks our design must mitigate. | 🔴 Elsevier (preprint 🟢 academia.edu) | **P0** |
| LLM-EST | *A Large Language Model-based Framework to Retrieve LCI and Environmental Impact Data from Scientific Literature* (Environ. Sci. Technol., 2025) | Blueprint for our literature-extraction + RAG subsystem (decomposition → retrieve → extract → validate). | 🔴 ACS | **P0** |
| ENTITY-LINK | *Entity Linking using LLMs for Automated Product Carbon Footprint Estimation* (arXiv 2502.07418, 2025) | Concrete matching architecture: gte-large embeddings + FAISS + fine-tuned Llama generating process descriptions. **Key finding: semantic similarity alone ≈5% top-5; LLM+datasheet+embedding ≈48% top-5** → mandates hybrid + human-in-loop. | 🟢 arXiv | **P0** |
| KG-EMB | *Knowledge graph embeddings for extrapolation of LCI data* (Sci. Total Environ., 2025) | Method to **fill LCI data gaps** via KG embeddings (reported MAPE ~2.4% on ecoinvent) — directly relevant to African data scarcity. | 🔴 Elsevier | P1 |
| LLM-METH | *Intelligent application of large language model to LCA methodology* (J. Cleaner Prod., 2025) | Patterns for LLM-assisted goal&scope / interpretation / report generation. | 🔴 Elsevier | P1 |
| SLCA-LLM | *Towards AI-augmented sustainability assessments… social LCA* (Int J LCA, 2025) | Human-in-the-loop augmentation patterns (not replacement). | 🔴 Springer | P2 |
| DIGITAL-LCA | *How digital technologies could empower LCA studies* + *Digital technologies for LCA: review & framework* (Int J LCA, 2024/25) | Survey of automation/digitalisation — situates our subsystems in the field. | 🔴 Springer | P1 |

## 6. Data-system, gaps & regional context — P1/P2

| Key | Title | Why | Access | Priority |
|-----|-------|-----|--------|----------|
| ROBUST-DATA | *Addressing critical challenges towards a robust data system for LCA* (Nature Rev. Clean Tech., 2025) | Authoritative statement of the data bottlenecks we aim to unlock (interoperability, gaps, uncertainty communication). | 🔴 Nature (abstract 🟢) | **P0** |
| GAP-METHODS | *Approaches for addressing LCA data gaps for bio-based products* | Concrete proxy/surrogate & data-creation methods for missing data. | 🟢 ResearchGate | P1 |
| NIGERIA-LCA | *Life cycle assessment research and application in Nigeria* (Int J LCA, 2024) | State of LCA in our target country — gaps, sectors, data availability, recommendations. | 🔴 Springer | P1 |
| LCA-REVIEW | *LCA as a Catalyst for Environmental Transformation: Systematic Review 2018–2024* (Sustainability, 2024) | Broad bottleneck taxonomy (methodological + institutional + geographical inequality). | 🟢 MDPI | P1 |
| AFRICA-DATA | National sources in `../../data_sources.md` (Ghana EPA/MOFA/CSIR; Nigeria FME/IITA/NASS) | Primary regionalisation data; partnership targets. | 🟢/partnership | P1 |

---

## Acquisition workflow

1. **P0 sweep first** — these block the Tier-1 build (ReCiPe, IPCC 2019/AR6, AWARE, LEAP, Agribalyse method, Poore&Nemecek SI, pedigree, the 3 AI-method papers, ISO 14040/44 + ILCD).
2. For 🔴 paywalled items, route through a **university partner** (also the path to the free ecoinvent LMIC license) or use the 🟢 preprint where noted.
3. Save each as `references/<KEY>.pdf` + a BibTeX entry in `references/refs.bib`.
4. Tag each with the categories in `LITERATURE_EXTRACTION.md` so extraction is traceable.
5. Load cleaned text + tables into the **RAG corpus** (E3) with citation metadata so the AI grounds every claim.

### Sources (for items surfaced via web research)
- [LLMs for LCA: opportunities, challenges, risks](https://www.sciencedirect.com/science/article/abs/pii/S095965262402273X)
- [LLM framework to retrieve LCI from literature (ES&T 2025)](https://pubs.acs.org/doi/10.1021/acs.est.5c05955)
- [Entity Linking using LLMs for PCF (arXiv)](https://arxiv.org/html/2502.07418v1)
- [Knowledge graph embeddings for LCI extrapolation](https://www.sciencedirect.com/science/article/abs/pii/S0195925525004585)
- [Robust data system for LCA (Nature Rev. Clean Tech.)](https://www.nature.com/articles/s44359-025-00107-4)
- [LCA systematic review 2018–2024 (MDPI)](https://www.mdpi.com/2071-1050/18/5/2284)
- [LCA research & application in Nigeria](https://link.springer.com/article/10.1007/s11367-024-02423-6)
- [ReCiPe 2016 report](https://www.rivm.nl/bibliotheek/rapporten/2016-0104.pdf) · [FAO LEAP](https://www.fao.org/partnerships/leap/en) · [AGRIBALYSE docs](https://doc.agribalyse.fr/documentation-en)
