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


def _load_units(client, o, store: CanonicalStore) -> int:
    """Load openLCA UnitGroups -> unit conversion factors.

    Exchange amounts and a provider's reference amount may be in different units of
    the same group (kg vs t). conversion_factor converts a unit to its group's
    reference unit, making them commensurate. Units are database-agnostic, so this
    table is shared across sources.
    """
    rows = []
    for d in client.get_descriptors(o.UnitGroup):
        g = client.get(o.UnitGroup, getattr(d, "id", None))
        if g is None:
            continue
        gname = getattr(g, "name", None)
        refu = oc.ref_name(getattr(g, "reference_unit", None))
        for u in (getattr(g, "units", None) or []):
            uname = getattr(u, "name", None)
            rows.append({
                "name": uname,
                "unit_group": gname,
                "conversion_factor": getattr(u, "conversion_factor", 1.0) or 1.0,
                "is_reference": 1 if (uname and uname == refu) else 0,
            })
    n = store.add_units(rows)
    store.commit()
    print(f"  units: {n} (conversion factors)", flush=True)
    return n


def backfill_units(store: CanonicalStore, port: int = 8080) -> dict:
    """Fast repair path: load unit conversion factors from the OPEN openLCA database."""
    ipc, o = _import_ipc()
    client = ipc.Client(port)
    return {"units": _load_units(client, o, store)}


def _load_methods(client, o, store: CanonicalStore, source_id: int) -> dict:
    """Load ImpactMethod entities and return {category_uid: method_uid}.

    openLCA keeps ImpactCategory as a standalone entity; the method only *references*
    its categories. Without this, categories have no method and `--method "ReCiPe"`
    silently matches nothing. (A category shared by several methods keeps the first.)
    """
    method_of: dict[str, str] = {}
    n = 0
    for d in client.get_descriptors(o.ImpactMethod):
        m = client.get(o.ImpactMethod, getattr(d, "id", None))
        if m is None:
            continue
        muid = getattr(m, "id", None)
        store.add_impact_method(source_id, muid, getattr(m, "name", None))
        n += 1
        for cref in (getattr(m, "impact_categories", None) or []):
            cuid = oc.ref_id(cref)
            if cuid:
                method_of.setdefault(cuid, muid)
    store.commit()
    print(f"  impact methods: {n} (covering {len(method_of)} categories)", flush=True)
    return method_of


def backfill_methods(
    store: CanonicalStore,
    source_name: str,
    source_version: str,
    port: int = 8080,
) -> dict:
    """Fast repair path: load ImpactMethods for the OPEN openLCA database and link
    already-imported categories to them. Does NOT re-read flows/processes/CFs."""
    ipc, o = _import_ipc()
    client = ipc.Client(port)
    source_id = store.upsert_source(source_name, source_version)
    method_of = _load_methods(client, o, store, source_id)
    linked = 0
    for cuid, muid in method_of.items():
        cur = store.conn.execute(
            "UPDATE impact_categories SET method_uid=? WHERE uid=? AND method_uid IS NULL",
            (muid, cuid),
        )
        linked += cur.rowcount
    store.commit()
    print(f"  linked {linked} existing categories to their method")
    return {"methods": len(set(method_of.values())), "linked": linked}


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
        # --- unit conversion factors (shared across sources) ---
        _load_units(client, o, store)

        # --- flows (descriptors -> full) ---
        print("  fetching flow descriptors from openLCA ...", flush=True)
        flow_refs = client.get_descriptors(o.Flow)
        total_flows = len(flow_refs)
        print(f"  {total_flows} flows to read (one IPC call each — this takes a while)", flush=True)
        flow_buf = []
        seen = 0
        for d in flow_refs:
            flow = client.get(o.Flow, getattr(d, "id", None))
            seen += 1
            if seen % 2000 == 0:
                print(f"    flows {seen}/{total_flows} ...", flush=True)
            if flow is None:
                continue
            flow_buf.append(oc.flow_to_row(flow))
            if len(flow_buf) >= batch:
                counts["flows"] += store.add_flows(source_id, flow_buf)
                store.commit(); flow_buf.clear()
        if flow_buf:
            counts["flows"] += store.add_flows(source_id, flow_buf)
            store.commit()
        print(f"  flows: {counts['flows']}", flush=True)

        # --- processes + exchanges ---
        print("  fetching process descriptors ...", flush=True)
        proc_refs = client.get_descriptors(o.Process)
        print(f"  {len(proc_refs)} processes to read", flush=True)
        ex_buf = []
        for d in proc_refs:
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

        # --- impact methods first, so categories can be linked to their method ---
        method_of = _load_methods(client, o, store, source_id)

        # --- impact categories + CFs ---
        for d in client.get_descriptors(o.ImpactCategory):
            cat = client.get(o.ImpactCategory, getattr(d, "id", None))
            if cat is None:
                continue
            crow, cfrows = oc.impact_category_to_rows(cat)
            store.add_impact_category(source_id, crow["uid"], crow["name"], crow["ref_unit"],
                                      method_of.get(crow["uid"]))
            if cfrows:
                counts["cfs"] += store.add_cfs(crow["uid"], cfrows)
            store.commit()
        print(f"  characterization factors: {counts['cfs']}")

        # An empty load is almost always a live-openLCA problem, not a real result.
        # Record it as an error rather than a clean run with zero rows.
        if counts["processes"] == 0 and counts["flows"] == 0:
            msg = (
                "IPC returned no data. Most likely NO DATABASE IS OPEN in openLCA "
                "(the server reports 'con is null'). In openLCA: double-click the "
                "database in Navigation, accept the update prompt, wait until it is "
                "bold/expanded, then restart the IPC server and retry."
            )
            store.finish_run(run_id, "error", counts, message=msg)
            raise RuntimeError(msg)

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
