# LCA Engineer — Data Load Runbook

End-to-end, repeatable sequence to take the LCA Engineer from empty to a working
canonical store with real ecoinvent + Agribalyse data, an AI matcher, and a live
API. Every step has a verification you can copy-paste. Times are rough.

> Source of truth: McGill OneDrive/SharePoint (BREE 505 research share).
> Runtime never touches SharePoint — we fetch a **version-pinned** copy once,
> import via openLCA, and load into the canonical store the engine reads.

```
[0] prereqs ─▶ [1] fetch ─▶ [2] openLCA import ─▶ [3] load store ─▶ [4] verify data
                                                                        │
                                              [5] serve API ◀───────────┘ ─▶ [6] verify API
```

---

## 0 · Prerequisites (once)  ~15 min
```bash
# Python deps (solver + readers + matcher)
pip install -r ingestion/requirements.txt          # Python 3.10: JSON-LD path (olca-schema)
python3.11 -m pip install -r ingestion/requirements.txt   # Python 3.11+: adds olca-ipc for live IPC
```

# rclone (fetch) — Linux
curl https://rclone.org/install.sh | sudo bash      # or: sudo apt install rclone
rclone config                                        # add remote 'mcgill' (type: onedrive, McGill account)
rclone lsd "mcgill:2 - Teaching/BREE 505 - 2026/6 - Tutorials/Database"   # must list folders

# openLCA desktop (free): https://www.openlca.org/download/   (needed once for import/export)

