"""
Inventory & matching API — exposes the LCA Engineer canonical store and the
cradle-to-gate solver over HTTP, and the AI matching subsystem.

Reads ONLY from the canonical store (data/canonical/lca_engineer.sqlite), which
is populated by the ingestion pipeline (../../ingestion). The runtime never
touches SharePoint. If the store hasn't been built yet, endpoints return 503
with guidance instead of crashing.

Endpoints (prefix /inventory):
    GET /inventory/health                         store status + counts
    GET /inventory/processes?q=&limit=            lookup processes by name
    GET /inventory/methods                        list LCIA methods
    GET /inventory/process/{uid}/exchanges        a process's exchanges
    GET /inventory/cradle-to-gate/{uid}?method=&top=   solve the supply chain
    GET /inventory/match?q=&top=&expand=          AI: free-text -> candidate processes
    POST /inventory/reindex                        rebuild the matcher embedding index
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

# make the ingestion package importable
_ING = Path(__file__).resolve().parents[2] / "ingestion"
if str(_ING) not in sys.path:
    sys.path.insert(0, str(_ING))

from canonical_store import DEFAULT_DB          # noqa: E402
from query import CanonicalQuery                # noqa: E402
from matching import ProcessMatcher             # noqa: E402

router = APIRouter(prefix="/inventory", tags=["inventory"])

_matcher: ProcessMatcher | None = None


def _store_ready() -> bool:
    if not Path(DEFAULT_DB).exists():
        return False
    try:
        con = sqlite3.connect(str(DEFAULT_DB))
        n = con.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='processes'"
        ).fetchone()[0]
        con.close()
        return n == 1
    except sqlite3.Error:
        return False


def _require_store() -> None:
    if not _store_ready():
        raise HTTPException(
            status_code=503,
            detail="Canonical store not built yet. Run the ingestion pipeline "
                   "(see ingestion/README.md): fetch -> import to openLCA -> load.",
        )


def _q() -> CanonicalQuery:
    # fresh connection per request (sqlite connections are not thread-safe)
    return CanonicalQuery(DEFAULT_DB)


def get_matcher() -> ProcessMatcher:
    global _matcher
    if _matcher is None:
        m = ProcessMatcher(_q())
        m.build_index()
        _matcher = m
    return _matcher


@router.get("/health")
async def health():
    if not _store_ready():
        return {"status": "not_built", "message": "Run the ingestion pipeline to populate the store."}
    q = _q()
    try:
        from canonical_store import CanonicalStore
        with CanonicalStore(DEFAULT_DB) as store:
            return {"status": "ok", **store.stats()}
    finally:
        q.close()


@router.get("/processes")
async def processes(q: str = Query(..., min_length=1), limit: int = 20):
    _require_store()
    conn = _q()
    try:
        return conn.find_processes(q, limit)
    finally:
        conn.close()


@router.get("/methods")
async def methods():
    _require_store()
    conn = _q()
    try:
        return conn.list_methods()
    finally:
        conn.close()


@router.get("/process/{uid}/exchanges")
async def exchanges(uid: str):
    _require_store()
    conn = _q()
    try:
        p = conn.get_process(uid)
        if not p:
            raise HTTPException(404, f"process not found: {uid}")
        return {"process": p, "exchanges": conn.get_exchanges(uid)}
    finally:
        conn.close()


@router.get("/cradle-to-gate/{uid}")
async def cradle_to_gate(uid: str, method: str | None = None, top: int = 25):
    _require_store()
    conn = _q()
    try:
        res = conn.cradle_to_gate(uid, method_name=method)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except SystemExit as e:  # numpy missing
        raise HTTPException(500, str(e))
    finally:
        conn.close()
    flows = sorted(res.elementary_flows.values(), key=lambda v: -abs(v["amount"]))[:top]
    impacts = sorted(res.impacts.items(), key=lambda kv: -abs(kv[1]["value"]))[:top]
    return {
        "target": {"uid": res.target_uid, "name": res.target_name},
        "supply_chain_processes": res.n_processes,
        "unlinked_inputs": res.n_unlinked_inputs,
        "notes": res.notes,
        "impacts": [{"category": c, **v} for c, v in impacts],
        "top_elementary_flows": flows,
    }


@router.get("/match")
async def match(q: str = Query(..., min_length=1), top: int = 5, expand: bool = False):
    _require_store()
    return {"query": q, "candidates": get_matcher().match(q, top_k=top, expand=expand)}


@router.post("/reindex")
async def reindex():
    _require_store()
    global _matcher
    m = ProcessMatcher(_q())
    n = m.build_index(force=True)
    _matcher = m
    return {"status": "ok", "indexed_processes": n, "embedder": m.embedder.name}
