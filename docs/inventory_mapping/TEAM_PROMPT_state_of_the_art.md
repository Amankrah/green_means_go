# Team brief: bring the Green Means Go LCA engine to expert grade

You are the lead of a team of agents working in the repository at
`C:\Users\Windows\Desktop\Dev_Projects\green_means_go` (branch `main`). Use the
Agent tool to form a team, one agent per workstream below, and run them in
parallel where the workstreams do not touch the same files. You own integration,
testing and the final report. Do not ask the user questions mid-task; make the
call an experienced LCA practitioner would make, state the assumption in your
report, and keep going.

## Ground truth you start from

Read these first. They were produced by executing the real engine and were
independently validated against the code at commit 45ad6b6:

- `docs/inventory_mapping/GMG_inventory_mapping_summary.json` (executive summary,
  per-commodity verdicts, quick input-to-dataset tables, list of defects)
- `docs/inventory_mapping/GMG_inventory_database_mapping.json` (every parameter
  with file:line citation, all matcher rows by region)
- `engine/README.md`, `docs/lca_engineer/RUST_WIRING_PLAN.md`

Architecture in one line: Rust kernel (`african_lca_backend/src`) computes
on-farm elementary flows; Python engine (`engine/`) matches purchased inputs to
background datasets in `data/canonical/lca_engineer.sqlite` (AGRIBALYSE 3.2 +
ecoinvent 3.11, 45,852 processes) by embedding similarity, solves, and
characterises with the ecoinvent 3.11 method pack; FastAPI app (`app/`) and the
Next.js wizard (`african-lca-frontend/`) sit on top. Regions today: GH, NG, CA.
Regions required at the end: GH, NG, SN (Senegal), BF (Burkina Faso),
ZA (South Africa), CA.

## The goal

A reviewer applying ISO 14040/14044 and the IPCC 2019 Refinement should find
nothing in this engine they would do differently for a cradle-to-gate crop and
processing LCA in West Africa. Every user input that the wizard collects must
either change the result or be removed from the wizard. Every dataset on disk
must either be ingested and used or be documented as intentionally unused.

## Workstreams

### 1. Foreground model gaps (Rust kernel + `engine/field_model.py`)

- Add IPCC 2019 Tier 1 N2O from crop residues (above and below ground residue
  N, Table 11.1A factors) with per-crop residue ratios and N contents for at
  least: maize, groundnut, cowpea, rice, cassava, tomato, pepper, eggplant,
  cucumber, cocoa, oil palm. Cite the table for each value in code.
- Model biological N fixation for legumes (groundnut) on the crop itself, not
  only as a credit to an intercrop partner.
- Perennials (cocoa, oil palm): establishment phase amortised over the
  productive lifetime, land occupation as permanent crop, and land-use-change
  carbon using the IPCC stock-change factors already on disk at
  `engine/recommend/reference/ipcc_stock_change_factors_gh.json` (currently
  unread). Follow the PAS 2050-1 / IPCC Vol 4 Ch 5 20-year amortisation.
- Fertiliser N content: replace the 10% fallback for unknown types with an
  explicit lookup (SSP and MOP contain no N; AS 0.21; CAN 0.27; organic by
  declared N or IPCC manure defaults). Unknown types must raise a validation
  warning, not silently get 10% N.
- Fuels: add LPG, firewood and charcoal combustion paths (ecoinvent has heat
  from wood/charcoal datasets; IPCC 2006 Vol 2 Table 2.5 for direct
  combustion). Fix the kerosene unit mismatch (MJ sent against a per-kg
  dataset). Any unit mismatch between an amount and its matched dataset must
  convert or fail, never pass through.
- Honey: either implement an apiculture inventory (hive materials, sugar feed,
  smoker fuel, extraction energy, transport; WFLDB honey datasets in the store
  as reference) or make the API reject honey with a clear message. Do not let
  it run as a field crop.

### 2. User inputs that are collected but ignored

Confirm each one by reading the wizard payload builder
(`african-lca-frontend/src/lib/api.ts`), the pydantic models in `app/`, and
`engine/inputs.py` / `engine/process_inputs.py`. Then wire it or remove it.

Farm wizard, currently dropped or unused:
- `pesticides_used` (frontend) vs `pesticides` (API model): pydantic silently
  discards the key, so no pesticide burden is ever counted. Fix the contract
  and add a schema test that fails on unknown keys (`extra="forbid"`).
