#!/usr/bin/env python3
"""
canonical_store.py — the LCA Engineer's canonical data store.

ONE internal schema, MANY importers (see DATABASE_PLAN.md §3). Readers for
ecoinvent / Agribalyse / LCIA methods all write through this single DAO so the
engine never sees a source's native quirks, and every record carries provenance
(source + version + import run) for ISO-14048 / reproducibility.

Implementation: SQLite for the scaffold — zero-config, file-based, perfect for
reproducible research and easy to ship. The schema mirrors the canonical record
types in LITERATURE_EXTRACTION.md and migrates cleanly to PostgreSQL later
(swap the connection + a few type names; the DAO surface stays the same).

Tables
------
sources                : a database edition (ecoinvent 3.11 Cutoff, Agribalyse 3.2, ...)
import_runs            : one ingestion run (provenance: when, from what file, counts)
flows                  : product / waste / elementary flows (biosphere + technosphere)
processes              : unit processes (the supply chain)
exchanges              : process <-> flow inputs/outputs (the technosphere/biosphere matrix)
impact_methods         : LCIA methods (ReCiPe, EF, ...)
impact_categories      : midpoint/endpoint categories within a method
characterization_factors : flow -> impact factor (the LCIA CFs)
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "canonical" / "lca_engineer.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,           -- e.g. 'ecoinvent'
    version     TEXT NOT NULL,           -- e.g. '3.11 Cutoff Unit'
    license     TEXT,                    -- e.g. 'ecoinvent (licensed, academic/research)'
    notes       TEXT,
    created_at  TEXT NOT NULL,
    UNIQUE(name, version)
);

CREATE TABLE IF NOT EXISTS import_runs (
    id            INTEGER PRIMARY KEY,
    source_id     INTEGER NOT NULL REFERENCES sources(id),
    reader        TEXT NOT NULL,         -- 'jsonld' | 'ipc'
    origin        TEXT,                  -- file path or ipc endpoint
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    status        TEXT NOT NULL DEFAULT 'running',
    n_flows       INTEGER DEFAULT 0,
    n_processes   INTEGER DEFAULT 0,
    n_exchanges   INTEGER DEFAULT 0,
    n_cfs         INTEGER DEFAULT 0,
    message       TEXT
);

-- Unit conversion factors (from openLCA UnitGroups). Required: exchange amounts and
-- a provider's reference amount can be in DIFFERENT units of the same group (an
-- Agribalyse input of 6411 kg manure against a provider whose reference is 0.9966 t).
-- Without converting, the solver over-scales that provider 1000x.
CREATE TABLE IF NOT EXISTS units (
    name              TEXT PRIMARY KEY,
    unit_group        TEXT,
    conversion_factor REAL NOT NULL DEFAULT 1.0,  -- multiply to get the group's reference unit
    is_reference      INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS flows (
    uid         TEXT PRIMARY KEY,        -- openLCA/source UUID
    source_id   INTEGER NOT NULL REFERENCES sources(id),
    name        TEXT NOT NULL,
    category    TEXT,
    flow_type   TEXT,                    -- ELEMENTARY_FLOW | PRODUCT_FLOW | WASTE_FLOW
    ref_unit    TEXT,
    cas         TEXT,
    formula     TEXT,
    flow_key    TEXT,                    -- canonical (name|compartment) for CF bridging
    cas_key     TEXT                     -- secondary (CAS|compartment), substance-identity cats only
);

CREATE TABLE IF NOT EXISTS processes (
    uid          TEXT PRIMARY KEY,
    source_id    INTEGER NOT NULL REFERENCES sources(id),
    name         TEXT NOT NULL,
    category     TEXT,
    location     TEXT,
    process_type TEXT,
    ref_flow     TEXT,                   -- reference product flow uid
    ref_amount   REAL,
    ref_unit     TEXT
);

CREATE TABLE IF NOT EXISTS exchanges (
    id                  INTEGER PRIMARY KEY,
    process_uid         TEXT NOT NULL REFERENCES processes(uid),
    flow_uid            TEXT,
    flow_name           TEXT,
    is_input            INTEGER NOT NULL,    -- 1 input, 0 output
    is_elementary       INTEGER NOT NULL DEFAULT 0,
    is_reference        INTEGER NOT NULL DEFAULT 0,
    amount              REAL,
    unit                TEXT,
    provider_process_uid TEXT                -- default provider (links technosphere)
);

CREATE TABLE IF NOT EXISTS impact_methods (
    uid        TEXT PRIMARY KEY,
    source_id  INTEGER NOT NULL REFERENCES sources(id),
    name       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS impact_categories (
    uid         TEXT PRIMARY KEY,
    method_uid  TEXT REFERENCES impact_methods(uid),
    source_id   INTEGER NOT NULL REFERENCES sources(id),
    name        TEXT NOT NULL,
    ref_unit    TEXT
);

CREATE TABLE IF NOT EXISTS characterization_factors (
    id            INTEGER PRIMARY KEY,
    category_uid  TEXT NOT NULL REFERENCES impact_categories(uid),
    flow_uid      TEXT,
    flow_name     TEXT,
    factor        REAL NOT NULL,
    unit          TEXT
);

CREATE INDEX IF NOT EXISTS ix_flows_name        ON flows(name);
CREATE INDEX IF NOT EXISTS ix_processes_name    ON processes(name);
CREATE INDEX IF NOT EXISTS ix_exchanges_process ON exchanges(process_uid);
CREATE INDEX IF NOT EXISTS ix_exchanges_flow    ON exchanges(flow_uid);
CREATE INDEX IF NOT EXISTS ix_cf_category       ON characterization_factors(category_uid);
CREATE INDEX IF NOT EXISTS ix_cf_flow           ON characterization_factors(flow_uid);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CanonicalStore:
    """Thin DAO over SQLite. Use as a context manager."""

    def __init__(self, db_path: Path | str = DEFAULT_DB):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        # bulk-load friendly pragmas (safe for a rebuildable cache DB)
        self.conn.execute("PRAGMA journal_mode = WAL;")
        self.conn.execute("PRAGMA synchronous = NORMAL;")
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        """Add columns introduced after a store was first created (CREATE TABLE IF
        NOT EXISTS won't add them to an existing table)."""
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(flows)")}
        if "flow_key" not in cols:
            self.conn.execute("ALTER TABLE flows ADD COLUMN flow_key TEXT")
        if "cas_key" not in cols:
            self.conn.execute("ALTER TABLE flows ADD COLUMN cas_key TEXT")
        self.conn.execute("CREATE INDEX IF NOT EXISTS ix_flows_key ON flows(flow_key)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS ix_flows_caskey ON flows(cas_key)")

    # -- context manager ------------------------------------------------------
    def __enter__(self) -> "CanonicalStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self.conn.commit()
        self.conn.close()

    # -- sources & runs -------------------------------------------------------
    def upsert_source(self, name: str, version: str, license: str = "", notes: str = "") -> int:
        cur = self.conn.execute(
            "INSERT INTO sources(name, version, license, notes, created_at) "
            "VALUES (?,?,?,?,?) "
            "ON CONFLICT(name, version) DO UPDATE SET license=excluded.license, notes=excluded.notes",
            (name, version, license, notes, _now()),
        )
        self.conn.commit()
        if cur.lastrowid:
            row = self.conn.execute(
                "SELECT id FROM sources WHERE name=? AND version=?", (name, version)
            ).fetchone()
            return row["id"]
        return self.conn.execute(
            "SELECT id FROM sources WHERE name=? AND version=?", (name, version)
        ).fetchone()["id"]

    def start_run(self, source_id: int, reader: str, origin: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO import_runs(source_id, reader, origin, started_at) VALUES (?,?,?,?)",
            (source_id, reader, origin, _now()),
        )
        self.conn.commit()
        return cur.lastrowid

    def finish_run(self, run_id: int, status: str, counts: dict, message: str = "") -> None:
        self.conn.execute(
            "UPDATE import_runs SET finished_at=?, status=?, n_flows=?, n_processes=?, "
            "n_exchanges=?, n_cfs=?, message=? WHERE id=?",
            (
                _now(),
                status,
                counts.get("flows", 0),
                counts.get("processes", 0),
                counts.get("exchanges", 0),
                counts.get("cfs", 0),
                message,
                run_id,
            ),
        )
        self.conn.commit()

    # -- bulk inserts (executemany for speed on big DBs) ----------------------
    def add_flows(self, source_id: int, rows: Iterable[dict]) -> int:
        from flowkey import flow_key, cas_key
        data = [
            (r["uid"], source_id, r["name"], r.get("category"), r.get("flow_type"),
             r.get("ref_unit"), r.get("cas"), r.get("formula"),
             flow_key(r.get("cas"), r.get("name"), r.get("category")),
             cas_key(r.get("cas"), r.get("category")))
            for r in rows
        ]
        self.conn.executemany(
            "INSERT OR REPLACE INTO flows(uid, source_id, name, category, flow_type, ref_unit, cas, formula, flow_key, cas_key) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            data,
        )
        return len(data)

    def backfill_flow_keys(self) -> int:
        """Compute flow_key + cas_key for every flow lacking a flow_key (existing stores)."""
        from flowkey import flow_key, cas_key
        rows = self.conn.execute(
            "SELECT uid, cas, name, category FROM flows WHERE flow_key IS NULL OR cas_key IS NULL"
        ).fetchall()
        updates = [(flow_key(r["cas"], r["name"], r["category"]),
                    cas_key(r["cas"], r["category"]), r["uid"]) for r in rows]
        self.conn.executemany("UPDATE flows SET flow_key=?, cas_key=? WHERE uid=?", updates)
        self.conn.commit()
        return len(updates)

    def add_units(self, rows: Iterable[dict]) -> int:
        data = [
            (r["name"], r.get("unit_group"), float(r.get("conversion_factor") or 1.0),
             int(r.get("is_reference", 0)))
            for r in rows if r.get("name")
        ]
        self.conn.executemany(
            "INSERT OR REPLACE INTO units(name, unit_group, conversion_factor, is_reference) "
            "VALUES (?,?,?,?)",
            data,
        )
        return len(data)

    def add_process(self, source_id: int, p: dict) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO processes(uid, source_id, name, category, location, process_type, "
            "ref_flow, ref_amount, ref_unit) VALUES (?,?,?,?,?,?,?,?,?)",
            (p["uid"], source_id, p["name"], p.get("category"), p.get("location"),
             p.get("process_type"), p.get("ref_flow"), p.get("ref_amount"), p.get("ref_unit")),
        )

    def add_exchanges(self, rows: Iterable[dict]) -> int:
        data = [
            (r["process_uid"], r.get("flow_uid"), r.get("flow_name"), int(r["is_input"]),
             int(r.get("is_elementary", 0)), int(r.get("is_reference", 0)),
             r.get("amount"), r.get("unit"), r.get("provider_process_uid"))
            for r in rows
        ]
        self.conn.executemany(
            "INSERT INTO exchanges(process_uid, flow_uid, flow_name, is_input, is_elementary, "
            "is_reference, amount, unit, provider_process_uid) VALUES (?,?,?,?,?,?,?,?,?)",
            data,
        )
        return len(data)

    def add_impact_method(self, source_id: int, uid: str, name: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO impact_methods(uid, source_id, name) VALUES (?,?,?)",
            (uid, source_id, name),
        )

    def add_impact_category(self, source_id: int, uid: str, name: str,
                            ref_unit: Optional[str], method_uid: Optional[str]) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO impact_categories(uid, method_uid, source_id, name, ref_unit) "
            "VALUES (?,?,?,?,?)",
            (uid, method_uid, source_id, name, ref_unit),
        )

    def add_cfs(self, category_uid: str, rows: Iterable[dict]) -> int:
        data = [
            (category_uid, r.get("flow_uid"), r.get("flow_name"), r["factor"], r.get("unit"))
            for r in rows
        ]
        self.conn.executemany(
            "INSERT INTO characterization_factors(category_uid, flow_uid, flow_name, factor, unit) "
            "VALUES (?,?,?,?,?)",
            data,
        )
        return len(data)

    def commit(self) -> None:
        self.conn.commit()

    # -- reporting ------------------------------------------------------------
    def stats(self) -> dict:
        def n(t: str) -> int:
            return self.conn.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]

        out = {t: n(t) for t in (
            "sources", "import_runs", "flows", "processes", "exchanges",
            "impact_methods", "impact_categories", "characterization_factors",
        )}
        out["sources_detail"] = [
            dict(r) for r in self.conn.execute(
                "SELECT name, version, license FROM sources ORDER BY name"
            ).fetchall()
        ]
        return out


if __name__ == "__main__":
    # quick smoke test of the schema
    import json
    with CanonicalStore() as store:
        sid = store.upsert_source("selftest", "v0", "n/a", "schema smoke test")
        run = store.start_run(sid, "selftest", "memory")
        store.add_flows(sid, [{"uid": "f1", "name": "CO2", "flow_type": "ELEMENTARY_FLOW", "ref_unit": "kg"}])
        store.add_process(sid, {"uid": "p1", "name": "demo", "ref_unit": "kg", "ref_amount": 1.0})
        store.add_exchanges([{"process_uid": "p1", "flow_uid": "f1", "is_input": 0, "is_elementary": 1, "amount": 2.0, "unit": "kg"}])
        store.finish_run(run, "ok", {"flows": 1, "processes": 1, "exchanges": 1})
        store.commit()
        print(json.dumps(store.stats(), indent=2))
