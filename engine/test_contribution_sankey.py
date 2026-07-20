"""Snapshot-style tests for contribution Sankey top-N ordering."""
from __future__ import annotations

from engine.contribution_sankey import build_contribution_sankey


def _fixture_cbs() -> dict:
    return {
        "Urea": {"Global warming": {"value": 0.30, "unit": "kg CO2-eq per kg"}},
        "Diesel, burned in agricultural machinery": {
            "Global warming": {"value": 0.45, "unit": "kg CO2-eq per kg"}
        },
        "Field emissions (on-farm)": {
            "Global warming": {"value": 0.20, "unit": "kg CO2-eq per kg"},
            "Land use": {"value": 9.0, "unit": "m2a crop-eq per kg"},
        },
        "Compost": {"Land use": {"value": 0.5, "unit": "m2a crop-eq per kg"}},
        "Seed maize": {"Land use": {"value": 0.2, "unit": "m2a crop-eq per kg"}},
    }


def test_top3_gwp_ordering_snapshot():
    sankey = build_contribution_sankey(_fixture_cbs(), top_n=3)
    gwp = sankey["categories"]["Global warming"]
    assert [s["source"] for s in gwp["sources"]] == [
        "Diesel, burned in agricultural machinery",
        "Urea",
        "Field emissions (on-farm)",
    ]
    assert gwp["sources"][0]["rank"] == 1
    assert gwp["sources"][0]["share"] > gwp["sources"][1]["share"]


def test_top3_land_ordering_snapshot():
    sankey = build_contribution_sankey(_fixture_cbs(), top_n=3)
    land = sankey["categories"]["Land use"]
    assert [s["source"] for s in land["sources"]] == [
        "Field emissions (on-farm)",
        "Compost",
        "Seed maize",
    ]


def test_climate_change_alias_maps_to_gwp():
    cbs = {
        "On-farm": {"Climate change": {"value": 1.0, "unit": "kg CO2-eq"}},
        "Input A": {"Climate change": {"value": 2.0, "unit": "kg CO2-eq"}},
    }
    sankey = build_contribution_sankey(cbs, top_n=2)
    assert sankey["categories"]["Global warming"]["sources"][0]["source"] == "Input A"
