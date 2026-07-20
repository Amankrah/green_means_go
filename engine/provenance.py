#!/usr/bin/env python3
"""
provenance.py: reproducibility stamp attached to every assessment result and export.

Researchers cannot reproduce or diff a result without knowing exactly which engine build,
background database editions, LCIA method, and field-emission model produced it. This
module derives that stamp from the live store (authoritative dataset versions) plus the
engine's own version constants, so a re-solve against an updated engine is diff-able rather
than silently different.
"""
from __future__ import annotations

from datetime import datetime, timezone

# Engine build. Bump when the LCI/solve/characterization behaviour changes in a way that
# can move numbers, so stored results carry the version that produced them.
ENGINE_NAME = "Green Means Go LCA Engine"
ENGINE_VERSION = "2.1.0"

# Export/result schema version. Bump on any breaking change to the result or export shape
# so downstream scripts can branch on it.
SCHEMA_VERSION = "1.0"

FIELD_EMISSION_MODEL = "IPCC 2019 Refinement to the 2006 IPCC Guidelines, Volume 4"


def build_provenance(engine, method: str) -> dict:
    """Assemble the reproducibility block. `engine` is a FarmLCA/process engine exposing
    `.q.sources()`; `method` is the full LCIA method name used for this result."""
    databases: list[dict] = []
    q = getattr(engine, "q", None)
    if q is not None and hasattr(q, "sources"):
        try:
            databases = q.sources()
        except Exception:
            databases = []

    region = getattr(engine, "region", None)
    return {
        "engine": ENGINE_NAME,
        "engine_version": ENGINE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "lcia_method": method,
        "field_emission_model": FIELD_EMISSION_MODEL,
        # Authoritative dataset editions loaded in the store (e.g. ecoinvent 3.11 Cutoff),
        # not a hardcoded string. This is the reproducibility pin the export needs.
        "background_databases": databases,
        "region": getattr(region, "name", None),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
