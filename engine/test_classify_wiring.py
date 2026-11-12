#!/usr/bin/env python3
"""engine.llm.classify is wired into the free-text fallbacks of input extraction: it only
renames an input onto the controlled vocabulary, never supplies a number, and runs offline
on its deterministic synonym table (GMG_LLM=0)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

from engine.inputs import carrier_or_classify, extract_purchased_inputs  # noqa: E402
from engine.process_inputs import _raw_material_match  # noqa: E402


def test_trade_fuel_names_resolve_offline(monkeypatch):
    monkeypatch.setenv("GMG_LLM", "0")
    notes = []
    assert carrier_or_classify("AGO", notes) == "diesel"
    assert carrier_or_classify("PMS", notes) == "petrol"
    assert any("AGO" in n and "diesel" in n for n in notes)
    assert carrier_or_classify("zzz", []) is None


def test_unrecognised_fuel_still_falls_back_with_a_note(monkeypatch):
    monkeypatch.setenv("GMG_LLM", "0")
    a = {"country": "Ghana", "foods": [{"name": "Maize", "area_allocated": 1.0, "quantity_kg": 2000}],
         "equipment_energy": {"fuel_consumption": [
             {"fuel_type": "AGO", "monthly_consumption": 10, "unit": "L"},
             {"fuel_type": "mystery fuel", "monthly_consumption": 5, "unit": "L"}]}}
    inputs, notes = extract_purchased_inputs(a)
    assert any("read as diesel" in n for n in notes)
    assert any("mystery fuel" in n and "diesel" in n for n in notes)


def test_local_raw_material_name_maps_to_hint(monkeypatch):
    monkeypatch.setenv("GMG_LLM", "0")
    hint, _ = _raw_material_match("garden egg")
    assert "aubergine" in hint
    assert _raw_material_match("Something odd") == ("Something odd production", False)
