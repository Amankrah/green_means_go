#!/usr/bin/env python3
"""
flowmap.py — map on-farm field emissions (from the Rust LCI kernel) to representative
canonical store flows, so they characterize through the same validated path as the
supply-chain inventory.

The Rust kernel emits a handful of field flows with its own naming (`N2O`/air,
`CH4`/air, `CO2`/air, water/resource, land occupation…). Each maps to a canonical
elementary flow identified by (substance name / CAS, compartment). We resolve that to
an actual store flow UID once (cached), matching by CAS+compartment then name, so the
merged inventory is entirely UID-keyed for characterization.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from ingestion.canonical_store import DEFAULT_DB          # noqa: E402
from ingestion.flowkey import norm_cas, norm_compartment  # noqa: E402

# Rust substance key -> (canonical name candidates, CAS, medium)
# CAS is the strong matcher; names are fallbacks / for CAS-less flows.
ONFARM_FLOWS = {
    # substance (Rust)         canonical name(s)                          CAS          medium
    "N2O":        (("Dinitrogen monoxide", "Nitrous oxide"),              "10024-97-2", "emission/air"),
    "CH4":        (("Methane", "Methane, fossil"),                        "74-82-8",    "emission/air"),
    "CH4_bio":    (("Methane, non-fossil", "Methane, biogenic"),          "74-82-8",    "emission/air"),
    "CO2":        (("Carbon dioxide, fossil", "Carbon dioxide"),          "124-38-9",   "emission/air"),
    "CO2_bio":    (("Carbon dioxide, non-fossil", "Carbon dioxide, in air"), "124-38-9", "emission/air"),
    "NH3":        (("Ammonia",),                                          "7664-41-7",  "emission/air"),
    "NOx":        (("Nitrogen oxides",),                                  "11104-93-1", "emission/air"),
    "NO3":        (("Nitrate",),                                          "14797-55-8", "emission/water"),
    "PO4":        (("Phosphate",),                                        "14265-44-2", "emission/water"),
    "P":          (("Phosphorus",),                                       "7723-14-0",  "emission/water"),
    "SO2":        (("Sulfur dioxide",),                                   "7446-09-5",  "emission/air"),
    "PM25":       (("Particulates, < 2.5 um", "Particulate Matter, < 2.5 um"), None,    "emission/air"),
    "water":      (("Water",),                                           None,          "resource/inwater"),
    "land_occ":   (("Occupation, annual crop", "Occupation, annual crop, non-irrigated"), None, "resource/land"),
}


class OnFarmFlowMap:
    def __init__(self, db_path=DEFAULT_DB):
        # check_same_thread=False: served across FastAPI threadpool threads under the
        # per-engine lock in engine/service.py (see CanonicalQuery for the rationale).
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._cache: dict[str, str | None] = {}

    def close(self):
        self.conn.close()

    def _resolve(self, names, cas, medium) -> str | None:
        # 1) exact name + compartment FIRST — the name carries the fossil/biogenic
        #    qualifier ("Carbon dioxide, fossil" vs "…non-fossil") that CAS can't (both
        #    share 124-38-9), so name-first keeps biogenic and fossil flows distinct.
        for nm in names:
            for r in self.conn.execute(
                "SELECT uid, category FROM flows WHERE name=? AND flow_type='ELEMENTARY_FLOW'",
                (nm,),
            ):
                if norm_compartment(r["category"]) == medium:
                    return r["uid"]
        # 2) CAS + compartment fallback (for flows whose store name differs from ours)
        c = norm_cas(cas)
        if c:
            for r in self.conn.execute(
                "SELECT uid, category FROM flows WHERE cas=? OR cas=?",
                (cas, c),
            ):
                if norm_compartment(r["category"]) == medium:
                    return r["uid"]
        return None

    def resolve(self, substance: str) -> str | None:
        """Rust substance key -> a canonical store flow UID (or None if unmappable)."""
        if substance in self._cache:
            return self._cache[substance]
        spec = ONFARM_FLOWS.get(substance)
        uid = self._resolve(*spec) if spec else None
        self._cache[substance] = uid
        return uid

    def coverage(self) -> dict:
        """Diagnostic: which on-farm flows resolve to a store flow."""
        return {k: (self.resolve(k) is not None) for k in ONFARM_FLOWS}


if __name__ == "__main__":
    m = OnFarmFlowMap()
    ok = m.coverage()
    for k, v in ok.items():
        print(f"  {'OK ' if v else 'MISS'} {k:<10} -> {m.resolve(k)}")
    print(f"\nresolved {sum(ok.values())}/{len(ok)} on-farm flows")
