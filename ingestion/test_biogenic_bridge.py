#!/usr/bin/env python3
"""
Biogenic carbon in the characterisation bridge (query._characterize).

FEDEFL has a single flowable 'carbon dioxide' (and 'methane') for fossil and biogenic
carbon, so before this fix a foreign-nomenclature 'Carbon dioxide, non-fossil' flow was
bridged to the fossil CF (1.0) and 'Methane, non-fossil' leaked into EF 3.1's fossil and
LULUC climate sub-categories. Rules now:
  * biogenic CO2 -> 0 in every climate category (IPCC / PEF carbon-neutrality convention);
  * non-fossil methane -> bridged by exact name key only, i.e. the method's own biogenic
    CH4 factor (ReCiPe 2016 H 34; EF 3.1 27.0, booked under 'Climate change: biogenic'),
    never the fossil / LULUC sub-category factor.
A synthetic store proves the rule; a store-backed check runs on the real method pack.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from canonical_store import CanonicalStore      # noqa: E402
from query import CanonicalQuery                # noqa: E402

AIR = "Elementary flows/Emission to air/low population density"
STRAT = "Elementary flows/Emission to air/lower stratosphere + upper troposphere"


@pytest.fixture()
def synth():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    with CanonicalStore(path) as st:
        sid = st.upsert_source("synthetic", "v1", "test")
        st.add_flows(sid, [
            {"uid": "co2f", "name": "Carbon dioxide, fossil", "category": AIR, "cas": "124-38-9", "flow_type": "ELEMENTARY_FLOW"},
            {"uid": "ch4f", "name": "Methane, fossil", "category": AIR, "cas": "74-82-8", "flow_type": "ELEMENTARY_FLOW"},
            {"uid": "ch4b", "name": "Methane, non-fossil", "category": AIR, "cas": "74-82-8", "flow_type": "ELEMENTARY_FLOW"},
            # foreign-nomenclature inventory flows (different UIDs, other sub-compartment)
            {"uid": "co2b_x", "name": "Carbon dioxide, non-fossil", "category": STRAT, "cas": "124-38-9", "flow_type": "ELEMENTARY_FLOW"},
            {"uid": "ch4b_x", "name": "Methane, non-fossil", "category": STRAT, "cas": "74-82-8", "flow_type": "ELEMENTARY_FLOW"},
            {"uid": "co2f_x", "name": "Carbon dioxide, fossil", "category": STRAT, "cas": "124-38-9", "flow_type": "ELEMENTARY_FLOW"},
        ])
        st.add_impact_method(sid, "m", "EF test")
        st.add_impact_category(sid, "cc", "Climate change", "kg CO2-Eq", "m")
        st.add_impact_category(sid, "ccf", "Climate change: fossil", "kg CO2-Eq", "m")
        st.add_impact_category(sid, "ccb", "Climate change: biogenic", "kg CO2-Eq", "m")
        st.add_cfs("cc", [{"flow_uid": "co2f", "factor": 1.0}, {"flow_uid": "ch4f", "factor": 29.8},
                          {"flow_uid": "ch4b", "factor": 27.0}])
        st.add_cfs("ccf", [{"flow_uid": "co2f", "factor": 1.0}, {"flow_uid": "ch4f", "factor": 29.8}])
        st.add_cfs("ccb", [{"flow_uid": "ch4b", "factor": 27.0}])
        st.commit()
    c = sqlite3.connect(path)
    c.execute("ALTER TABLE flows ADD COLUMN fed_id TEXT")
    # FEDEFL merges fossil and biogenic carbon into one flowable (the root cause)
    c.execute("UPDATE flows SET fed_id='carbon dioxide|emission/air/low-pop' WHERE uid IN ('co2f','co2f_x','co2b_x')")
    c.execute("UPDATE flows SET fed_id='methane|emission/air/low-pop' WHERE uid IN ('ch4f','ch4b','ch4b_x')")
    c.commit(); c.close()
    q = CanonicalQuery(path)
    yield q
    q.close()
    for ext in ("", "-wal", "-shm"):
        try:
            os.remove(path + ext)
        except OSError:
            pass


def _v(imp, cat):
    return (imp.get(cat) or {}).get("value", 0.0)


def test_biogenic_co2_is_zero(synth):
    imp = synth.characterize_flows({"co2b_x": {"amount": 10.0}}, "EF test")
    assert _v(imp, "Climate change") == 0.0 and _v(imp, "Climate change: fossil") == 0.0


def test_fossil_co2_still_bridges(synth):
    imp = synth.characterize_flows({"co2f_x": {"amount": 10.0}}, "EF test")
    assert _v(imp, "Climate change") == 10.0 and _v(imp, "Climate change: fossil") == 10.0


def test_non_fossil_methane_takes_biogenic_factor_only(synth):
    imp = synth.characterize_flows({"ch4b_x": {"amount": 1.0}}, "EF test")
    assert _v(imp, "Climate change") == 27.0
    assert _v(imp, "Climate change: biogenic") == 27.0
    assert _v(imp, "Climate change: fossil") == 0.0


DB = HERE.parent / "data" / "canonical" / "lca_engineer.sqlite"
# Agribalyse-nomenclature biogenic flows (stratosphere sub-compartment, no own CFs).
AGB_CO2_BIO = "4e1f0bb0-2703-4303-bf86-972d810612cf"
AGB_CH4_BIO = "258263a0-6be3-4439-bd84-efee0498b849"


@pytest.mark.skipif(not DB.exists(), reason="canonical store not present")
@pytest.mark.parametrize("method,total,fossil_cat", [("ReCiPe 2016 v1.03, midpoint (H)", 34.0, None),
                                                     ("EF v3.1", 27.0, "Climate change: fossil")])
def test_store_biogenic_carbon(method, total, fossil_cat):
    q = CanonicalQuery(DB)
    try:
        if not q.conn.execute("SELECT 1 FROM flows WHERE uid=?", (AGB_CO2_BIO,)).fetchone():
            pytest.skip("Agribalyse biogenic flows not in this store")
        imp = q.characterize_flows({AGB_CO2_BIO: {"amount": 1.0}, AGB_CH4_BIO: {"amount": 1.0}}, method)
    finally:
        q.close()
    assert abs(_v(imp, "Climate change") - total) < 1e-9      # CO2 contributes 0
    if fossil_cat:
        assert _v(imp, fossil_cat) == 0.0
        assert _v(imp, "Climate change: land use and land use change") == 0.0
        assert abs(_v(imp, "Climate change: biogenic") - 27.0) < 1e-9
