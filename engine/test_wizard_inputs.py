"""Every farm-wizard / processing field that implies a flow must reach the inventory (WS2).

Pure extraction tests (no matcher, no Rust): they check that each field changes the
purchased-input list or the extra elementary flows, with cited defaults when blank.
"""
from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path

import pytest

from engine import crop_defaults as cd
from engine import energy_carriers as ec
from engine import pesticides as pz
from engine.conversion_ratios import RATIOS, default_raw_input
from engine.inputs import extract_purchased_inputs, irrigation_water, pumping_declared
from engine.process_inputs import extract_processing_inputs, processing_water_withdrawals

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "canonical" / "lca_engineer.sqlite"


def _farm(**over):
    base = {
        "country": "Ghana", "region": "GH",
        "foods": [{"id": "c1", "name": "Maize", "category": "Cereals", "quantity_kg": 5000,
                   "area_allocated": 2.0, "seasonal_factor": "WetSeason"}],
        "management_practices": {
            "soil_management": {"uses_compost": False},
            "fertilization": {"uses_fertilizers": False, "fertilizer_applications": []},
            "water_management": {"water_source": ["Rainfall only"], "irrigation_system": "None (Rainfed)"},
            "pest_management": {"pesticides": []},
        },
        "equipment_energy": {"equipment": [], "energy_sources": [], "fuel_consumption": []},
    }
    for k, v in over.items():
        base[k] = v
    return base


def _by_kind(inputs, kind):
    return [i for i in inputs if i.get("kind") == kind]


# ---- pesticides ---------------------------------------------------------------------------

def test_pesticides_used_alias_and_ai_mass():
    a = _farm()
    a["management_practices"]["pest_management"] = {"pesticides_used": [
        {"pesticide_type": "Herbicide", "active_ingredient": "Glyphosate", "application_rate": 3.0,
         "applications_per_season": 1}]}
    inputs, _ = extract_purchased_inputs(a)
    p = _by_kind(inputs, "pesticide")
    assert len(p) == 1
    assert p[0]["match_as"] == "market for glyphosate"
    assert p[0]["amount"] == pytest.approx(3.0 * 2.0 * 0.360)   # 360 g/L SL
    assert p[0]["unit"] == "kg"


def test_pesticide_user_content_and_unknown_ai_conservative():
    rows, notes = pz.applications({"management_practices": {"pest_management": {"pesticides": [
        {"pesticide_type": "Insecticide", "active_ingredient": "Lambda-cyhalothrin",
         "application_rate": 1.0, "applications_per_season": 2, "active_ingredient_content": 0.05},
        {"pesticide_type": "Fungicide", "active_ingredient": "Mysterycide",
         "application_rate": 1.0, "applications_per_season": 1}]}}}, 1.0)
    assert rows[0]["kg_ai"] == pytest.approx(0.1) and rows[0]["dataset"] == "market for pyrethroid-compound"
    assert rows[1]["kg_ai"] == pytest.approx(1.0) and rows[1]["dataset"] == pz.GENERIC_DATASET
    assert any("conservative" in n for n in notes)


@pytest.mark.skipif(not DB.exists(), reason="canonical store not available")
def test_pesticide_soil_emission_is_characterised_for_toxicity():
    from ingestion.query import CanonicalQuery
    q = CanonicalQuery(DB)
    try:
        rows, _ = pz.applications({"management_practices": {"pest_management": {"pesticides": [
            {"pesticide_type": "Insecticide", "active_ingredient": "Cypermethrin",
             "application_rate": 1.0, "applications_per_season": 1}]}}}, 1.0)
        flows, notes = pz.field_emission_flows(q.conn, rows)
        assert len(flows) == 1 and not notes
        inv = {f["uid"]: {"name": f["name"], "unit": f["unit"], "amount": f["amount"]} for f in flows}
        impacts = q.characterize_flows(inv, "ReCiPe 2016 v1.03, midpoint (H)")
        tox = {k: v["value"] for k, v in impacts.items() if "ecotox" in k.lower()}
        assert tox and any(v > 0 for v in tox.values())
    finally:
        q.close()


