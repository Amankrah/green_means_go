# Consequential LCA — design spike checklist

**Status:** Deferred (Tier 3-M5). No production toggle in this release.

This document records when and how attributional inventory from Green Means Go could support **system-expansion consequential** analysis, without committing to implementation.

## Goal

Determine whether the existing farm LCI + supply-chain solver can be extended to answer consequential questions (e.g. “What happens to total GHG if this farm switches fertiliser?”) using marginal/default datasets, rather than building a full consequential engine now.

## Preconditions to evaluate

- [ ] **Functional unit clarity** — consequential comparisons require explicit reference flow and substitution rules; confirm per-kg and per-ha FU blocks are sufficient for researcher exports.
- [ ] **Attributional baseline quality** — `contribution_by_source` and `input_matches` must reliably identify dominant flows before any expansion logic.
- [ ] **Dataset availability** — identify whether background processes in the matcher support marginal/consequential variants (or only average/attributional).
- [ ] **Scenario patch coverage** — current `yield_scale`, `n_rate_scale`, `diesel_scale` patches are attributional; list which patches map to consequential “what-if” questions vs simple parameter sweeps.

## System expansion mapping

For each major purchased input category, document a candidate **avoided burden** or **expanded system**:

| Input / flow | Attributional source today | Candidate expansion product | Data source needed |
|--------------|---------------------------|----------------------------|-------------------|
| Synthetic N fertiliser | Matched ecoinvent process | Grid electricity / other crop margin | TBD |
| Diesel / machinery | Supply-chain solve | Alternative power / reduced tillage margin | TBD |
| Land use (on-farm) | Field LCI + yield | Yield increase on same hectare vs expansion | TBD |
| Compost / organic N | Field emissions model | Avoided synthetic N production | TBD |

## Methodological decisions (before any code)

- [ ] Choose consequential framework reference (ISO 14044 §4.3.4, EPD guidance, or ILCD).
- [ ] Define default **substitution vs system expansion** rule per impact category (GWP vs land).
- [ ] Specify whether results are **opt-in per study** (`study_meta.consequential_mode`?) or a separate assessment type.
- [ ] Agree on reporting: separate `consequential_midpoints` block vs overwriting primary midpoints (recommend separate block).

## Engine touchpoints (if pursued later)

- [ ] `engine/orchestrator.py` — optional second characterization pass with expansion vectors.
- [ ] `engine/adapter.py` — attach `consequential_results` without breaking attributional `midpoint_impacts`.
- [ ] `app/scenarios.py` — distinguish attributional parameter patches from expansion scenarios.
- [ ] `app/research_export.py` — export both attributional and consequential slices with explicit `methodology` labels.
- [ ] Frontend — researcher-only panel; never show consequential numbers without explicit mode label.

## Validation plan

- [ ] Golden case: single-input change (N −20%) attributional vs documented consequential expectation from literature.
- [ ] Regression: attributional results unchanged when consequential mode is off.
- [ ] Peer review gate: align with `review_status` before public share/export of consequential results.

## Out of scope for this spike

- Production API toggle or UI switch
- Automatic marginal dataset selection
- Processing-sector consequential models
- Policy/market equilibrium models

## Next step when prioritized

Run a ½-day workshop with LCA method owner; complete the table above for Ghana maize + cowpea case study; estimate 2–3 sprint effort for a read-only consequential prototype behind `study_meta` flag.
