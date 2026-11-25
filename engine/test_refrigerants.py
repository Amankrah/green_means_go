"""Refrigerant GWPs: blends recomputed from AR6 component GWPs x ASHRAE mass fractions,
method-consistent basis (ReCiPe 2016 H vs AR6), and cold-storage leakage from charge."""
from __future__ import annotations

import pytest

from engine import refrigerants as rf

# AR6 GWP100 components, data/IPCC GWP/Global-Warming-Potential-Values (August 2024).pdf
# (HFC-134a: AR6 WG1 Table 7.15 unrounded 1526).
AR6 = {"R-32": 771, "R-125": 3740, "R-134a": 1526, "R-143a": 5810, "R-1234yf": 0.501, "R-1234ze": 1.37}


@pytest.mark.parametrize("blend,expected", [
    ("R-404A", 0.44 * 3740 + 0.52 * 5810 + 0.04 * 1526),     # 4727.8
    ("R-507A", 0.50 * 3740 + 0.50 * 5810),                     # 4775.0
    ("R-448A", 0.26 * 771 + 0.26 * 3740 + 0.20 * 0.501 + 0.21 * 1526 + 0.07 * 1.37),  # 1493.4
    ("R-449A", 0.243 * 771 + 0.247 * 3740 + 0.253 * 0.501 + 0.257 * 1526),          # 1503.4
    ("R-513A", 0.56 * 0.501 + 0.44 * 1526),                    # 671.7
    ("R-410A", 0.5 * 771 + 0.5 * 3740),
    ("R-407C", 0.23 * 771 + 0.25 * 3740 + 0.52 * 1526),
])
def test_ar6_blends_match_component_arithmetic(blend, expected):
    assert rf.AR6_GWP100[blend] == pytest.approx(expected, abs=0.06)
    assert abs(sum(rf.BLEND_COMPOSITION[blend].values()) - 1.0) < 1e-9


def test_audit_values_corrected():
    # audit table: R-404A ~4728, R-507A ~4775, R-448A ~1494, R-449A ~1504, R-513A ~672
    for b, v in {"R-404A": 4728, "R-507A": 4775, "R-448A": 1494, "R-449A": 1504, "R-513A": 672}.items():
        assert abs(rf.AR6_GWP100[b] - v) <= 1.0, b


def test_method_consistent_basis():
    ar6, note_ar6 = rf.refrigerant_co2e("R-134a", 1.0, "EF v3.1")
    rec, note_rec = rf.refrigerant_co2e("R-134a", 1.0, "ReCiPe 2016 v1.03, midpoint (H)")
    assert ar6 == 1526.0 and "AR6" in note_ar6
    assert rec == 1549.0 and "ReCiPe" in note_rec          # ReCiPe 2016 v1.1 H workbook value
    assert rf.gwp100("R-404A", "ReCiPe 2016 v1.03, midpoint (H)") == pytest.approx(
        0.44 * 3691 + 0.52 * 5508 + 0.04 * 1549, abs=0.06)
    assert rf.refrigerant_co2e("R-404A", 2.0)[0] == pytest.approx(2 * 4727.8)   # default AR6


def test_cold_storage_leakage_from_charge():
    kg, info = rf.annual_leakage_from_charge(4.0)
    assert info["leak_rate_range"] == [0.07, 0.25]               # IPCC 2006 Vol 3 Ch 7 Table 7.9
    assert kg == pytest.approx(4.0 * 0.16)
    assert info["kg_per_year_range"] == pytest.approx([0.28, 1.0])
    co2e, note, inf = rf.storage_leakage_co2e(
        {"facilities": ["Cold Storage"], "refrigerant": "R-404A", "refrigerant_charge_kg": 4.0}, "EF v3.1")
    assert co2e == pytest.approx(0.64 * 4727.8, rel=1e-6) and "Table 7.9" in note
    assert rf.storage_leakage_co2e({"facilities": ["Silo"], "refrigerant": "R-404A",
                                    "refrigerant_charge_kg": 4.0})[0] == 0.0
    c, n, _ = rf.storage_leakage_co2e({"facilities": ["Cold Storage"]})
    assert c == 0.0 and "not modelled" in n