- Seeds / planting material, irrigation water as a purchased input, LPG fuel,
  `energy_sources` (diesel generator, solar, biogas, firewood, charcoal),
  equipment `power_source` (electric, solar, manual, animal) with
  `fuel_efficiency` and `hours_per_year`, packaging, transport of inputs and
  to gate, ammonium sulfate and CAN, farm-made compost and manure sources.
- `food.category` has no numerical effect in the validated path.

Processing request, currently ignored by the Python engine:
`facility_type`, `product_type`, `processing_capacity`,
`operational_hours_per_day`, `location_type`, `primary_energy_source`,
`secondary_energy_sources`, `backup_generator`, `energy_efficiency_measures`,
`water_source`, `water_treatment`, `water_conservation_measures`,
`wastewater_treatment`, `organic_waste_percentage`, `recycling_programs`,
`byproduct_utilization`, `local_sourcing_percentage`,
`supplier_sustainability_practices`, `storage_practices`,
`equipment_efficiency.*`, `processing_steps[].duration / yield_efficiency /
emissions_factor`, `raw_material_inputs[].source_location /
quality_requirements`, `packaging.recyclable`, `quality_grade`,
`market_destination`. Add per-commodity default conversion ratios where the
user leaves them blank (FFB to CPO oil extraction rate, cocoa bean to nib,
maize milling extraction), each with a cited source.

Only one fuel stream can be entered for a facility today; allow several.

### 3. Data on disk that is never read

Ingest into the canonical store (`ingestion/`) with provenance rows, or
document why not:
- `data/AWARE2.0/*.xlsx`: water scarcity CFs by country. `regions.aware_country`
  exists but is never consumed and irrigation water currently characterises to
  zero. Wire AWARE 2.0 as the water-scarcity indicator for every region
  (GH, NG, SN, BF, ZA, CA). This matters most for Senegal, Burkina Faso and
  South Africa, where irrigation water is scarce and the indicator will move
  results.
- `data/USEtox_2.14/`: ecotoxicity and human toxicity CFs, needed once
  pesticides are counted.
- `data/LANCA/`: land-use soil quality CFs (EF 3.1 land use indicator).
- `data/IPCC GWP/Global-Warming-Potential-Values (August 2024).pdf`: AR6
  GWP100 values. Decide one GWP basis per method and make the reports state
  it; today ReCiPe uses AR5 (298 for N2O) and EF 3.1 uses AR6 (273).
- `data/ReCipe2016/` and `data/EVvinronmental_Footprint_EF3.1/` spreadsheets:
  reconcile against the ecoinvent method pack in the store; the normalisation
  factors in `engine/adapter.py` are hand-transcribed and should load from the
  file.
- `data/References_C/` (GLAD, Federal LCA Commons flow lists, ILCD): use for
  elementary-flow mapping QA in `engine/flowmap.py`.
- `data/recommendations/Tier1`, `Tier2`, `engine/case_studies/*.json`: confirm
  each is loaded by a code path or a test.
- Ghana-only tables (`ghana_farm_activity_defaults.json`, `ghana_grid_ef.json`,
  yield guides): produce Nigeria equivalents with sources, and calibrate the
  Nigeria grid factor the way Ghana's is. Senegal, Burkina Faso and South
  Africa equivalents are covered in workstream 3b.

### 3b. New regions: Senegal, Burkina Faso, South Africa

`engine/regions.py` is a data-driven registry; adding a region is adding an
entry, but an entry is only as good as its data. For each of SN, BF and ZA
deliver, with a cited source per value:

- Registry entry: ISO code, location preference list for the matcher
  (country, then West Africa `WA` or Southern Africa, then `RAF`, `RoW`,
  `GLO`), AWARE country key, IPCC climate zone and disaggregated EF1
  (Senegal and Burkina Faso are largely dry tropical, so EF1 0.005 under
  IPCC 2019 Table 11.1 for dry climates, not the 0.016 wet value used for
  Ghana; South Africa varies by province, pick and document one default and
  allow override), FracGASF, FracLEACH where climate-dependent, default LCIA
  method (ReCiPe 2016 midpoint (H), same as GH and NG), currency (XOF, XOF,
  ZAR).
- Grid: confirm which electricity datasets the store holds for each country
  (ecoinvent 3.11 has ZA; check SN and BF, which may fall to a West Africa or
  RAF market) and the official national grid factor to calibrate to, the way
  Ghana is calibrated to the Energy Commission figure. Sources to try: the
  national utility or regulator (SENELEC, SONABEL, Eskom), the IEA, and the
  UNFCCC CDM grid factor tool. If no official figure exists, say so and use the
  dataset uncalibrated.
