#!/usr/bin/env python3
"""
test_matching.py — proves the matching subsystem ranks the right process first,
using the dependency-free LexicalEmbedder on a small synthetic catalogue.

Run:  python3 test_matching.py
"""
from __future__ import annotations

import os
import tempfile

from canonical_store import CanonicalStore
from query import CanonicalQuery
from matching import ProcessMatcher, LexicalEmbedder

CATALOGUE = [
    ("p-maize", "maize grain production", "cereals", "GH"),
    ("p-rice", "rice production, paddy", "cereals", "NG"),
    ("p-urea", "urea ammonium nitrate production", "fertiliser", "GLO"),
    ("p-npk", "NPK compound fertiliser 15-15-15 production", "fertiliser", "GLO"),
    ("p-diesel", "diesel, burned in agricultural machinery", "energy", "GLO"),
    ("p-elec-gh", "electricity, grid mix", "energy", "GH"),
    ("p-cassava", "cassava root production", "roots and tubers", "NG"),
]

# (query text, expected best uid)
CASES = [
    ("local maize", "p-maize"),
    ("nitrogen fertiliser urea", "p-urea"),
    ("NPK 15-15-15", "p-npk"),
    ("diesel for the tractor", "p-diesel"),
    ("grid electricity Ghana", "p-elec-gh"),
    ("cassava", "p-cassava"),
]


def build(db_path: str):
    with CanonicalStore(db_path) as store:
        sid = store.upsert_source("synthetic", "v1", "test")
        for uid, name, cat, loc in CATALOGUE:
            store.add_process(sid, {"uid": uid, "name": name, "category": cat, "location": loc,
                                    "ref_amount": 1.0, "ref_unit": "kg"})
        store.commit()


def main() -> int:
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    try:
        build(path)
        with CanonicalQuery(path) as q:
            m = ProcessMatcher(q, embedder=LexicalEmbedder())
            n = m.build_index(force=True)
            print(f"index: {n} processes, embedder={m.embedder.name}\n")
            ok = True
            for text, expected in CASES:
                ranked = m.match(text, top_k=3)
                top = ranked[0]["uid"] if ranked else None
                good = top == expected
                ok = ok and good
                got = ", ".join(f"{r['uid']}({r['score']})" for r in ranked)
                print(f"  {'PASS' if good else 'FAIL'}  {text!r:32s} -> {top}   [{got}]")
            print("\nRESULT:", "ALL PASS ✅" if ok else "FAILURES ❌")
            return 0 if ok else 1
    finally:
        # also clear the embedding cache written during build_index
        for p in EMB_GLOB():
            try: os.remove(p)
            except OSError: pass
        for ext in ("", "-wal", "-shm"):
            try: os.remove(path + ext)
            except OSError: pass


def EMB_GLOB():
    from matching import EMB_CACHE
    return list(EMB_CACHE.glob("proc_emb_*.npz"))


if __name__ == "__main__":
    raise SystemExit(main())
