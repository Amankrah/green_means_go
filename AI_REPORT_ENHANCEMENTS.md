# AI Plain-Language Guide Layer

## Two-layer model

| Layer | Role | Source |
|-------|------|--------|
| **ISO draft** | Deterministic LCA report (numbers, boundaries, methodology) | `engine/iso_report.py` via `POST /assess` |
| **AI guide** | Plain-language interpreter only — restates and prioritises | `app/services/ai_report_generator.py` via `POST /reports/generate` |

**Rule:** AI may only explain what is already in `iso_report` + assessment metrics. It must not invent numbers, boundaries, or claim critical review is complete.

## Report types

| Type | Purpose | Section keys |
|------|---------|--------------|
| `farmer_friendly` | Farm guide for smallholders | `what_it_means`, `your_performance`, `practical_steps`, `what_we_didnt_count` |
| `executive` | Buyer/program admin summary (~250 words) | `executive_summary` |
| `comprehensive` | Commentary on each ISO block | `commentary_goal`, `commentary_scope`, `commentary_inventory`, `commentary_impact_assessment`, `commentary_interpretation`, `commentary_limitations` |

## Grounding

`app/services/report_grounding.py` builds a slim JSON payload from `assessment_data["iso_report"]` for LLM prompts. Generation fails with HTTP 400 if `iso_report` is missing (re-run assessment).

## Metadata

Every AI report includes:

- `disclaimer`: "Plain-language summary of the deterministic ISO draft. Not a substitute for independent critical review."
- `metadata.grounded_on_iso_report`: `true`
- `metadata.ai_role`: `"plain_language_guide"`
- `metadata.temperature`: `0`

## API usage

```python
# Requires assessment with iso_report from POST /assess
report = await generator.generate_comprehensive_report(assessment_data)
summary = await generator.generate_executive_summary(assessment_data)
guide = await generator.generate_farmer_friendly_report(assessment_data)
```

## Frontend UX

Results page order:

1. Impact dashboard (charts/cards)
2. **What this means for your farm** — AI guide (default: `farmer_friendly`)
3. **Technical report (ISO 14044 draft)** — collapsible `ISOReport` component

## PDF export

- Disclaimer on first page for all AI PDFs
- `comprehensive` PDF: deterministic ISO sections + AI commentary underneath each
- `farmer_friendly` PDF: AI guide + charts (no duplicate methodology chapter)
