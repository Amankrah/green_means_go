# Recommendation Data - Extraction Plan

> **Purpose.** Turn the acquired but unextracted files under `data/recommendations/`
> into curated measures, prices, and factors the recommendation engine actually uses.
> Every output follows the existing discipline: record type 5 in
> [`measures.jsonl`](../../engine/recommend/measures.jsonl) with non-null provenance, a
> licence row in [`LICENCES.md`](./LICENCES.md), and DRAFT status until re-reviewed via
> [`reviews.jsonl`](../../engine/recommend/reviews.jsonl). No number is invented: if a
> file does not state it, the field is null, not guessed.
>
> **Status:** Planning - **Scope:** Ghana - **Depends on:** [`RECOMMENDATION_ENGINE_PLAN.md`](./RECOMMENDATION_ENGINE_PLAN.md), [`LITERATURE_EXTRACTION.md`](./LITERATURE_EXTRACTION.md)

---

## 1. Where we are (audit, verified 2026-07-17)

Of 11 acquired files, 2 are fully extracted, 1 partial, 8 untouched. The live v1 library
leans on web research (IPCC, CCAFS, SNV, UNDP, IFC), not on most of these files.

| File | Status | Extractability (probed) |
|---|---|---|
| Tier1/Commodity prices CSV | ✅ done (PriceBook) | clean CSV |
| Tier2/2025 Energy Statistics.pdf | ✅ done (grid EF + mix) | text PDF, clean |
| Tier1/CSAIP for Ghana.txt | ⚠️ partial (2 measures) | plain text; annex tables not pulled |
| Tier2/ECG Tarrifs proposal.pdf | ❌ untouched | **text PDF, clean** (~2k chars/pg) |
| Tier2/Ghana Country Action Plan.pdf | ❌ untouched | **text PDF, clean**; it is a COOKSTOVE action plan (21 "cookstove" hits) |
| Tier2/Climate-smart cocoa in forest landscapes.pdf | ❌ untouched | **text PDF, rich** (~22k chars/3pg) |
| Tier2/COCOA...AWARENESS-AND-DECISION-MAKING.pdf | ❌ untouched | **text PDF, clean** |
| Tier2/6-CS-Cocoa-COCOBOD.pdf | ❌ untouched | ⚠️ **scanned** (~700 chars/3pg) - needs OCR |
| Tier1/EX-ACT_V9.4.2.xlsb | ❌ untouched | needs `pyxlsb`; binary macro workbook |
| Tier1/EX-ACT VC_v3.5.xlsx | ❌ untouched | needs `openpyxl` |
| Tier1/B-INTACT_v.1.9.xlsx | ❌ untouched | needs `openpyxl` |

### Delivered 2026-07-17 (E1-E5 + tractable E4)

- **E1 electricity tariff:** the gathered ECG file is a PROPOSAL whose end-user rate tables did not extract; recorded what it does provide (DSC1, cost of energy) and set a screening price (GHS 2.16/kWh, PURC research) in [`reference/ghana_electricity_tariff.json`](../../engine/recommend/reference/ghana_electricity_tariff.json), linked from the solar-drying measure. Acquire the PURC decision PDF to firm it.
- **E2 cookstove CAP:** a strategy doc; corroborated the two cookstove measures' cost/payback (no new effect sizes).
- **E3 cocoa:** three new DRAFT cocoa measures (`rehabilitate_with_hybrids`, `disease_phytosanitation`, `zone_shade_management`) from the two text PDFs + the OCR'd COCOBOD standard. Library 17 -> 20.
- **E5 CSAIP:** firmed the legume measure with CSAIP Table 14 (net -0.02 MtCO2, +40% yield boost, +11% maize).
- **E4 EX-ACT/B-INTACT:** both are IPCC-Tier-1 / ESVD CALCULATORS, not coefficient tables, and their factors are largely IPCC values the engine already applies. Extracted the tractable win: IPCC 2019 Table 5.5 tropical stock-change factors ([`reference/ipcc_stock_change_factors_gh.json`](../../engine/recommend/reference/ipcc_stock_change_factors_gh.json), no-till FMG 1.10), firming the conservation-tillage measure. Full EX-ACT-as-carbon-engine / B-INTACT-biodiversity integration is deferred as a separate, larger feature with mostly-redundant coefficients.