# ---- energy carriers ----------------------------------------------------------------------

def test_lpg_is_lpg_not_diesel_and_firewood_is_biomass_heat():
    a = _farm()
    a["equipment_energy"]["fuel_consumption"] = [
        {"fuel_type": "Liquefied Petroleum Gas (LPG)", "monthly_consumption": 10, "primary_use": "Drying"}]
    a["equipment_energy"]["energy_sources"] = [
        {"energy_type": "Firewood", "monthly_consumption": 100, "primary_use": "Drying"},
        {"energy_type": "Charcoal", "monthly_consumption": 20, "primary_use": "Cooking"},
        {"energy_type": "Biogas", "monthly_consumption": 30, "primary_use": "Cooking"}]
    inputs, _ = extract_purchased_inputs(a)
    lpg = next(i for i in inputs if i.get("fuel") == "lpg")
    assert lpg["match_as"] == "propane, burned in building machine"
    assert lpg["amount"] == pytest.approx(120 * 47.3 * 0.54)
    wood = next(i for i in inputs if i.get("fuel") == "firewood")
    assert wood["unit"] == "MJ" and wood["amount"] == pytest.approx(1200 * 15.6)
    assert wood["kind"] == "fuel"
    char = next(i for i in inputs if i.get("fuel") == "charcoal")
    assert char["unit"] == "kg" and char["amount"] == pytest.approx(240)
    bio = next(i for i in inputs if i.get("fuel") == "biogas")
    assert bio["unit"] == "m3" and bio["amount"] == pytest.approx(360)
    assert not any(i.get("fuel") == "diesel" and not i.get("estimated") for i in inputs)


def test_solar_is_pv_dataset_not_grid_and_not_calibrated():
    a = _farm()
    a["equipment_energy"]["energy_sources"] = [
        {"energy_type": "Solar Panels", "monthly_consumption": 50, "primary_use": "Pumping"}]
    inputs, _ = extract_purchased_inputs(a)
    pv = next(i for i in inputs if i.get("fuel") == "solar")
    assert pv["kind"] == "electricity_onsite"            # grid_calibration acts on "electricity" only
    assert "photovoltaic" in pv["match_as"] and pv["amount"] == pytest.approx(600)


def test_generator_counted_once_when_duplicated_in_fuel():
    a = _farm()
    a["equipment_energy"]["fuel_consumption"] = [
        {"fuel_type": "Diesel", "monthly_consumption": 220, "primary_use": "Irrigation pumping"}]
    a["equipment_energy"]["energy_sources"] = [
        {"energy_type": "Diesel Generator", "monthly_consumption": 220, "primary_use": "Irrigation pumping"}]
    inputs, notes = extract_purchased_inputs(a)
    assert len([i for i in inputs if i.get("fuel") == "diesel" and not i.get("estimated")]) == 1
    assert any("counted once" in n for n in notes)
    a["equipment_energy"]["energy_sources"][0]["primary_use"] = "Lighting"
    inputs, _ = extract_purchased_inputs(a)
    gen = [i for i in inputs if "generating set" in (i.get("match_as") or "")]
    assert len(gen) == 1 and gen[0]["amount"] == pytest.approx(220 * 12 * 38.7)


def test_equipment_power_source_hours_and_efficiency():
    a = _farm()
    a["equipment_energy"]["equipment"] = [
        {"equipment_type": "Animal-drawn implements", "power_source": "Animal power", "age": 3, "hours_per_year": 200},
        {"equipment_type": "Sprayer", "power_source": "Solar powered", "age": 1, "hours_per_year": 50},
        {"equipment_type": "Water Pump", "power_source": "Petrol engine", "age": 2, "hours_per_year": 100,
         "fuel_efficiency": 1.5},
        {"equipment_type": "Medium Tractor (40-100HP)", "power_source": "Diesel engine", "age": 5,
         "hours_per_year": 100}]
    inputs, _ = extract_purchased_inputs(a)
    petrol = next(i for i in inputs if i.get("fuel") == "petrol")
    assert petrol["unit"] == "kg" and petrol["amount"] == pytest.approx(150 * 34.2 / 44.3)
    diesel = next(i for i in inputs if i.get("fuel") == "diesel" and i.get("source_equipment"))
    assert diesel["estimated"] is True                                       # ASABE D497 class estimate
    assert diesel["native_amount"] == pytest.approx(0.223 * 70 * 0.7457 * 100)
    # metered diesel suppresses the equipment estimate for the same carrier
    a["equipment_energy"]["fuel_consumption"] = [
        {"fuel_type": "Diesel", "monthly_consumption": 10, "primary_use": "Tillage"}]
    inputs, _ = extract_purchased_inputs(a)
    assert not [i for i in inputs if i.get("fuel") == "diesel" and i.get("source_equipment")]


