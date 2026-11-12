#!/usr/bin/env python3
"""
regional_lcia.py: single entry point the orchestrator calls (one line) to regionalise
the FOREGROUND inventory before characterisation:
  * engine/water_scarcity.py  - AWARE country CF for consumptive irrigation water;
  * engine/land_use_regional.py - EF soil-quality-index country CF for on-farm land.
Both work by re-booking on-farm amounts onto regionalised store flows, so every
downstream characterisation (any method, endpoints, Monte Carlo) stays consistent.
"""
from __future__ import annotations

try:
    from . import water_scarcity, land_use_regional
except ImportError:
    import water_scarcity
    import land_use_regional


def apply(q, region, on_farm_lci, purchased_inputs, onfarm: dict, supply: dict, res, method: str) -> dict:
    return {
        "water": water_scarcity.apply(q, region, on_farm_lci or [], purchased_inputs or [],
                                      onfarm, supply, res, method),
        "land": land_use_regional.apply(q, region, onfarm, res),
    }
