#!/usr/bin/env python3
"""
ipc_reader.py — read a LIVE openLCA database via the IPC protocol into the
canonical store.

This is the convenient path when you've imported ecoinvent + Agribalyse into a
single openLCA database and don't want to export JSON-LD first:

  1. In openLCA: open your database, then Tools > Developer tools > IPC server
     (default port 8080). Leave it running.
  2. python3 ipc_reader.py --name ecoinvent --version "3.11 Cutoff" --port 8080

Processes are streamed via descriptors + get() so a full ecoinvent database does
not have to be pulled at once. For very large DBs the JSON-LD path is faster;
use whichever fits your workflow.

Requires: olca-ipc + olca-schema (pip install olca-ipc). See requirements.txt.
"""
from __future__ import annotations

import sys
from canonical_store import CanonicalStore
import olca_common as oc


def _import_ipc():
    try:
        import olca_ipc as ipc  # noqa
        import olca_schema as o  # noqa
        return ipc, o
    except Exception as exc:  # pragma: no cover
        print(
            "ERROR: olca-ipc / olca-schema not installed.\n"
            "  pip install -r ingestion/requirements.txt\n"
            f"  underlying import error: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1)


def read_ipc(
    store: CanonicalStore,
    source_name: str,
    source_version: str,
    port: int = 8080,
    license: str = "",
    batch: int = 5000,
) -> dict:
    ipc, o = _import_ipc()
    client = ipc.Client(port)

    source_id = store.upsert_source(source_name, source_version, license,
                                    notes=f"IPC import from openLCA :{port}")
    run_id = store.start_run(source_id, "ipc", f"localhost:{port}")
    counts = {"flows": 0, "processes": 0, "exchanges": 0, "cfs": 0}

    try:
        # --- flows (descriptors -> full) ---
        flow_buf = []
        for d in client.get_descriptors(o.Flow):
            flow = client.get(o.Flow, getattr(d, "id", None))
            if flow is None:
                continue
            flow_buf.append(oc.flow_to_row(flow))
            if len(flow_buf) >= batch:
                counts["flows"] += store.add_flows(source_id, flow_buf)
                store.commit(); flow_buf.clear()
        if flow_buf:
            counts["flows"] += store.add_flows(source_id, flow_buf)
            store.commit()
        print(f"  flows: {counts['flows']}")

        # --- processes + exchanges ---
        ex_buf = []
        for d in client.get_descriptors(o.Process):
            proc = client.get(o.Process, getattr(d, "id", None))
            if proc is None:
                continue
            prow, exrows = oc.process_to_rows(proc)
            store.add_process(source_id, prow)
            counts["processes"] += 1
            ex_buf.extend(exrows)
            if len(ex_buf) >= batch:
                counts["exchanges"] += store.add_exchanges(ex_buf)
                store.commit(); ex_buf.clear()
            if counts["processes"] % 2000 == 0:
                print(f"  processes: {counts['processes']} ...")
        if ex_buf:
            counts["exchanges"] += store.add_exchanges(ex_buf)
            store.commit()
        print(f"  processes: {counts['processes']}, exchanges: {counts['exchanges']}")

        # --- impact categories + CFs ---
        for d in client.get_descriptors(o.ImpactCategory):
            cat = client.get(o.ImpactCategory, getattr(d, "id", None))
            if cat is None:
                continue
            crow, cfrows = oc.impact_category_to_rows(cat)
            store.add_impact_category(source_id, crow["uid"], crow["name"], crow["ref_unit"], None)
            if cfrows:
                counts["cfs"] += store.add_cfs(crow["uid"], cfrows)
            store.commit()
        print(f"  characterization factors: {counts['cfs']}")

        store.finish_run(run_id, "ok", counts)
        return counts
    except Exception as exc:
        store.finish_run(run_id, "error", counts, message=str(exc))
        raise


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Load a live openLCA database (IPC) into the canonical store.")
    ap.add_argument("--name", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--license", default="")
    args = ap.parse_args()

    with CanonicalStore() as store:
        counts = read_ipc(store, args.name, args.version, args.port, args.license)
        print("Done:", counts)