# ---- fertiliser, seed, irrigation, logistics ---------------------------------------------

def test_ammonium_sulfate_and_can_steered():
    a = _farm()
    a["management_practices"]["fertilization"] = {"uses_fertilizers": True, "fertilizer_applications": [
        {"fertilizer_type": "Ammonium Sulfate", "npk_ratio": "21-0-0", "application_rate": 100, "applications_per_season": 1},
        {"fertilizer_type": "Calcium Ammonium Nitrate (CAN)", "npk_ratio": "27-0-0", "application_rate": 50, "applications_per_season": 1}]}
    inputs, _ = extract_purchased_inputs(a)
    f = _by_kind(inputs, "fertiliser")
    assert f[0]["match_as"] == "market for ammonium sulfate"
    assert f[1]["match_as"] == "market for calcium ammonium nitrate"


def test_seed_default_by_crop_then_category_and_user_override():
    assert cd.seed_default({"name": "Maize", "category": "Cereals"})["kg_per_ha"] == 25.0
    # unrecognised crop: the category decides
    via_cat = cd.seed_default({"name": "Fonio", "category": "Legumes"})
    assert via_cat["match_as"] == "market for pea seed, for sowing" and "category" in via_cat["source"]
    assert cd.seed_default({"name": "Fonio", "category": "Cereals"})["match_as"] == "market for maize seed, for sowing"
    assert cd.seed_default({"name": "Cassava", "category": "Roots"}) is None
    user = cd.seed_default({"name": "Rice", "category": "Cereals", "seed_rate_kg_per_ha": 40})
    assert user["kg_per_ha"] == 40 and user["estimated"] is False
    inputs, _ = extract_purchased_inputs(_farm())
    seed = _by_kind(inputs, "seed")[0]
    assert seed["amount"] == pytest.approx(50.0) and seed["estimated"] is True


def test_irrigation_default_volume_pumping_and_sources():
    a = _farm()
    a["foods"][0]["seasonal_factor"] = "DrySeason"
    a["management_practices"]["water_management"] = {"water_source": ["Borehole"],
                                                     "irrigation_system": "Drip Irrigation"}
    w = irrigation_water(a)
    assert w["m3"] == pytest.approx(650 * 10 * 2.0 * 1.0 / 0.90) and w["estimated"]
    inputs, _ = extract_purchased_inputs(a)
    pump = _by_kind(inputs, "irrigation_energy")
    assert len(pump) == 2 and all("water pump operation" in p["match_as"] for p in pump)
    assert sum(p["amount"] for p in pump) == pytest.approx(w["m3"] * (0.3003 + 0.5255))
    # declared pump -> no default pumping energy
    a["equipment_energy"]["equipment"] = [{"equipment_type": "Water Pump", "power_source": "Electric",
                                          "age": 1, "hours_per_year": 300}]
    assert pumping_declared(a) == {"power": "electric"}
    inputs, _ = extract_purchased_inputs(a)
    assert not _by_kind(inputs, "irrigation_energy")
    # measured volume wins; municipal share is purchased tap water
    a["management_practices"]["water_management"].update(
        {"irrigation_water_m3": 1000.0, "water_source": ["Borehole", "Municipal Water Supply"]})
    inputs, _ = extract_purchased_inputs(a)
    tap = _by_kind(inputs, "water")[0]
    assert tap["match_as"] == "market for tap water" and tap["amount"] == pytest.approx(500 * 1000)


