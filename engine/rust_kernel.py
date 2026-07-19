#!/usr/bin/env python3
"""
rust_kernel.py — invoke the Rust LCI kernel and extract its on-farm field emissions
for the Python characterization path (Option A).

The Rust engine computes the full on-farm inventory. We take from it ONLY the DIRECT
field emissions (N2O, indirect N2O/nitrate leaching, on-farm fuel-combustion CO2, rice
CH4, irrigation water, land occupation). We deliberately DROP the upstream production
burdens it also computes (fertiliser production CO2, phosphate rock, potash, pesticide
production) — those come from the supply-chain solver, so keeping both would double-
count. The pre-aggregated "CO2 equivalent" is also dropped (already characterized).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
RUST_DIR = _ROOT / "african_lca_backend"
# Cargo appends .exe on Windows; check both so the same lookup works on either platform.
_EXE = ".exe" if os.name == "nt" else ""
BINARIES = [RUST_DIR / f"target/release/server{_EXE}", RUST_DIR / f"target/debug/server{_EXE}"]

# Rust InventoryItem.substance  ->  flowmap.ONFARM_FLOWS key
SUBSTANCE_MAP = {
    "Dinitrogen monoxide (N2O)": "N2O",
    "Dinitrogen monoxide (N2O) - indirect": "N2O",
    "Nitrate (NO3-)": "NO3",
    "Carbon dioxide (CO2)": "CO2",           # kept only when source is direct (see below)
    "Methane (CH4)": "CH4_bio",              # rice paddy CH4 is biogenic
    "Water": "water",
    "Land occupation, annual crop": "land_occ",
}

# Sources that mean UPSTREAM production (come from the supply-chain solver) -> drop.
_UPSTREAM_MARKERS = ("production", "mining", "transport of")

# On-farm fuel/electricity COMBUSTION CO2 the Rust kernel emits (source "... consumption:
# NNN L/year" / "... consumption: NNN kWh/year", or legacy "(ESTIMATED...)" flat fallbacks).
# This is ALSO produced by the supply-chain solver: ecoinvent "diesel, burned in agricultural
# machinery" is the combustion process and the electricity market carries generation
# emissions. Keeping the Rust value too would double-count fuel/grid CO2, so we drop it
# and let the supply-chain solver own it (including Python activity defaults).
_ENERGY_COMBUSTION_MARKERS = ("consumption:", "(estimated")


def _binary() -> Path | None:
    return next((b for b in BINARIES if b.exists()), None)


def run_kernel(assessment: dict, timeout: int = 120) -> dict:
    """Run the Rust binary on an assessment dict; return the parsed result JSON."""
    b = _binary()
    if not b:
        raise FileNotFoundError(
            "Rust binary not built. Run: cd african_lca_backend && cargo build --release")
    fd, tmp = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(assessment, fh)
        # The kernel writes UTF-8; decoding with the Windows locale codec (cp1252) would
        # raise on its non-latin1 output, so pin the encoding rather than inherit it.
        r = subprocess.run([str(b), tmp], capture_output=True, text=True,
                           timeout=timeout, cwd=str(RUST_DIR),
                           encoding="utf-8", errors="replace")
        out = r.stdout
        start = out.find("{")
        if start < 0:
            raise RuntimeError(f"Rust produced no JSON. stderr: {r.stderr[-300:]}")
        return json.loads(out[start:])
    finally:
        os.remove(tmp)


def extract_onfarm_lci(result: dict) -> tuple[list[dict], list[str]]:
    """From a Rust result, return (on_farm_lci, notes). Keeps direct field emissions,
    drops upstream production and pre-aggregated CO2-eq."""
    inv = (result.get("results") or {}).get("lci_inventory") or result.get("lci_inventory") or []
    onfarm, notes, dropped, dropped_energy = [], [], 0, 0
    for item in inv:
        sub = item.get("substance", "")
        src = (item.get("source") or "").lower()
        if "equivalent" in sub.lower():
            continue                                    # pre-aggregated, already CO2-eq
        if any(mk in src for mk in _UPSTREAM_MARKERS):
            dropped += 1                                # upstream -> supply-chain solver
            continue
        # Drop on-farm fuel/electricity combustion CO2 — the supply-chain solver's ecoinvent
        # diesel-burning and electricity processes already include these emissions.
        if sub == "Carbon dioxide (CO2)" and any(mk in src for mk in _ENERGY_COMBUSTION_MARKERS):
            dropped_energy += 1
            continue
        key = SUBSTANCE_MAP.get(sub)
        if not key:
            notes.append(f"unmapped Rust flow '{sub}' (source: {item.get('source')})")
            continue
        onfarm.append({"substance": key, "quantity": item.get("quantity", 0.0),
                       "unit": item.get("unit")})
    if dropped:
        notes.append(f"dropped {dropped} upstream-production flow(s) (covered by supply-chain solver)")
    if dropped_energy:
        notes.append(f"dropped {dropped_energy} on-farm fuel/electricity CO2 flow(s) "
                     "(combustion covered by supply-chain solver, avoids double-count)")
    return onfarm, notes


def onfarm_lci_from_assessment(assessment: dict) -> tuple[list[dict], list[str]]:
    """Convenience: run the kernel and extract the on-farm LCI in one call."""
    return extract_onfarm_lci(run_kernel(assessment))


if __name__ == "__main__":
    # Demo the extraction on a SIMULATED Rust inventory (proves parse/map/filter without
    # needing a full comprehensive input). Real runs use run_kernel() on a farm assessment.
    simulated = {"results": {"lci_inventory": [
        {"substance": "Dinitrogen monoxide (N2O)", "quantity": 0.0031, "unit": "kg",
         "compartment": "air", "source": "Direct N2O emissions from Urea application"},
        {"substance": "Dinitrogen monoxide (N2O) - indirect", "quantity": 0.0008, "unit": "kg",
         "compartment": "air", "source": "Indirect N2O emissions from Urea (volatilization/leaching)"},
        {"substance": "Carbon dioxide (CO2)", "quantity": 1.34, "unit": "kg",
         "compartment": "air", "source": "Diesel consumption for farm operations (ESTIMATED)"},
        {"substance": "Carbon dioxide (CO2)", "quantity": 0.045, "unit": "kg",
         "compartment": "air", "source": "Production and transport of Urea"},   # DROP (upstream)
        {"substance": "Phosphate rock", "quantity": 0.02, "unit": "kg",
         "compartment": "resource", "source": "Phosphate mining for NPK production"},  # DROP
        {"substance": "Nitrate (NO3-)", "quantity": 0.012, "unit": "kg",
         "compartment": "water", "source": "Nitrate leaching from Urea application"},
        {"substance": "Land occupation, annual crop", "quantity": 1.0, "unit": "m2*a",
         "compartment": "resource", "source": "Land use for Maize"},
    ]}}
    lci, notes = extract_onfarm_lci(simulated)
    print("on-farm LCI (direct field emissions kept):")
    for f in lci:
        print("  ", f)
    print("\nnotes:", notes)
    print("\nbinary present:", _binary())
