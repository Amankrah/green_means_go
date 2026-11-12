#!/usr/bin/env python3
"""Irrigation water is counted once: one volume (engine/inputs.irrigation_water) replaces the
kernel default, water_scarcity books the consumed share on the regional AWARE flow, and
farm_flows only re-labels the withdrawal by source (characterisation-neutral)."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

from orchestrator import _irrigation_override  # noqa: E402
import farm_flows as ff  # noqa: E402

DB = ROOT.parent / "data" / "canonical" / "lca_engineer.sqlite"


def _farm(m3=None, system="Sprinkler"):
    wm = {"irrigation_system": system, "water_source": ["Borehole"]}
    if m3 is not None:
        wm["irrigation_water_m3"] = m3
    return {"country": "Nigeria", "region": "NG",
            "foods": [{"name": "Rice", "area_allocated": 2.0, "quantity_kg": 8000}],
            "management_practices": {"water_management": wm}}


def test_measured_volume_replaces_kernel_water():
    lci = [{"substance": "water", "quantity": 16000.0, "unit": "m3", "source": "generic"},
           {"substance": "N2O", "quantity": 1.0, "unit": "kg"}]
    out, notes = _irrigation_override(lci, _farm(m3=5000))
    water = [f for f in out if f["substance"] == "water"]
    assert len(water) == 1 and water[0]["quantity"] == 5000
    assert water[0]["source"] == "sprinkler"
    assert any(f["substance"] == "N2O" for f in out)
    assert "16000" in notes[0] and "measured" in notes[0]


def test_rainfed_keeps_kernel_flows():
    lci = [{"substance": "N2O", "quantity": 1.0, "unit": "kg"}]
    a = _farm(system="None (Rainfed)")
    a["management_practices"]["water_management"]["water_source"] = ["Rainfall only"]
    out, notes = _irrigation_override(lci, a)
    assert out == lci and notes == []


@pytest.mark.skipif(not DB.exists(), reason="canonical store not present")
def test_farm_flows_adds_no_consumption_flow():
    conn = sqlite3.connect(str(DB))
    try:
        flows, _, replaces = ff.extra_flows(_farm(m3=5000), conn, None)
    finally:
        conn.close()
    assert replaces
    names = {f["name"] for f in flows}
    assert not any("evapotranspired" in n or n == "Water" for n in names)
    assert sum(f["amount"] for f in flows if f["name"].startswith("Water, well")) == pytest.approx(5000)
