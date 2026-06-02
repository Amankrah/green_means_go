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
pip install -r ingestion/requirements.txt

# rclone (fetch) — Linux
curl https://rclone.org/install.sh | sudo bash      # or: sudo apt install rclone
rclone config                                        # add remote 'mcgill' (type: onedrive, McGill account)
rclone lsd "mcgill:2 - Teaching/BREE 505 - 2026/6 - Tutorials/Database"   # must list folders

# openLCA desktop (free): https://www.openlca.org/download/   (needed once for import/export)

# API keys (optional, enables semantic matching): put in app/.env
#   ANTHROPIC_API_KEY=...   OPENAI_API_KEY=...
```
**Verify:** `rclone version`, `python3 -c "import numpy,scipy,olca_schema"` (no error).

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
   DB, restart IPC, load the next.

   **Path A — JSON-LD export (faster for full ecoinvent):**
   `File ▸ Export ▸ JSON-LD` → produces a `.zip` per database.

**Verify:** Path A → the `.zip` exists; Path B → `curl localhost:8080` responds.

---

## 3 · Load into the canonical store  ~2–20 min (DB size dependent)
```bash
cd ingestion
pip install -r requirements.txt   # ensure olca-schema (+ olca-ipc for Path B) are installed

# Path B (live openLCA IPC) — activate each DB in openLCA, start IPC, then:
python3 ingest.py load-ipc --name ecoinvent  --version "3.11 Cutoff Unit" --port 8080
python3 ingest.py load-ipc --name agribalyse --version "3.2"             --port 8080

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

## Validation gate (do before trusting absolute numbers)
The inventory (elementary-flow) math is proven (`test_query.py`), but **characterized
impact signs/units depend on each method's flow directions**. Before reporting
absolutes:
1. Pick 2–3 reference products (e.g. `market for maize grain`, electricity mix).
2. Compute the same impacts **in openLCA** (same method, same system model).
3. Compare to `query.py inventory`. They should agree within rounding.
4. If a category is off by a sign/factor, adjust the sign convention in
   `query.py::cradle_to_gate` (documented in its header) and re-verify.

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
| Loader runs but 0 processes | Wrong export type — re-export as **JSON-LD** (not CSV/EcoSpold) from openLCA. |
| Matcher uses lexical despite keys | `pip install openai` + confirm `OPENAI_API_KEY` in `app/.env`. |
| Impacts look wrong by a sign/factor | Run the Validation gate above. |

## Licensing reminder
ecoinvent is **licensed** — kept here for **McGill research** computation only.
Don't redistribute raw datasets or expose them via a public API; aggregated impact
results are fine. See `docs/lca_engineer/DATABASE_PLAN.md §5`.
