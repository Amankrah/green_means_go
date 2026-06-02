#!/usr/bin/env python3
"""
jsonld_reader.py — read an openLCA JSON-LD zip (olca-schema format) into the
canonical store.

This is the primary, headless ingestion path. It works for:
  - ecoinvent unit-process packages exported as JSON-LD,
  - Agribalyse (open the .zolca in openLCA, then File > Export > JSON-LD),
  - LCIA method packs exported as JSON-LD.

It streams entities (read_each) so large databases don't have to fit in memory,
and commits in batches.

Requires: olca-schema (pip install olca-schema). See requirements.txt.
"""
from __future__ import annotations

import sys
from pathlib import Path

from canonical_store import CanonicalStore
import olca_common as oc


def _import_olca():
    try:
        import olca_schema as o  # noqa
        from olca_schema import zipio  # noqa
        return o, zipio
    except Exception as exc:  # pragma: no cover
        print(
            "ERROR: olca-schema is not installed.\n"
            "  pip install -r ingestion/requirements.txt\n"
            "  (or: pip install olca-schema)\n"
            f"  underlying import error: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1)


def read_jsonld_zip(
    zip_path: Path | str,
    store: CanonicalStore,
    source_name: str,
    source_version: str,
    license: str = "",
    batch: int = 5000,
) -> dict:
    o, zipio = _import_olca()
    zip_path = Path(zip_path)
    if not zip_path.exists():
        raise FileNotFoundError(zip_path)

    source_id = store.upsert_source(source_name, source_version, license,
                                    notes=f"JSON-LD import from {zip_path.name}")
    run_id = store.start_run(source_id, "jsonld", str(zip_path))
    counts = {"flows": 0, "processes": 0, "exchanges": 0, "cfs": 0}

    try:
        reader = zipio.ZipReader(str(zip_path))
        if not hasattr(reader, "read_each"):
            raise RuntimeError(
                "Installed olca-schema lacks ZipReader.read_each — please upgrade: "
                "pip install -U olca-schema"
            )
        try:
            # --- flows ---
            flow_buf = []
            for flow in reader.read_each(o.Flow):
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
            for proc in reader.read_each(o.Process):
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

            # --- impact methods + categories + CFs ---
            for method in reader.read_each(o.ImpactMethod):
                store.add_impact_method(source_id, getattr(method, "id", None),
                                        getattr(method, "name", None))
                for cat_ref in (getattr(method, "impact_categories", None) or []):
                    # store the link; full category (with CFs) is read below
                    pass
            for cat in reader.read_each(o.ImpactCategory):
                crow, cfrows = oc.impact_category_to_rows(cat)
                store.add_impact_category(source_id, crow["uid"], crow["name"],
                                          crow["ref_unit"], None)
                if cfrows:
                    counts["cfs"] += store.add_cfs(crow["uid"], cfrows)
                store.commit()
            print(f"  characterization factors: {counts['cfs']}")
        finally:
            close = getattr(reader, "close", None)
            if callable(close):
                close()

        store.finish_run(run_id, "ok", counts)
        return counts
    except Exception as exc:
        store.finish_run(run_id, "error", counts, message=str(exc))
        raise


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Load an openLCA JSON-LD zip into the canonical store.")
    ap.add_argument("zip", help="path to the JSON-LD .zip")
    ap.add_argument("--name", required=True, help="source name, e.g. ecoinvent")
    ap.add_argument("--version", required=True, help="source version, e.g. '3.11 Cutoff Unit'")
    ap.add_argument("--license", default="", help="license note")
    args = ap.parse_args()

    with CanonicalStore() as store:
        counts = read_jsonld_zip(args.zip, store, args.name, args.version, args.license)
        print("Done:", counts)
