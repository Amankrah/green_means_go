#!/usr/bin/env python3
"""Unit tests for literature-linked ipcc_ef1_scale on field N2O."""
from __future__ import annotations

import sys
from types import SimpleNamespace
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from field_model import adjust_field_emissions, RUST_EF1


def test_ef1_scale_doubles_n2o():
    region = SimpleNamespace(ipcc_n2o_ef1=RUST_EF1, climate_zone="test")
    on_farm = [{"substance": "N2O", "quantity": 1.0, "unit": "kg"}]
    base_assessment = {"foods": [{"name": "Maize", "quantity_kg": 1000, "area_allocated": 1.0}]}

    adjusted_base, _ = adjust_field_emissions(on_farm, base_assessment, region)
    scaled = {**base_assessment, "ipcc_ef1_scale": 2.0}
    adjusted_scaled, notes = adjust_field_emissions(on_farm, scaled, region)

    assert adjusted_base[0]["quantity"] == pytest.approx(1.0)
    assert adjusted_scaled[0]["quantity"] == pytest.approx(2.0)
    assert any("literature-linked EF1 scale" in n for n in notes)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
