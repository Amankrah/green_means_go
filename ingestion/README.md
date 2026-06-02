# LCA Engineer — Ingestion Pipeline

Pulls the background LCA databases from the McGill OneDrive/SharePoint research
share, then loads ecoinvent / Agribalyse / LCIA methods into a **canonical store**
the engine can query. SharePoint stays the source of truth; we keep a
version-pinned local copy for reproducible research.

```
SharePoint  ──fetch (rclone)──▶  data/raw/  ──openLCA import──▶  JSON-LD zip  ──load──▶  canonical store
                                                            └──▶  live IPC ────load──▶  (SQLite: data/canonical/lca_engineer.sqlite)
            engine reads ONLY the canonical store — never SharePoint at runtime.
```

## Files
| File | Role |
|------|------|
| `manifest.json` | Which files to fetch from the share (edit paths/filenames here) |
| `fetch_data.py` | rclone-based fetcher (resumable, headless, handles multi-GB files) |
| `canonical_store.py` | SQLite canonical store + DAO (schema mirrors `LITERATURE_EXTRACTION.md`) |
| `olca_common.py` | Defensive olca-schema → canonical-row mappers (shared by both readers) |
| `jsonld_reader.py` | Load an openLCA **JSON-LD zip** (primary, headless path) |
| `ipc_reader.py` | Load a **live openLCA** database via IPC (convenient path) |
| `ingest.py` | One CLI over all of the above |
| `query.py` | Read API: lookups (no deps) + **cradle-to-gate inventory solver** (`T s = f`, `g = B s`; needs numpy/scipy) |
| `test_query.py` | Proves the solver on a synthetic looped system with a known analytical answer |
| `requirements.txt` | `olca-schema`, `olca-ipc`, `numpy`, `scipy` (+ system `rclone`) |

## Setup
```bash
pip install -r ingestion/requirements.txt
# system tool:
curl https://rclone.org/install.sh | sudo bash        # or: sudo apt install rclone
rclone config                                          # add remote 'mcgill', type onedrive (McGill account)
rclone lsd "mcgill:2 - Teaching/BREE 505 - 2026/6 - Tutorials/Database"   # verify access
```

## Step 1 — Fetch (scripted, version-pinned)
```bash
cd ingestion
python3 ingest.py fetch --only P0          # essentials: Agribalyse, ecoinvent Cutoff Unit, the docx
python3 fetch_data.py --list-remote        # see exact filenames on the share...
#   ...then update the truncated 'remote' fields in manifest.json to the exact names.
python3 fetch_data.py --mount              # alternative: mount on-demand instead of downloading
```
Files land in `data/raw/<target>/`; a `data/raw/_fetch_log.json` records provenance.

> **Why not query SharePoint directly at runtime?** ecoinvent/Agribalyse aren't
> live-queryable blobs — the whole database must be parsed/imported once. So we
> fetch+cache a pinned copy, then read from the canonical store. The runtime
> engine never depends on the cloud share.

## Step 2 — Import into openLCA (one-time, per database)
`.zolca` files and EcoSpold packages need openLCA once:
1. Open **openLCA** (free desktop) → import the `.zolca` (Agribalyse) / ecoinvent package
   (follow `data/raw/_docs/OpenLCA Databases.docx`).
2. Then pick **one** load path below.

**Path A — export JSON-LD (best for big/headless, reproducible):**
openLCA → `File ▸ Export ▸ JSON-LD` → a `.zip`.

**Path B — live IPC (convenient, no export):**
openLCA → `Tools ▸ Developer tools ▸ IPC server` → port `8080`, leave running.

## Step 3 — Load into the canonical store
```bash
# Path A (JSON-LD zip):
python3 ingest.py load-jsonld data/raw/ecoinvent_3.11_cutoff_unit/ecoinvent.zip \
    --name ecoinvent --version "3.11 Cutoff Unit" --license "ecoinvent academic/research (McGill)"

python3 ingest.py load-jsonld data/raw/agribalyse_3.2/agribalyse.zip \
    --name agribalyse --version 3.2 --license "ETALAB open + ecoinvent-derived parts"

# Path B (live openLCA IPC):
python3 ingest.py load-ipc --name ecoinvent --version "3.11 Cutoff" --port 8080

# inspect:
python3 ingest.py stats
```

## What lands in the store
- `flows` — elementary + product/waste flows (with category, type)
- `processes` + `exchanges` — the technosphere/biosphere matrix (upstream supply chain)
- `impact_methods` / `impact_categories` / `characterization_factors` — LCIA CFs
- `sources` + `import_runs` — provenance (which DB version, when, from what, counts)

The Rust engine (and AI matching/RAG subsystems) read from this store. See
`docs/lca_engineer/DATABASE_PLAN.md §3` for the full architecture and the
PostgreSQL migration path.

## Licensing reminder
ecoinvent is **licensed**. This pipeline keeps it for **internal computation only**
under McGill **research** use — do not redistribute raw datasets or expose them
through a public API. Aggregated impact results are fine. Before any commercial
use, obtain a proper ecoinvent license (free LMIC academic license via a
Ghana/Nigeria partner, or a commercial seat). See `DATABASE_PLAN.md §5`.