@pytest.mark.skipif(not DB.exists(), reason="canonical store not available")
def test_irrigation_withdrawal_flows_by_source():
    from engine.farm_flows import extra_flows
    a = _farm()
    a["management_practices"]["water_management"] = {"water_source": ["Borehole", "River/Stream"],
                                                     "irrigation_system": "Sprinkler System",
                                                     "irrigation_water_m3": 800.0}
    conn = sqlite3.connect(str(DB))
    try:
        flows, _, replaces = extra_flows(a, conn)
    finally:
        conn.close()
    assert replaces is True
    names = {f["name"]: f["amount"] for f in flows}
    assert names["Water, well, in ground"] == 400.0 and names["Water, river"] == 400.0
    # consumption is booked once, by water_scarcity on the regional AWARE flow, not here
    assert not any(n.startswith("Water (evapotranspired") for n in names)


def test_logistics_packaging_and_transport():
    a = _farm(logistics={"packaging_material": "Polypropylene sacks", "distance_to_market_km": 40,
                         "market_transport_mode": "Pickup truck"})
    a["management_practices"]["fertilization"] = {"uses_fertilizers": True, "fertilizer_applications": [
        {"fertilizer_type": "Urea", "npk_ratio": "46-0-0", "application_rate": 100, "applications_per_season": 1}]}
    inputs, notes = extract_purchased_inputs(a)
    pack = _by_kind(inputs, "packaging")[0]
    assert pack["amount"] == pytest.approx(5.0 * 2.0)                         # 5 t x 2 kg/t
    tr = {i["name"]: i for i in _by_kind(inputs, "transport")}
    inbound = tr["transport of inputs to farm"]
    t_in = (200 + 50.0) / 1000.0                                               # urea + maize seed
    assert inbound["amount"] == pytest.approx(t_in * 230.0) and inbound["estimated"]
    assert tr["transport of harvest to first point of sale"]["amount"] == pytest.approx(5.0 * 40)
    assert any("first point of sale" in n for n in notes)


# ---- processing -------------------------------------------------------------------------

def _proc(**ops):
    return {"country": "Ghana", "region": "GH",
            "facility_profile": {"facility_name": "f", "company_name": "c", "facility_type": "PalmOilMill",
                                 "processing_capacity": 10, "operational_days_per_year": 200},
            "processing_operations": ops,
            "processed_products": [{"id": "p1", "name": "CPO", "product_type": "PalmOil",
                                    "annual_production": 100.0, "raw_material_inputs": []}]}


def test_default_conversion_ratio_when_raw_material_blank():
    inputs, notes, _ = extract_processing_inputs(_proc(raw_material_sourcing={
        "storage_practices": {"storage_loss_percentage": 0.0}}))
    raw = _by_kind(inputs, "raw_material")[0]
    assert "palm" in raw["name"].lower() and raw["estimated"]
    assert raw["amount"] == pytest.approx(100.0 * 1000.0 / RATIOS["PalmOil"]["extraction_rate"])
    for ptype in ("CocoaPowder", "FlourMaize", "RiceProcessed", "FlourCassava"):
        assert default_raw_input({"product_type": ptype}, None)["source"]
    # "Other" falls back to the facility type
    assert default_raw_input({"product_type": "Other"}, "CocoaProcessing")["product_type_used"] == "CocoaPowder"
    # storage loss raises the defaulted purchase
    inputs, _, _ = extract_processing_inputs(_proc(raw_material_sourcing={
        "storage_practices": {"storage_loss_percentage": 10.0}}))
    assert _by_kind(inputs, "raw_material")[0]["amount"] == pytest.approx(500000.0 / 0.9)


def test_several_fuel_streams_and_genset_electricity():
    inputs, _, _ = extract_processing_inputs(_proc(energy_management={
        "primary_energy_source": "DieselGenerator", "monthly_electricity_consumption": 1000,
        "fuel_streams": [{"fuel_type": "Palm kernel shell", "monthly_consumption": 2000, "unit": "kg"},
                         {"fuel_type": "Diesel", "monthly_consumption": 100, "use": "backup generator"}]}))
    fuels = {i["name"]: i for i in inputs if i.get("kind") in ("fuel", "heat_fuel")}
    assert fuels["Palm kernel shell (facility fuel)"]["amount"] == pytest.approx(24000 * 11.6)
    assert "generating set" in fuels["Diesel (facility fuel)"]["match_as"]
    gen = fuels["diesel generator electricity (on-site)"]
    assert gen["native_amount"] == pytest.approx(12000 * 0.30)
    assert not [i for i in inputs if i.get("kind") == "electricity"]


