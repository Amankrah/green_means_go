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