- Activity defaults, yield guides and price feeds equivalent to the Ghana
  tables (`ghana_farm_activity_defaults.json`, `ghana_grid_ef.json`, MoFA
  yield guides, SRID price CSV): build Senegal, Burkina Faso and South Africa
  versions from ANSD/DAPSA, INSD/DGESS and DALRRD/Stats SA statistics, or
  FAOSTAT where national figures are missing. Mark every value with its
  pedigree so the Monte Carlo uncertainty reflects data quality.
- Frontend: region picker, common-crops-by-region lists (Senegal: groundnut,
  millet, rice, tomato, onion; Burkina Faso: cotton, maize, sorghum, sesame,
  tomato; South Africa: maize, sugarcane, citrus, grapes, deciduous fruit),
  currency and unit display.
- Recommendation measures: the Ghana measure set is COCOBOD and CSAIP based;
  add at least a starter set per new country from national climate-smart
  agriculture plans, each with a licence that permits non-commercial reuse.
- Case study per new region under `engine/case_studies/` (suggested: Senegal
  groundnut rainfed, Burkina Faso maize with compost, South Africa irrigated
  maize), run end to end, with results in the final report.

Do not let a new region silently inherit Ghana values. Any field left at the
Ghana number must be flagged as such in the registry and in the ISO report's
data-quality section.

### 4. Matching quality

The matcher ranks by region preference before similarity, so an unknown raw
material in Ghana resolves to the Ghana cocoa dataset. Fix it so a candidate
must pass a product-identity check before region preference applies. Make the
CA electricity match deterministic (`regions.location_rank` treats "Canada"
and "Canada, Ontario" as equal). Remove the dead fallback chains in
`engine/process_inputs.py` and `engine/orchestrator.py` or make them live.
Add a regression test that runs the matcher for every input name in
`GMG_inventory_database_mapping.json` and fails on any change in matched
process.

### 5. Intelligence layer

An Anthropic API key is in `app/.env` as `ANTHROPIC_API_KEY`. Never print it,
log it, commit it, or copy it anywhere. Load the `claude-api` skill before
writing any client code and use the current model ids from it. Use the model
only where judgment is needed and a deterministic rule is not enough:

- Free-text classification: map a user's crop, fertiliser, fuel, raw-material
  or packaging text to the controlled vocabulary, with a confidence and a
  "needs user confirmation" flag below a threshold. Cache results by
  normalised string.
- Candidate adjudication: when the embedding matcher's top candidates are
  close or cross product families, have the model pick, with the dataset
  names and the user's context as evidence, and record the rationale in the
  input match report.
- Plain-language and ISO report narrative (already partly present in
  `app/services/ai_report_generator.py`).

The model must never invent an emission factor, characterisation factor, yield
or dataset. Every number in a result must trace to the store, to a cited
constant in code, or to the user. Make that a test.

## Guardrails

- This is a free, non-commercial tool. Keep CC-BY-NC and IPCC sources in scope.
- Do not use the em-dash character (Unicode U+2014) anywhere in code, docs
  or messages. Use a comma, a colon or a new sentence instead.
- No file in `audits/` is to be touched or read; it is confidential.
- Keep the canonical path single: Rust for on-farm flows, Python for
  supply-chain and characterisation. Do not resurrect the legacy Rust LCIA.
- Every new factor carries a source string and a file:line-checkable
  citation. Every new behaviour gets a test under `engine/test_*.py` or the
  Rust test suite. Run the full test suite and the three case studies in
  `engine/case_studies/` before and after; report the deltas per impact
  category and explain each one.
- Regenerate `docs/inventory_mapping/*.json` with the same executed-matcher
  method when you are done so the PM's mapping stays true.
- Work on a branch, commit in small reviewed steps, do not push until the
  final report is written. Commit messages end with
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Deliverable

A final report at `docs/inventory_mapping/STATE_OF_THE_ART_REPORT.md` with:
what changed per workstream, what was left out and why, the before/after
case-study impact table, the list of inputs now live versus removed, the list
of datasets now ingested versus documented as unused, and the open items a
human LCA reviewer still has to decide (allocation choices, GWP basis, cut-off
rules). Then stop and hand back.