def test_water_source_treatment_wastewater_waste_and_transport():
    req = _proc(water_management={"water_source": ["Borehole"], "monthly_water_consumption": 10,
                                  "water_treatment": "BasicFiltration", "wastewater_treatment": "None"},
                waste_management={"solid_waste_generation": 10, "organic_waste_percentage": 60,
                                  "waste_disposal_method": "Landfill",
                                  "byproduct_utilization": [{"byproduct_name": "fibre",
                                                             "utilization_method": "boiler fuel",
                                                             "percentage_utilized": 50}]},
                raw_material_sourcing={"local_sourcing_percentage": 50})
    inputs, notes, _ = extract_processing_inputs(req)
    assert processing_water_withdrawals(req) == [("Water, well, in ground", 120.0)]
    assert not _by_kind(inputs, "water") and not _by_kind(inputs, "wastewater")
    assert any("untreated" in n for n in notes)
    waste = {i["name"]: i["amount"] for i in _by_kind(inputs, "waste")}
    assert waste["solid waste (organic), landfill"] == pytest.approx(10 * 200 * 0.5 * 0.6)
    assert waste["solid waste (inorganic), landfill"] == pytest.approx(10 * 200 * 0.5 * 0.4)
    tr = _by_kind(inputs, "transport")[0]
    assert tr["estimate_meta"]["basis"].startswith("140 km")                 # 0.5x50 + 0.5x230
    # chemical treatment -> treated-water dataset, no separate withdrawal
    req["processing_operations"]["water_management"]["water_treatment"] = "ChemicalTreatment"
    inputs, _, _ = extract_processing_inputs(req)
    assert _by_kind(inputs, "water")[0]["match_as"] == "market for water, decarbonised"
    assert processing_water_withdrawals(req) == []


def test_renewable_share_is_pv_not_zero():
    inputs, _, _ = extract_processing_inputs(_proc(energy_management={
        "monthly_electricity_consumption": 1000, "renewable_energy_percentage": 25}))
    pv = next(i for i in inputs if i.get("fuel") == "solar")
    grid = next(i for i in inputs if i.get("kind") == "electricity")
    assert pv["amount"] == pytest.approx(3000) and grid["amount"] == pytest.approx(9000)


def test_carrier_table_sources_present():
    for carrier, units in ec.LHV.items():
        for unit, (val, src) in units.items():
            assert val > 0 and src
    assert ec.carrier_of("Liquefied Petroleum Gas (LPG)") == "lpg"
    assert ec.carrier_of("Diesel engine") == "diesel"


