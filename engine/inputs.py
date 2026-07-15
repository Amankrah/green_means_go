#!/usr/bin/env python3
"""
inputs.py — auto-extract the purchased inputs (for the supply-chain solver) from a
submitted farm assessment, so the frontend doesn't pass them separately.

Fertiliser  : application_rate (kg/ha) × applications × total cropped area → kg
Fuel        : monthly litres × 12 → litres/yr → MJ (process ref unit is MJ)
Electricity : monthly kWh × 12 → kWh
"""
from __future__ import annotations

# Lower heating values (MJ per litre) for common farm fuels.
FUEL_MJ_PER_L = {"diesel": 38.7, "petrol": 34.2, "gasoline": 34.2, "kerosene": 37.0, "biodiesel": 33.0}


def _fuel_word(ft: str) -> tuple[str, float]:
    f = (ft or "").lower()
    for k, mj in FUEL_MJ_PER_L.items():
        if k in f:
            word = "diesel" if k == "diesel" else ("petrol" if k in ("petrol", "gasoline") else k)
            return word, mj
    return "diesel", FUEL_MJ_PER_L["diesel"]


def extract_purchased_inputs(assessment: dict) -> tuple[list[dict], list[str]]:
    """Return (purchased_inputs, notes) for the supply-chain solver."""
    inputs, notes = [], []
    foods = assessment.get("foods") or []
    total_area = sum((f.get("area_allocated") or 0) for f in foods)

    mp = assessment.get("management_practices") or {}
    fert = mp.get("fertilization") or {}
    if fert.get("uses_fertilizers"):
        if not total_area:
            notes.append("fertiliser reported but no crop area — cannot scale fertiliser inputs")
        for app in fert.get("fertilizer_applications") or []:
            rate = app.get("application_rate") or 0
            n = app.get("applications_per_season") or 1
            kg = rate * n * total_area
            if kg <= 0:
                continue
            npk = (app.get("npk_ratio") or "").strip()
            name = f"{app.get('fertilizer_type', 'fertiliser')} {npk}".strip() + " fertiliser"
            inputs.append({"name": name, "amount": kg, "unit": "kg", "kind": "fertiliser"})

    ee = assessment.get("equipment_energy") or {}
    fuels = ee.get("fuel_consumption") or []
    if fuels:
        for fu in fuels:
            litres = (fu.get("monthly_consumption") or 0) * 12
            if litres <= 0:
                continue
            word, mj_per_l = _fuel_word(fu.get("fuel_type"))
            inputs.append({"name": f"{word}, burned in agricultural machinery",
                           "amount": litres * mj_per_l, "unit": "MJ", "kind": "fuel"})
    else:
        # fall back to equipment hours × fuel efficiency
        for eq in ee.get("equipment") or []:
            eff = eq.get("fuel_efficiency"); hrs = eq.get("hours_per_year")
            if eff and hrs:
                word, mj_per_l = _fuel_word(eq.get("power_source"))
                inputs.append({"name": f"{word}, burned in agricultural machinery",
                               "amount": eff * hrs * mj_per_l, "unit": "MJ", "kind": "fuel"})

    for en in ee.get("energy_sources") or []:
        et = (en.get("energy_type") or "").lower()
        if "electric" in et or "grid" in et:
            kwh = (en.get("monthly_consumption") or 0) * 12
            if kwh > 0:
                inputs.append({"name": "electricity low voltage", "amount": kwh, "unit": "kWh",
                               "kind": "electricity"})

    if not inputs:
        notes.append("no purchased inputs extracted (no fertiliser/fuel/electricity data)")
    return inputs, notes


def total_production_kg(assessment: dict) -> float:
    return sum((f.get("quantity_kg") or 0) for f in assessment.get("foods") or [])


if __name__ == "__main__":
    demo = {"foods": [{"quantity_kg": 9500, "area_allocated": 5.0},
                      {"quantity_kg": 31500, "area_allocated": 3.5}],
            "management_practices": {"fertilization": {"uses_fertilizers": True,
                "fertilizer_applications": [
                    {"fertilizer_type": "NPK", "npk_ratio": "15-15-15", "application_rate": 250, "applications_per_season": 1},
                    {"fertilizer_type": "Urea", "npk_ratio": "46-0-0", "application_rate": 100, "applications_per_season": 2}]}},
            "equipment_energy": {"fuel_consumption": [{"fuel_type": "Diesel", "monthly_consumption": 150}],
                                 "energy_sources": [{"energy_type": "Grid Electricity", "monthly_consumption": 85}]}}
    inp, notes = extract_purchased_inputs(demo)
    for i in inp:
        print(f"  {i['name']:<42} {i['amount']:>10.1f} {i['unit']}  ({i['kind']})")
    print("total production kg:", total_production_kg(demo), "| notes:", notes)