# API keys (optional, enables semantic matching): put in app/.env
#   ANTHROPIC_API_KEY=...   OPENAI_API_KEY=...
```
**Verify:** `rclone version`, `python3 -c "import numpy,scipy,olca_schema"` (no error).
For the optional IPC path (`load-ipc`), also run
`python3.11 -c "import olca_schema, olca_ipc; print('ok')"`.

---

## 1 · Get the databases (version-pinned)  ~5–30 min (network)

**Primary: browser download.** McGill's tenant blocks the rclone OAuth app
(requires admin consent), so the reliable path is the OneDrive **share link** in
a browser — it uses your normal McGill login. Select just the P0 files and
**Download**, then place them where the pipeline expects:
```bash
mkdir -p data/raw/agribalyse_3.2 data/raw/ecoinvent_3.11_cutoff_unit data/raw/_docs
mv ~/Downloads/agribalyse\ 3.2.zolca       data/raw/agribalyse_3.2/
mv ~/Downloads/ecoinvent*Cutoff*Unit*.zolca data/raw/ecoinvent_3.11_cutoff_unit/
mv ~/Downloads/OpenLCA\ Databases.docx     data/raw/_docs/
```
**Verify:** `ls -lh data/raw/*/` shows ~499 MB (Agribalyse) and ~153 MB (ecoinvent) `.zolca`.

> The downloads are openLCA **`.zolca`** (Apache Derby DB backups), NOT JSON-LD —
> they must be restored in openLCA (step 2). `load-jsonld` cannot read a `.zolca`.

> _Optional rclone path (only if your tenant approves the rclone app):_ `rclone config`
> (remote `mcgill`, type onedrive), `rclone lsf mcgill:`, then `python3 ingest.py fetch --only P0`.

---

## 2 · Restore in openLCA, then expose for loading  ~15–40 min (one-time per DB)
`.zolca` = an openLCA (Apache Derby) database backup — it must be restored in
openLCA before the engine can read it. Follow `data/raw/_docs/OpenLCA Databases.docx`.

1. Open **openLCA** → Navigation panel → right-click → **"Restore database…"** →
   select the `.zolca` → double-click the new database to **activate** it.
   Do this for both the ecoinvent and Agribalyse `.zolca` files.
2. Pick **one** load path:

   **Path B — live IPC (recommended, no export):** with a DB active,
   `Tools ▸ Developer tools ▸ IPC server` → port `8080`, leave running. The IPC
   server serves the **currently active** database, so load one DB, switch active
   DB, restart IPC, load the next. **Requires Python >=3.11** (`olca-ipc`).

   **Path A — JSON-LD export (faster for full ecoinvent; works on Python 3.10):**
   `File ▸ Export ▸ JSON-LD` → produces a `.zip` per database.

**Verify:** Path A → the `.zip` exists; Path B → `curl localhost:8080` responds.

---

## 3 · Load into the canonical store  ~2–20 min (DB size dependent)
```bash
cd ingestion
python3.11 -m pip install -r requirements.txt   # Path B needs olca-ipc (Python 3.11+)

# Path B (live openLCA IPC) — activate each DB in openLCA, start IPC, then:
python3.11 ingest.py load-ipc --name ecoinvent  --version "3.11 Cutoff Unit" --port 8080
python3.11 ingest.py load-ipc --name agribalyse --version "3.2"             --port 8080

# Path A (JSON-LD) — point at the zip you EXPORTED from openLCA (NOT the .zolca):
python3 ingest.py load-jsonld "../data/raw/ecoinvent_3.11_cutoff_unit/ecoinvent_jsonld.zip" \
    --name ecoinvent --version "3.11 Cutoff Unit" --license "ecoinvent academic/research (McGill)"
```
Both DBs load into the same store, so Agribalyse→ecoinvent provider links resolve by UID.
**Verify:**
```bash
python3 ingest.py stats     # expect non-zero flows / processes / exchanges / CFs per source
```

---

## 4 · Verify the data (lookups, matcher, solver)  ~2 min
```bash
cd ingestion
# lookup
python3 query.py find "maize"
# AI match (uses OpenAI embeddings + Claude expansion if keys set; else lexical)
python3 matching.py "NPK 15-15-15 50kg" --expand --reindex
# cradle-to-gate on a real process uid (copy a uid from the find/match output)
python3 query.py inventory <PROCESS_UID> --method "ReCiPe" --top 20
```
**Verify:** `inventory` prints a supply-chain process count > 1 and non-zero impacts.

---

## 5 · Serve the API  ~1 min
```bash
cd app
uvicorn main:app --reload --port 8000        # needs anthropic installed (report module)
```

## 6 · Verify the API  ~1 min
```bash
curl -s localhost:8000/inventory/health | python3 -m json.tool
curl -s "localhost:8000/inventory/match?q=local%20maize&expand=true&top=5" | python3 -m json.tool
curl -s "localhost:8000/inventory/cradle-to-gate/<PROCESS_UID>?method=ReCiPe&top=20" | python3 -m json.tool
curl -s -X POST localhost:8000/inventory/reindex            # rebuild matcher index after a new load
```
**Verify:** `/inventory/health` → `status: ok` with non-zero counts.

---

## Validation gate — ✅ PASSED against TWO independent references

**Reference 1 — ecoinvent → openLCA** (2026-06-02)
- Product: ecoinvent 3.11 Cutoff Unit, `maize grain production … Cutoff, U` (AU-VIC,
  uid `d821b9ce-7106-3ec9-b6c9-3a2e6e0969ff`), 1 kg, method `ReCiPe 2016 v1.03, midpoint (H)`.
- **All 18 categories agree, worst 0.45% (rounding in openLCA's displayed values).**

**Reference 2 — Agribalyse → ADEME's OFFICIAL published EF 3.1 results** (2026-07-15)
- Product: Agribalyse 3.2, `Maize grain, conventional, 28% moisture, national average,
  animal feed, at farm gate {FR} U` (uid `df3618ff-5c9a-3abf-a3ee-1afed0bf3910`), 1 kg,
  method `EF v3.1`; reference = `data/AGRIBALYSE3.2/…partie agriculture_conv…xlsx`.
- **11 of 12 categories within 5%** of ADEME's published values (climate, land use
  exact, ionising radiation, ozone, photochem, acidification, freshwater + marine
  eutrophication, energy resources +3.2%, mineral resources +1.4%, particulate −2%).
- Known residual: **ecotoxicity +15%.** The authoritative FEDEFL layer (below) gives
  the SAME ecotox result as the heuristic — proving it is NOT a nomenclature/matching
  problem but a **supply-chain reconstruction difference**: our deterministic flow-linked
  system characterizes ~15% more freshwater ecotoxicity than ADEME's exact product
  systems. Inherent to rebuilding from a flat process list; only bites the most
  trace-sensitive category. Not double-counting (verified: no duplicate pesticide flows).
- Water use excluded from bridging (AWARE is flow-instance specific — shows a gap, not a
  wrong number).

### Authoritative FEDEFL normalization (glad_fetch.py + glad_load.py)
The heuristic name/CAS bridge is backstopped by the official GLAD/FEDEFL "one list":
- `glad_fetch.py` downloads the GLAD mapped files (`ecoinventEFv3.7→FEDEFL`,
  `ILCD-EFv3.0→FEDEFL`) via the GitHub **LFS batch API** (the on-disk `.xlsx` are LFS
  stubs; the repo is a ZIP extract with no git). Public Apache-2.0 data.
- `glad_load.py` assigns every flow a canonical **`fed_id = flowable|compartment`**,
  resolved by (1) mapped-file source-name, (2) CAS, (3) FEDEFL synonym → **86% of flows**.
  Curated `NO_FLOW_MATCH` entries (e.g. biogenic `Carbon dioxide, in air`) get a
  `__NOMAP__` sentinel and are never bridged — replacing our heuristic CO2 special-case
  with authoritative data.
- The solver's top match tier is `fed_id` (fine→medium), then the heuristic tiers for the
  14% FEDEFL didn't resolve. Run once after loading databases: `python3 ingest.py glad`.
- Version caveat: GLAD maps ecoinvent 3.7 / EF 3.0; we run 3.11 / EF 3.1 — so resolution
  is by name+CAS+context, not raw UUID (UUID overlap is only ~6%).

### Bridge tiers (query.py::_characterize)
Match a CF to an inventory flow in this order, each guarded by method-known + unique-value:
`exact UID → name|fine-compartment → CAS|fine-compartment (substance cats) → name|medium-compartment`.
Fine = medium + canonical sub-compartment (`emission/soil/agricultural`), with synonyms
normalised (`river`→surface, `long-term` stripped) so inventory and CF lists align. Fine
serves sub-compartment-specific CFs (ecotox, PM); the name→medium fallback serves coarse
CFs (eutrophication: P-to-any-water = 1.0). CAS is fine-only (CAS+medium over-counts).
Backfill after loading: `python3.11 ingest.py flowkeys`.

### Flow-nomenclature bridge (why Agribalyse needed more than ecoinvent)
The same substance appears under different flow UIDs across/within databases, and a
method's CFs are keyed to only some. `flowkey.py` computes a canonical
`name|compartment` signature; `_characterize()` matches a CF to an inventory flow by
exact UID first, then by that key. Guards that keep it correct:
- **two tiers:** `name|compartment` first, then `CAS|compartment` for substance-identity
  categories only (allow-listed: NOT climate, NOT water). CAS rescues same-substance
  flows whose NAMES differ across nomenclatures ("BENFURACARB"/"Benfuracarb", "Gas,
  natural") — it fixed energy (−38%→+3%) and minerals (−57%→+1%).
- **name-based tier first** (not CAS): "Carbon dioxide, fossil" (CF 1.0) stays separate
  from "…non-fossil" (biogenic, CF 0) — CAS+compartment alone would merge them, which is
  why the CAS tier is excluded from climate.
- **method-known guard:** never bridge a flow whose UID the method already knows in
  ANY category (its omission here is a deliberate CF=0). This keeps ecoinvent exact.
- **unique-value guard:** only bridge when all CFs sharing a key agree.
- **water categories excluded:** AWARE water-use CFs are net-consumption, flow-instance
  specific — bridging over-counts.
Backfill after loading a database: `python3.11 ingest.py flowkeys`.

Three bugs were found and fixed by this gate — re-run it after ANY change to
`query.py::cradle_to_gate`:

1. **Waste-treatment traversal.** ecoinvent links landfills/tailings via *output*
   exchanges with a default provider. Following inputs only dropped every treatment
   activity → toxicity / ionising radiation / freshwater eutrophication ~95% LOW,
   while climate and land use looked perfectly fine. `_reachable()` now follows all
   provider-linked technosphere exchanges (supply chain 13,491 → 17,182 processes).
2. **Elementary-flow signs.** Inputs must NOT be negated: openLCA encodes direction
   in the flow itself and signs its CFs to match. Negating flipped resource and
   land-use impacts negative.
3. **Method name ambiguity.** `find_method()` used a bare `LIKE`, so
   "…midpoint (H)" silently matched "…midpoint (H) **no LT**" (long-term emissions
   excluded). It now prefers an exact match, then the shortest containing name.

### Re-running the gate
```bash
# openLCA: open the process -> Direct calculation -> pick the SAME method -> 1 kg
python3 query.py inventory <uid> --method "ReCiPe 2016 v1.03, midpoint (H)" --top 20
```
Compare category by category. A *uniform* offset points at allocation/system model;
*one bad category* points at a CF direction; *a cluster of long-term-dominated
categories* points at supply-chain traversal (bug 1 above).

This is the ISO-spirit critical-review step from `docs/lca_engineer/DEVELOPER_GUIDE.md §9`.

---

## Reproducibility & re-runs
- **Pin versions.** The `--version` you pass at load time is stored in `sources`;
  keep it exact (e.g. `3.11 Cutoff Unit`). Bump it only when you re-fetch a newer DB.
- **Re-load a source:** loaders use `INSERT OR REPLACE` on flows/processes by UID, so
  re-running `load-*` for the same source refreshes it. To start clean, delete
  `data/canonical/lca_engineer.sqlite*` and reload.
- **Matcher index** caches to `data/canonical/proc_emb_*.npz`; it auto-rebuilds when
  the process count changes, or force with `--reindex` / `POST /inventory/reindex`.
- **Provenance:** every result traces via `import_runs` (when, from what file, counts).

## Troubleshooting
| Symptom | Fix |
|---|---|
| `/inventory/*` → 503 "not built" | Store empty — run steps 1–3. |
| `rclone` lists nothing | Re-run `rclone config`; check the remote name (`--remote`) and the path in `manifest.json`. |
| `ZipReader has no read_each` | `pip install -U olca-schema` (needs v2). |
| `No module named 'olca_schema.results'` | Broken `olca-ipc` alpha on Python 3.10 — run `pip uninstall olca-ipc`, reinstall requirements, use JSON-LD (`load-jsonld`) or upgrade to Python 3.11+ for `load-ipc`. |
| Loader runs but 0 processes | Wrong export type — re-export as **JSON-LD** (not CSV/EcoSpold) from openLCA. |
| Matcher uses lexical despite keys | `pip install openai` + confirm `OPENAI_API_KEY` in `app/.env`. |
| Impacts look wrong by a sign/factor | Run the Validation gate above. |

## Licensing reminder
ecoinvent is **licensed** — kept here for **McGill research** computation only.
Don't redistribute raw datasets or expose them via a public API; aggregated impact
results are fine. See `docs/lca_engineer/DATABASE_PLAN.md §5`.