**The concrete gaps these leave:**

1. **No electricity input price** in the economic screen (ECG tariffs unextracted). Processor opex/payback on electricity measures falls back to the questionnaire.
2. **One cocoa measure only**, sourced from the CSAIP rather than the three authoritative cocoa documents. A conspicuous hole for a Ghana-first tool.
3. **Effect sizes lean on expert judgement.** Several measures are `basis: expert_judgement` because the modelled source (EX-ACT) was never opened.

---

## 2. Cross-cutting rules (apply to every phase)

- **Evidence-gated extraction.** Each extracted value carries a provenance span (the exact quoted sentence/cell). If the source does not state it, the field is null. Same rule as v1.
- **Draft by default.** Every new or upgraded measure loads with `reviewed_by: null`, so it does NOT reach users until a domain specialist adds an `approved` line to `reviews.jsonl`. Extraction re-opens the review cycle for new content only; the 17 already-approved measures are untouched.
- **Licence first.** Add a row to `LICENCES.md` for each new source before the measure that cites it loads. Free-tool status ([[free-tool]]) keeps NC/IGO sources in scope with attribution.
- **Units are typed.** Effect units map to the `EffectUnit` enum; prices to GHS with an `as_of`; factors to a provenanced reference file. No bare numbers.
- **No number touches the LLM.** Everything extracted lands in the deterministic layer (measures, prices, reference factors). The chat only explains.

---

## 3. Phases

Ordered by value-over-effort and by dependency. Each phase is independently shippable and
ends with a test + a re-review prompt.

### Phase E1 - Electricity tariff (closes the economic-layer gap) - SMALL

**Input:** `ECG Tarrifs proposal.pdf` (clean text). Cross-check against PURC if a newer approved tariff exists.

**Method:** `pdftotext -layout`, pull the non-residential / industrial tariff bands (pesewas/kWh) and the effective date.

**Deliverable:**
- A provenanced reference `engine/recommend/reference/ghana_electricity_tariff.json` (bands, GHS/kWh, `as_of`, `staleness_policy: quarterly`).
- Wire it into `economics.py` as the electricity price for processor opex, so the electricity measures (solar drying, electrification, efficient stoves) get real payback instead of a gap.
- A `price.ghs.electricity.ecg` row in `LICENCES.md`.

**Test:** a processing assessment's electricity measures show a payback derived from the tariff, not a data gap.

### Phase E2 - Cookstove action plan (strengthens existing processing measures) - SMALL

**Input:** `Ghana Country Action Plan.pdf` (clean; it is a cookstove CAP).

**Method:** `pdftotext`, extract stove efficiency gains, adoption costs, and fuel-saving figures for improved cookstoves.

**Deliverable:**
- Upgrade the two cookstove measures (`meas.proc.efficient_gari_stove.gh`, `meas.proc.efficient_smoking_oven.gh`) with any firmer effect/cost numbers, raising confidence or moving `basis` toward `measured` where the CAP supports it.
- Possibly one new institutional/clean-cooking measure.
- `Ghana-CleanCooking-CAP` licence row.

**Test:** the cookstove measures carry a second corroborating source; `test_recommend` still green.

### Phase E3 - Cocoa measures (fills the crop hole) - MEDIUM

**Inputs (in extractability order):**
1. `Climate-smart cocoa in forest landscapes.pdf` (rich text) - primary.
2. `COCOA...AWARENESS-AND-DECISION-MAKING.pdf` (clean text) - practices + adoption.
3. `6-CS-Cocoa-COCOBOD.pdf` (**scanned - OCR required**) - the authoritative CS-Cocoa standard; attempt `ocrmypdf`/Tesseract, else defer and rely on 1+2 with a flag.

**Method:** extract shade-tree / agroforestry, pruning/rehabilitation, fertiliser-rate, and pod-disease measures with quantified yield/carbon/cost where stated.

