"""Untreated wastewater: measured effluent concentrations -> kg COD/BOD5/N/P to surface water;
no concentrations -> no invented default, disclosed as a data gap."""
from __future__ import annotations

import pytest

from engine.process_inputs import WASTEWATER_SHARE, untreated_effluent_loads


def _req(treatment="None", **conc):
    return {"processing_operations": {"water_management": {
        "monthly_water_consumption": 100.0, "wastewater_treatment": treatment, **conc}}}


def test_loads_from_measured_concentrations():
    loads = {l["name"]: l for l in untreated_effluent_loads(
        _req(effluent_cod_mg_per_l=2000, effluent_total_p_mg_per_l=10))}
    m3 = 100.0 * 12 * WASTEWATER_SHARE
    assert loads["COD, Chemical Oxygen Demand"]["kg"] == pytest.approx(2000 * m3 / 1000)
    assert loads["Phosphorus"]["kg"] == pytest.approx(10 * m3 / 1000)
    assert all(l["compartment"].endswith("Emission to water/surface water") for l in loads.values())
    assert "Nitrogen" not in loads                     # not measured -> not modelled


def test_no_concentrations_or_treated_means_no_flows():
    assert untreated_effluent_loads(_req()) == []
    assert untreated_effluent_loads(_req("BasicSedimentation", effluent_cod_mg_per_l=2000)) == []
