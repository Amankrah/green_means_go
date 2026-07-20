#!/usr/bin/env python3
"""Unit tests for Ghana regional benchmark overlay math."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from regional_benchmark import compute_regional_benchmark


def test_maize_yield_vs_rainfed_guide():
    assessment = {
        "country": "Ghana",
        "region": "GH",
        "foods": [{
            "name": "Maize",
            "quantity_kg": 3000,
            "area_allocated": 2.0,
        }],
    }
    bench = compute_regional_benchmark(
        assessment,
        midpoints={"Land use": {"value": 6.67, "unit": "m2a crop-eq per kg"}},
    )
    assert bench is not None
    crop = bench["crops"][0]
    assert crop["guide_yield_kg_per_ha"] == 1500
    assert crop["actual_yield_kg_per_ha"] == 1500
    assert crop["yield_ratio_vs_guide"] == pytest.approx(1.0)

    guide_land = crop["guide_land_m2_per_kg"]
    assert guide_land == pytest.approx(10000 / 1500)
    agg_guide_land = bench["aggregate"]["guide_land_m2_per_kg"]
    assert bench["aggregate"]["land_ratio_vs_guide"] == pytest.approx(6.67 / agg_guide_land)


def test_non_ghana_returns_none():
    assert compute_regional_benchmark({"country": "Canada", "region": "CA", "foods": []}) is None


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
