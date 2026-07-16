# engine/ — region-aware cradle-to-gate LCA orchestrator

Option A (see `docs/lca_engineer/RUST_WIRING_PLAN.md`): **Rust = on-farm LCI kernel,
Python = supply-chain LCI + characterization** through the single validated canonical
path. Region-parameterised so Ghana, Nigeria and Canada are registry entries.

## Modules
| file | role |
|------|------|
| `regions.py` | Data-driven region registry (grid location prefs, AWARE key, IPCC climate/EF1, default LCIA method, currency). Add a region = add an entry. |
| `flowmap.py` | Maps on-farm field flows (Rust: `N2O`/air, `CH4`/air, fuel `CO2`, water…) to canonical store flow UIDs (CAS+compartment → name). 13/13 resolve. |
| `orchestrator.py` | `FarmLCA(region).assess(on_farm_lci, purchased_inputs)` → total impacts + on-farm/upstream contribution split + input match report. |

## Flow
```
on-farm LCI (Rust) ──flowmap──▶ canonical flows ┐
                                                 ├─▶ merge ─▶ characterize_flows(method) ─▶ impacts
purchased inputs ──match──▶ process ──solve──▶ supply-chain flows ┘         (validated canonical CFs)
```

## Use
```python
from orchestrator import FarmLCA
eng = FarmLCA("CA")                      # Canada → prefers ecoinvent CA + EF 3.1 automatically
r = eng.assess(
    on_farm_lci=[{"substance":"N2O","quantity":0.003,"unit":"kg"}],
    purchased_inputs=[{"name":"NPK fertiliser","amount":0.05,"unit":"kg"}])
r.impacts            # {category: {value, unit}}  (total)
r.contribution       # {"on_farm": {...}, "supply_chain": {...}}
r.input_matches      # what each input matched to (+ ref_unit, location, score)
```

## Status — increments 1 & 2 DONE
Full Option-A path proven end-to-end for Ghana **and** Canada:
- **Rust kernel wired** (`rust_kernel.py`): the Rust engine now serialises its on-farm
  `lci_inventory`; `run_kernel()` invokes the binary and `extract_onfarm_lci()` keeps
  the **direct field emissions** (N2O, indirect N2O/nitrate, on-farm fuel CO2, rice CH4,
  water, land) and **drops upstream production** (fertiliser production, phosphate/potash
  mining) — that comes from the supply-chain solver, so keeping both would double-count.
- `FarmLCA.assess_farm(rust_assessment, purchased_inputs)` = run Rust → combine → characterize.
- **Region-aware grid matching** fixed (region-augmented retrieval): CA farm → CA grid, GH → GH grid.
- **Biogenic vs fossil** CO2/CH4 resolve to distinct store flows (name-first).
- Ghana maize demo (1 kg): Climate 1.54 = field 1.47 + upstream 0.07; land use 1.0 (field).

## Single-score bands (empirically calibrated)

The normalized single score (µPt/kg, in `adapter.single_score`) carries a Low/Moderate/
High band whose cutoffs are **not hardcoded**. `calibrate_bands.py` computes the score
for a benchmark basket of 20 ecoinvent farm-gate crop products through the identical
pipeline and sets the cutoffs at the basket's tertiles; results + provenance are written
to `single_score_bands.json` (currently Low<930, Moderate<1990, High≥1990). So "Moderate"
means "typical among real crops we can measure," not an absolute verdict. Regenerate with
`python -m engine.calibrate_bands`. If the file is absent, the adapter falls back to
indicative 500/1500 and flags the band as uncalibrated.

## ISO 14044 report (deterministic, review-ready)
`iso_report.py` emits a data-backed ISO 14040/14044 report (document control · goal ·
scope · LCI · LCIA · interpretation · critical review · references), structured per CSIR
LCA Guideline 4 and the OCP LCA SOP. Every element comes from the real assessment; the
mandatory statements (functional unit, system boundary, cut-off, the "results are relative
expressions" disclaimer, value-choice flags) are always present. Default posture is
external/public (`intended_for_public=True`), which — per ISO 14044 §6.3 / ISO/TS
14071:2024 — makes an independent critical review by a qualified 3-expert panel MANDATORY.
The generator never conducts that review, so the report is emitted as an ISO-conformant
DRAFT with the critical review marked REQUIRED and PENDING and the review statement left
empty (issued only when a real panel accepts the study). Rendered by
`african-lca-frontend/src/components/ISOReport.tsx`.

### AI plain-language guide (optional second layer)
`app/services/ai_report_generator.py` interprets the ISO draft on demand via
`POST /reports/generate`. It does **not** regenerate ISO sections or invent LCA facts.
See `AI_REPORT_ENHANCEMENTS.md` for report types (`farmer_friendly`, `executive`,
`comprehensive` commentary). Requires `iso_report` in assessment data.

## Remaining refinements
1. **Cross-unit input amounts** (kg diesel vs MJ process): surfaced as a note when
   `amount_unit != ref_unit`; needs substance-specific conversion (e.g. diesel LHV) or
   matcher preference for a ref_unit-compatible process.
2. **Auto-extract purchased inputs** from the assessment (fertiliser type/rate, fuel) so
   the caller doesn't pass them separately.
3. **Final validation** — run the real Rust binary on a full *comprehensive* farm input
   (with `management_practices`) so field emissions are Rust-computed, not illustrative;
   the production app already builds that input format. Rust exposure + invocation +
   extraction are proven; only a hand-built comprehensive JSON was out of scope here.
4. **Retire Rust's LCIA** from the served path once the app routes call this engine.
