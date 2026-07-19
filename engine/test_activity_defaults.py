#!/usr/bin/env python3
"""Unit tests for Ghana farm activity defaults (Tier A inventory defaults)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))

try:
    from activity_defaults import resolve_energy_defaults
    from inputs import extract_purchased_inputs
    from rust_kernel import extract_onfarm_lci
except ImportError:
    from engine.activity_defaults import resolve_energy_defaults
    from engine.inputs import extract_purchased_inputs
    from engine.rust_kernel import extract_onfarm_lci


def _base(*, production_system="Rainfed", equipment=None, energy_sources=None,
          fuel_consumption=None, irrigation_system=None, country="Ghana") -> dict:
    return {
        "country": country,
        "region": "GH" if country == "Ghana" else "CA",
        "foods": [{"name": "Maize", "quantity_kg": 3000, "area_allocated": 2.0,
                   "production_system": production_system}],
        "management_practices": {
            "water_management": {
                "irrigation_system": irrigation_system or (
                    "Flood Irrigation" if production_system == "Irrigated" else "None (Rainfed)"
                ),
            },
        },
        "equipment_energy": {
            "equipment": equipment or [],
            "energy_sources": energy_sources or [],
            "fuel_consumption": fuel_consumption or [],
        },
    }


def test_rainfed_manual_zero_energy() -> None:
    r = resolve_energy_defaults(_base())
    assert r is not None
    assert r["diesel_l_per_ha"] == 0
    assert r["electricity_kwh_per_ha"] == 0
    assert r["row_id"] == "rainfed_manual"
    inputs, notes = extract_purchased_inputs(_base())
    assert not any(i.get("kind") == "fuel" for i in inputs)
    assert not any(i.get("kind") == "electricity" for i in inputs)
    assert any("used activity defaults" in n for n in notes)
    assert any("0 L diesel" in n for n in notes)
    print("[ok] rainfed + manual -> 0/0 energy estimates")


def test_irrigated_mechanized_nonzero() -> None:
    a = _base(
        production_system="Irrigated",
        irrigation_system="Flood Irrigation",
        equipment=[{
            "equipment_type": "Tractor", "power_source": "Diesel",
            "age": 5, "hours_per_year": 100, "fuel_efficiency": None,
        }],
    )
    r = resolve_energy_defaults(a)
    assert r is not None
    assert r["diesel_l_per_ha"] > 0
    assert r["diesel_l_per_ha"] <= 80
    inputs, notes = extract_purchased_inputs(a)
    fuel = [i for i in inputs if i.get("kind") == "fuel"]
    assert len(fuel) == 1
    assert fuel[0].get("estimated") is True
    assert fuel[0]["amount"] > 0
    assert any("estimated diesel" in n for n in notes)
    print(f"[ok] irrigated + mechanized -> {r['diesel_l_per_ha']} L/ha within bounds")


def test_measured_fuel_skips_defaults() -> None:
    a = _base(fuel_consumption=[{
        "fuel_type": "Diesel", "monthly_consumption": 10, "primary_use": "ploughing",
    }])
    inputs, notes = extract_purchased_inputs(a)
    fuel = [i for i in inputs if i.get("kind") == "fuel"]
    assert len(fuel) == 1
    assert not fuel[0].get("estimated")
    # Electricity may still come from activity defaults; fuel must not be re-estimated.
    assert not any(i.get("kind") == "fuel" and i.get("estimated") for i in inputs)
    print("[ok] measured fuel is not overwritten by activity defaults")


def test_non_ghana_skips_table() -> None:
    a = _base(country="Canada")
    a["region"] = "CA"
    assert resolve_energy_defaults(a) is None
    inputs, notes = extract_purchased_inputs(a)
    assert not any(i.get("estimated") for i in inputs)
    assert not any("used activity defaults" in n for n in notes)
    print("[ok] non-Ghana assessments skip the Ghana table")


def test_rust_estimated_co2_dropped() -> None:
    simulated = {"results": {"lci_inventory": [
        {"substance": "Carbon dioxide (CO2)", "quantity": 400.0, "unit": "kg",
         "compartment": "air",
         "source": "Diesel consumption for farm operations (ESTIMATED: 160 L/year based on 2 ha)"},
        {"substance": "Carbon dioxide (CO2)", "quantity": 140.0, "unit": "kg",
         "compartment": "air",
         "source": "Grid electricity (ESTIMATED: 400 kWh/year based on 2 ha)"},
        {"substance": "Dinitrogen monoxide (N2O)", "quantity": 0.1, "unit": "kg",
         "compartment": "air", "source": "Direct N2O from Urea"},
    ]}}
    lci, notes = extract_onfarm_lci(simulated)
    assert not any(f.get("substance") == "CO2" for f in lci), f"estimated CO2 leaked: {lci}"
    assert any(f.get("substance") == "N2O" for f in lci)
    assert any("dropped" in n and "fuel/electricity" in n for n in notes)
    print("[ok] legacy Rust ESTIMATED energy CO2 is dropped (supply-chain owns energy)")


def _run_all() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failed += 1
            print(f"[FAIL] {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"[ERROR] {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_all())
