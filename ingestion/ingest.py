#!/usr/bin/env python3
"""
ingest.py — one CLI to drive the LCA Engineer ingestion pipeline.

    SharePoint  --fetch-->  data/raw  --(openLCA import, manual)-->  JSON-LD / live IPC
                                                                          |
                                                            load-jsonld / load-ipc
                                                                          v
                                                              canonical store (SQLite)

Commands:
    fetch         Fetch databases from the McGill share via rclone (wraps fetch_data.py)
    load-jsonld   Load an openLCA JSON-LD zip into the canonical store
    load-ipc      Load a live openLCA database (IPC server) into the canonical store
    stats         Show what is currently in the canonical store

Examples:
    python3 ingest.py fetch --only P0
    python3 ingest.py load-jsonld data/raw/ecoinvent_3.11_cutoff_unit/ecoinvent.zip \\
            --name ecoinvent --version "3.11 Cutoff Unit" --license "ecoinvent academic/research"
    python3 ingest.py load-ipc --name agribalyse --version 3.2 --port 8080
    python3 ingest.py stats
"""
from __future__ import annotations

import argparse
import json
import sys

from canonical_store import CanonicalStore


def cmd_fetch(args) -> int:
    import fetch_data
    argv = []
    if args.only:
        argv += ["--only", args.only]
    if args.remote:
        argv += ["--remote", args.remote]
    if args.dry_run:
        argv += ["--dry-run"]
    return fetch_data.main(argv)


def cmd_load_jsonld(args) -> int:
    from jsonld_reader import read_jsonld_zip
    with CanonicalStore(args.db) as store:
        counts = read_jsonld_zip(args.zip, store, args.name, args.version, args.license)
        print("Loaded:", json.dumps(counts))
    return 0


def cmd_load_ipc(args) -> int:
    from ipc_reader import read_ipc
    with CanonicalStore(args.db) as store:
        counts = read_ipc(store, args.name, args.version, args.port, args.license)
        print("Loaded:", json.dumps(counts))
    return 0


def cmd_load_methods(args) -> int:
    from ipc_reader import backfill_methods
    with CanonicalStore(args.db) as store:
        res = backfill_methods(store, args.name, args.version, args.port)
        print("Done:", json.dumps(res))
    return 0


def cmd_load_units(args) -> int:
    from ipc_reader import backfill_units
    with CanonicalStore(args.db) as store:
        res = backfill_units(store, args.port)
        print("Done:", json.dumps(res))
    return 0


def cmd_glad(args) -> int:
    """Fetch GLAD mapped files (LFS) + normalise every flow to a FEDEFL fed_id."""
    import glad_fetch, glad_load
    if glad_fetch.main([]) != 0:
        return 1
    with CanonicalStore(args.db) as store:
        glad_load.build_fed_ids(store)
    return 0


def cmd_flowkeys(args) -> int:
    with CanonicalStore(args.db) as store:
        n = store.backfill_flow_keys()
        print(f"Done: computed flow_key for {n} flows")
    return 0


def cmd_stats(args) -> int:
    with CanonicalStore(args.db) as store:
        print(json.dumps(store.stats(), indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default=None, help="canonical store path (default: data/canonical/lca_engineer.sqlite)")
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="fetch databases from SharePoint via rclone")
    f.add_argument("--only", help="priority (P0/P1/P2/P3) or item name")
    f.add_argument("--remote", default="mcgill")
    f.add_argument("--dry-run", action="store_true")
    f.set_defaults(func=cmd_fetch)

    j = sub.add_parser("load-jsonld", help="load an openLCA JSON-LD zip")
    j.add_argument("zip")
    j.add_argument("--name", required=True)
    j.add_argument("--version", required=True)
    j.add_argument("--license", default="")
    j.set_defaults(func=cmd_load_jsonld)

    i = sub.add_parser("load-ipc", help="load a live openLCA database via IPC")
    i.add_argument("--name", required=True)
    i.add_argument("--version", required=True)
    i.add_argument("--port", type=int, default=8080)
    i.add_argument("--license", default="")
    i.set_defaults(func=cmd_load_ipc)

    lm = sub.add_parser("load-methods",
                        help="backfill LCIA methods + link categories (fast, no re-import)")
    lm.add_argument("--name", required=True)
    lm.add_argument("--version", required=True)
    lm.add_argument("--port", type=int, default=8080)
    lm.set_defaults(func=cmd_load_methods)

    lu = sub.add_parser("load-units",
                        help="backfill unit conversion factors from openLCA (fast, no re-import)")
    lu.add_argument("--port", type=int, default=8080)
    lu.set_defaults(func=cmd_load_units)

    fk = sub.add_parser("flowkeys", help="backfill canonical flow keys (CF nomenclature bridge)")
    fk.set_defaults(func=cmd_flowkeys)

    gl = sub.add_parser("glad", help="fetch GLAD mapped files + assign authoritative FEDEFL fed_id to flows")
    gl.set_defaults(func=cmd_glad)

    s = sub.add_parser("stats", help="show canonical store contents")
    s.set_defaults(func=cmd_stats)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    # default db handling: let CanonicalStore default apply when --db is None
    if args.db is None:
        from canonical_store import DEFAULT_DB
        args.db = str(DEFAULT_DB)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