**Deliverable:**
- A cluster of cocoa measures (`meas.cocoa.*`) targeting cocoa hotspots (fertiliser, field emissions, land), each region GH, crop cocoa, with provenance spans.
- New licence rows (`CS-Cocoa-ForestLandscapes`, `Cocoa-CSA-DecisionMaking`, `COCOBOD-CSCocoa`).
- Retire or corroborate the single CSAIP-sourced `meas.system.agroforestry_cocoa.gh` against these better sources.

**Test:** a cocoa assessment (crop = cocoa) surfaces cocoa-specific measures, not just the generic agroforestry one.

### Phase E4 - EX-ACT / B-INTACT (the methodological spine) - LARGE

**Prerequisite:** `pip install openpyxl pyxlsb` into the venv (no Excel lib is currently present).

**Inputs:** `EX-ACT_V9.4.2.xlsb` (via pyxlsb), `EX-ACT VC_v3.5.xlsx`, `B-INTACT_v.1.9.xlsx` (via openpyxl).

**Method:** these are calculators, not tables of measures, so extraction is different: pull the **per-practice GHG coefficients** and (from EX-ACT VC) the socio-economic outputs that back the practice categories already in the library. B-INTACT gives biodiversity (MSA-style) deltas that map to the engine's biodiversity category.

**Deliverable:**
- Upgrade `expert_judgement` measures (split application, compost, IPM, machinery, conservation tillage, etc.) to `basis: modelled` with EX-ACT-derived effect sizes and uncertainty, where EX-ACT covers the practice.
- Add biodiversity effect fields to relevant measures from B-INTACT.
- A `reference/exact_coefficients.json` provenance record set.

**Risk/caveat:** EX-ACT is a complex macro workbook; coefficient extraction requires understanding its sheet structure and is the highest-effort item. Budget for exploration before committing to a schema. Confirm the EX-ACT VC deprecation status first (flagged in the research).

**Test:** upgraded measures report `basis: modelled` with an EX-ACT provenance span; effect magnitudes stay within their prior uncertainty range (sanity gate).

### Phase E5 - CSAIP annex tables (finish the partial) - SMALL

**Input:** the CSAIP `.txt` already on disk.

**Method:** systematically walk the annex tables (the per-programme EX-ACT results and investment costs) rather than the ad-hoc grep used in v1.

**Deliverable:** firmer numbers behind the two CSAIP-sourced measures, plus any per-practice figures the annexes hold.

---

## 4. Sequence and effort

| Phase | Effort | Unblocks | Prereq |
|---|---|---|---|
| E1 electricity tariff | small | economic screen for processors | none |
| E2 cookstove CAP | small | firmer cookstove measures | none |
| E3 cocoa | medium | cocoa crop coverage | OCR for 1 of 3 files |
| E4 EX-ACT / B-INTACT | large | modelled effect sizes, biodiversity | `pip install openpyxl pyxlsb` |
| E5 CSAIP annexes | small | firmer CSAIP measures | none |

**Recommended order: E1, E2, E3, then E5, then E4.** Front-load the clean-text PDFs that
close concrete gaps (tariff, cocoa) and defer the Excel spine to last because it is the
largest effort and needs a dependency added. Each phase ends by re-opening the review gate
for its new/changed measures only.

---

## 5. Definition of done (per phase)

1. Extracted values in the right typed store (measure record / price record / reference factor), provenance span non-null.
2. Licence row added for every new source.
3. New/changed measures are DRAFT (`reviewed_by: null`); a re-review worksheet is generated (`python review.py --pending`).
4. Tests green (`test_recommend`, `test_economics`, plus any phase-specific test).
5. This plan's audit table updated to move the file to ✅.

### Sources

Acquired files under `data/recommendations/` (Tier1/Tier2). Extraction tooling: `pdftotext -layout` (poppler, present), `ocrmypdf`/Tesseract for the scanned COCOBOD standard, `openpyxl` + `pyxlsb` (to be installed) for the Excel tools.