@pytest.mark.skipif(not DB.exists(), reason="canonical store not available")
def test_farm_flows_apply_replaces_rust_water_and_recharacterises():
    """apply() swaps the Rust generic water flow for the source-specific withdrawal and keeps
    per-source flows, the merged inventory and the totals consistent."""
    from types import SimpleNamespace
    from engine import farm_flows

    conn = sqlite3.connect(str(DB))

    class Q:
        def __init__(self):
            self.conn = conn

        def characterize_flows(self, flows, method):
            return {"total": {"value": sum(r["amount"] for r in flows.values()), "unit": "x"}}

    class FMap:
        def resolve(self, key):
            return {"water": "RUST_WATER", "N2O": "N2O_UID", "CH4_bio": "CH4_UID"}.get(key)

    eng = SimpleNamespace(q=Q(), fmap=FMap(), method="m")
    res = SimpleNamespace(
        contribution_flows_by_source={farm_flows.FIELD_LABEL: {
            "RUST_WATER": {"name": "water", "unit": "m3", "amount": 999.0}}},
        inventory={"RUST_WATER": {"name": "water", "unit": "m3", "amount": 999.0},
                   "OTHER": {"name": "x", "unit": "kg", "amount": 1.0}},
        contribution={}, contribution_by_source={}, impacts={}, notes=[])
    a = _farm()
    a["management_practices"]["water_management"] = {"water_source": ["Borehole"],
                                                     "irrigation_system": "Drip Irrigation",
                                                     "irrigation_water_m3": 300.0}
    a["management_practices"]["soil_management"] = {"uses_compost": True, "compost_source": "Farm-made compost",
                                                    "compost_application_rate": 1.0}
    try:
        farm_flows.apply(res, eng, a)
    finally:
        conn.close()
    field = res.contribution_flows_by_source[farm_flows.FIELD_LABEL]
    assert "RUST_WATER" not in field and "RUST_WATER" not in res.inventory
    well = [r for r in field.values() if r["name"] == "Water, well, in ground"]
    assert well and well[0]["amount"] == pytest.approx(300.0)
    assert not [r for r in field.values() if r["name"].startswith("Water (evapotranspired")]
    assert field["CH4_UID"]["amount"] == pytest.approx(2000.0 * 0.004)     # 1 t/ha x 2 ha
    assert field["N2O_UID"]["amount"] == pytest.approx(2000.0 * 0.0003)
    assert res.impacts["total"]["value"] == pytest.approx(sum(r["amount"] for r in res.inventory.values()))
    assert res.contribution["on_farm"] == res.contribution_by_source[farm_flows.FIELD_LABEL]


def test_zero_applications_means_zero_and_no_area_is_a_warning():
    """0 applications per season used to be read as 1 here while the kernel read 0."""
    a = {"foods": [{"name": "Maize", "category": "Cereals", "quantity_kg": 1000, "area_allocated": 2.0}],
         "management_practices": {"fertilization": {"uses_fertilizers": True, "fertilizer_applications": [
             {"fertilizer_type": "Urea", "npk_ratio": "46-0-0", "application_rate": 100,
              "applications_per_season": 0}]},
             "pest_management": {"pesticides": [{"pesticide_type": "Herbicide", "active_ingredient": "Glyphosate",
                                                 "application_rate": 2.0, "applications_per_season": 0}]}}}
    inputs, notes = extract_purchased_inputs(a)
    assert not [i for i in inputs if i.get("kind") in ("fertiliser", "pesticide")]
    assert any("0 applications per season" in n for n in notes)

    a["management_practices"]["fertilization"]["fertilizer_applications"][0]["applications_per_season"] = 1
    a["management_practices"]["pest_management"]["pesticides"][0]["applications_per_season"] = 1
    a["foods"][0].pop("area_allocated")
    inputs, notes = extract_purchased_inputs(a)
    assert not [i for i in inputs if i.get("kind") in ("fertiliser", "pesticide")]
    warn = [n for n in notes if n.startswith(pz.WARNING_PREFIX)]
    assert any("fertiliser" in n and "no crop area" in n for n in warn)
    assert any("pesticide" in n and "no crop area" in n for n in warn)


def test_negative_rates_are_clamped_with_a_warning_not_credited():
    a = {"foods": [{"name": "Maize", "category": "Cereals", "quantity_kg": 1000, "area_allocated": 2.0}],
         "management_practices": {
             "fertilization": {"uses_fertilizers": True, "fertilizer_applications": [
                 {"fertilizer_type": "Urea", "application_rate": -100, "applications_per_season": 1}]},
             "soil_management": {"uses_compost": True, "compost_source": "Purchased compost",
                                 "compost_application_rate": -5}},
         "equipment_energy": {"fuel_consumption": [{"fuel_type": "Diesel", "monthly_consumption": -10}],
                              "equipment": [{"equipment_type": "Tractor", "power_source": "Diesel engine",
                                             "hours_per_year": -3}]}}
    inputs, notes = extract_purchased_inputs(a)
    assert all(i["amount"] >= 0 for i in inputs)
    assert not [i for i in inputs if i.get("kind") in ("fertiliser", "compost")]
    assert sum(1 for n in notes if n.startswith(pz.WARNING_PREFIX) and "negative" in n) >= 3
