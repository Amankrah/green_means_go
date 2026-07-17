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

Auth: /match and /reindex can trigger billable AI work (LLM query expansion and
re-embedding ~46k processes via the OpenAI embeddings API), so both require an
authenticated user. /reindex is an operator action — re-embedding the whole store
is expensive and denial-of-wallet-prone — so it additionally requires the admin
token (INVENTORY_ADMIN_TOKEN, sent as the `X-Admin-Token` header). The read-only
lookup endpoints stay open.
"""
from __future__ import annotations

import asyncio
import os
import secrets
import sqlite3
import sys
import time
from collections import deque
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from auth.deps import get_current_user
from models import User

# make the ingestion package importable
_ING = Path(__file__).resolve().parents[2] / "ingestion"
if str(_ING) not in sys.path:
    sys.path.insert(0, str(_ING))

from canonical_store import DEFAULT_DB          # noqa: E402
from query import CanonicalQuery                # noqa: E402
from matching import ProcessMatcher             # noqa: E402

router = APIRouter(prefix="/inventory", tags=["inventory"])

_matcher: ProcessMatcher | None = None

# Only one reindex may run at a time: it re-embeds ~46k processes and mutates the
# shared matcher + on-disk cache. Concurrent runs would waste money and race on the
# cache file. A second request while one is in flight gets 409 instead of piling on.
_reindex_lock = asyncio.Lock()

# In-process per-user rate limit for /match. Each /match with expand=true bills an
# LLM completion, so even authenticated users are capped. Sliding-window over
# monotonic timestamps. NOTE: in-memory and per-process — with multiple workers the
# effective limit is MATCH_RATE_MAX * num_workers. For a hard global cap, back this
# with Redis; this is a cheap first line of defense against a single account looping.
MATCH_RATE_MAX = int(os.getenv("INVENTORY_MATCH_RATE_MAX", "30"))   # requests...
MATCH_RATE_WINDOW = float(os.getenv("INVENTORY_MATCH_RATE_WINDOW", "60"))  # ...per this many seconds
_match_hits: dict[str, deque[float]] = {}


def _rate_limit_match(user: User) -> None:
    now = time.monotonic()
    hits = _match_hits.setdefault(user.id, deque())
    cutoff = now - MATCH_RATE_WINDOW
    while hits and hits[0] < cutoff:
        hits.popleft()
    if len(hits) >= MATCH_RATE_MAX:
        retry_after = max(1, int(hits[0] + MATCH_RATE_WINDOW - now))
        raise HTTPException(
            status_code=429,
            detail="Too many match requests; slow down.",
            headers={"Retry-After": str(retry_after)},
        )
    hits.append(now)


def match_rate_limited_user(user: User = Depends(get_current_user)) -> User:
    """Auth + per-user rate limit for /match, in one dependency."""
    _rate_limit_match(user)
    return user


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    """Gate for operator-only actions. Requires INVENTORY_ADMIN_TOKEN to be set
    server-side and matched by the caller's X-Admin-Token header. Compared with a
    constant-time check to avoid leaking the token via timing."""
    expected = os.getenv("INVENTORY_ADMIN_TOKEN")
    if not expected:
        # Fail closed: if no admin token is configured, the action is unavailable
        # rather than silently open.
        raise HTTPException(status_code=503, detail="Admin operations are not configured.")
    if not x_admin_token or not secrets.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=403, detail="Admin token required.")


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
async def match(
    q: str = Query(..., min_length=1),
    top: int = 5,
    expand: bool = False,
    user: User = Depends(match_rate_limited_user),
):
    _require_store()
    # match() embeds the query (and, with expand, calls an LLM) — CPU/network work
    # that would otherwise block the event loop. Run it in the threadpool.
    candidates = await run_in_threadpool(
        lambda: get_matcher().match(q, top_k=top, expand=expand)
    )
    return {"query": q, "candidates": candidates}


def _do_reindex() -> dict:
    global _matcher
    m = ProcessMatcher(_q())
    n = m.build_index(force=True)
    _matcher = m
    return {"status": "ok", "indexed_processes": n, "embedder": m.embedder.name}


@router.post("/reindex", dependencies=[Depends(require_admin)])
async def reindex(user: User = Depends(get_current_user)):
    _require_store()
    if _reindex_lock.locked():
        raise HTTPException(status_code=409, detail="A reindex is already in progress.")
    async with _reindex_lock:
        # Re-embedding ~46k processes is heavy CPU/network work; keep it off the
        # event loop so the server stays responsive during the rebuild.
        return await run_in_threadpool(_do_reindex)
