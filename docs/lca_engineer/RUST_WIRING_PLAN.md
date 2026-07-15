# Rust ↔ Python Wiring Plan (Option A) + Multi-Region

> **Decision (locked):** Rust = **LCI kernel** (on-farm field emissions, IPCC AFOLU);
> Python = **supply-chain LCI + characterization** via the validated canonical store.
> One validated impact path (openLCA 18/18, ADEME 11/12). Region is **data-driven** so
> Canada (and beyond) is a registry entry, not a code fork.

## Target architecture

```
 user farm/facility data
        │
        ▼
 ┌─────────────────────┐        ┌────────────────────────────────────────────┐
 │ Rust LCI kernel      │        │ Python orchestrator (engine/)               │
 │ IPCC AFOLU field      │  LCI   │ 1. map on-farm flows → canonical store flows │
 │ emissions:            │──────▶│ 2. per purchased input: match → solve        │
 │  N2O, CH4(rice/ente-  │ (bio-  │    cradle-to-gate supply-chain LCI           │
 │  ric/manure), fuel CO2│ sphere │ 3. merge on-farm + supply-chain elementary   │
 │  region-parameterized │ flows) │ 4. characterize ALL via canonical CFs        │
 └─────────────────────┘        │    (ReCiPe / EF, FEDEFL-normalised)          │
                                 │ 5. midpoint + contribution (on-farm/upstream)│
                                 └────────────────────────────────────────────┘
                                                    │
                                          region registry (Ghana/Nigeria/Canada):
                                          grid dataset · AWARE CF · IPCC tier · currency
```

**Why Option A:** the Python characterization is validated against two references;
duplicating it in Rust (or keeping Rust's hardcoded LCIA) would create a second,
unvalidated impact path. Rust keeps its strength — fast, deterministic ISO field-
emission arithmetic — and simply hands Python the biosphere flows.

## Region abstraction (Canada-ready from day one)
Replace the Rust `enum Country { Ghana, Nigeria }` with a **registry** keyed by region
code. Each entry carries the data the pipeline needs to regionalise:

| field | Ghana | Nigeria | Canada |
|-------|-------|---------|--------|
| grid electricity dataset (canonical store) | GH mix | NG mix | CA mix (ecoinvent CA) |
| AWARE water CF | Ghana | Nigeria N/S | Canada (basin) |
| IPCC climate zone / tier params | wet tropical | wet/dry tropical | cool temperate |
| default LCIA method | ReCiPe H (or EF) | ReCiPe H | EF 3.1 / ReCiPe H |
| currency | GHS | NGN | CAD |

Canada = ecoinvent `CA` background processes + temperate IPCC factors + Canadian grid,
selected via the registry — no new code paths.

## On-farm flow mapping (the one seam that needs curation)
Rust emits field flows with its own names (`N2O` / air, `CH4` / air, `CO2` / air …).
To characterize them with canonical CFs they map to a representative **store flow**
(by name/CAS + compartment). Small curated table (~15 flows): N₂O, CH₄ (fossil vs
biogenic), CO₂ fossil, NH₃, NOₓ, NO₃⁻/PO₄³⁻ to water, P, SO₂, PM2.5, occupation/land.
Once mapped to a store UID, on-farm flows characterize through the exact same validated
path as supply-chain flows.

## Status: increments 1–4 DONE ✅
- Rust exposes `lci_inventory` (LciFlow) ✓ · region registry (GH/NG/CA) ✓ · orchestrator
  + validated characterization ✓ · region-aware grid matching ✓ · `rust_kernel.py` wires
  the real binary (keeps direct field emissions, drops upstream to avoid double-count) ✓
- **End-to-end verified with the real Rust binary**: Ghana maize (1 ha, 100 kg urea/ha) →
  Climate **0.263 kg CO₂-eq/kg** (field 0.103 from IPCC N₂O 0.723 kg — exact — + upstream
  0.159), land use 4.0 m²a/kg — both in the literature range.
- **App route migrated**: `POST /farm/assess` (+ `GET /farm/regions`) runs the new engine;
  the old Rust-LCIA `/assess` route stays until the frontend switches.
- Remaining: cross-unit input conversion, auto-extract purchased inputs from the
  assessment, retire Rust's LCIA from the served path.

## Increments (original plan)
1. **(done) Python orchestrator + region registry** — combine an on-farm LCI
   (canonical elementary flows) + supply-chain LCI (matcher→solver) + canonical
   characterization → results + on-farm/upstream contribution split. Tested with
   synthetic on-farm data (not blocked on the Rust rebuild). Regions incl. Canada.
2. **Rust: expose the LCI inventory** — add the computed `InventoryItem` list
   (substance, quantity, unit, compartment, source) to the Rust output JSON; make the
   `Country` handling data-driven (accept an arbitrary region code + params). `cargo build`.
3. **Wire Rust → orchestrator** — flowmap Rust output → canonical; drop Rust's LCIA from
   the served path (keep as offline fallback/sanity check).
4. **Validate end-to-end** — a Ghana farm and a Canada farm; sanity-check magnitudes and
   the on-farm/upstream split against literature (Poore&Nemecek ranges, national inventories).

## Non-goals (now)
- Reimplementing the solver in Rust. - Ripping out Rust's LCIA before the served path is
migrated. - Full Canadian primary-data collection (registry + ecoinvent CA suffices to start).
