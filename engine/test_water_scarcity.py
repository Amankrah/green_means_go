#!/usr/bin/env python3
"""Tests for AWARE water scarcity and EF soil-quality land-use regionalisation
(engine/water_scarcity.py, engine/land_use_regional.py, ingestion/gmg_reference.py).

Unit tests use an in-memory fake store; the store-backed tests check the regionalised
flows actually ingested into data/canonical/lca_engineer.sqlite (by direct SQL on the CF
table, which is exactly what the UID tier of query._characterize uses) and skip if the
store or the ingest is absent."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

import water_scarcity as ws          # noqa: E402
import land_use_regional as lur      # noqa: E402
from regions import get_region       # noqa: E402

DB = ROOT.parent / "data" / "canonical" / "lca_engineer.sqlite"


# ------------------------------------------------------------------ fakes
class FakeQ:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.executescript("""
            CREATE TABLE flows(uid TEXT PRIMARY KEY, name TEXT, category TEXT);
            CREATE TABLE gmg_regionalised_flows(flow_uid TEXT, kind TEXT, country TEXT, use_type TEXT,
                base_flow_uid TEXT, base_flow_name TEXT);
            INSERT INTO flows VALUES ('w-gh','Water, consumptive use, agri, Ghana (AWARE)','Elementary flows/Emission to air/unspecified');
            INSERT INTO flows VALUES ('w-world','Water, consumptive use, agri, World (AWARE)','Elementary flows/Emission to air/unspecified');
            INSERT INTO flows VALUES ('evap','Water','Elementary flows/Emission to air/unspecified');
            INSERT INTO flows VALUES ('river','Water, river','Elementary flows/Resource/in water');
            INSERT INTO flows VALUES ('occ','Occupation, annual crop','Elementary flows/Resource/land');
            INSERT INTO flows VALUES ('occ-gh','Occupation, annual crop, Ghana (EF soil quality index)','Elementary flows/Resource/land');
            INSERT INTO gmg_regionalised_flows VALUES ('w-gh','water','Ghana','agri','evap','Water');
            INSERT INTO gmg_regionalised_flows VALUES ('w-world','water','World','agri','evap','Water');
            INSERT INTO gmg_regionalised_flows VALUES ('occ-gh','land','Ghana','arable','occ','Occupation, annual crop');
        """)

    def characterize_flows(self, flows, method):
        return {"Water use": {"value": sum(r["amount"] for r in flows.values()), "unit": "m3"}}


def _res():
    return SimpleNamespace(notes=[], contribution_by_source={}, contribution_flows_by_source={})


# ------------------------------------------------------------------ unit
def test_aware_cf_country_and_world_fallback():
    cf, used = ws.aware_cf(get_region("GH"), "agri")
    assert used == "Ghana" and abs(cf - 16.837) < 1e-3
    cf, used = ws.aware_cf(get_region("NG"), "agri")
    assert used == "Nigeria" and abs(cf - 7.998) < 1e-3
    cf, used = ws.aware_cf(SimpleNamespace(aware_country="Senegal"), "agri")
    assert abs(cf - 80.818) < 1e-3                       # Senegal: highly water scarce
    cf, used = ws.aware_cf(SimpleNamespace(aware_country="Atlantis"), "agri")
    assert used == "World" and abs(cf - 45.737) < 1e-3   # AWARE 'World AGRI'


def test_world_unknown_equals_ef31_background_cf():
    # the ecoinvent EF 3.1 'Water use' CF on evaporation (42.95) is AWARE 'World, UNKNOWN'
    assert abs(ws._table()["world"]["unspecified"] - 42.95) < 0.01


def test_measured_purchased_water_supersedes_kernel_estimate():
    lci = [{"substance": "water", "quantity": 8000.0}]
    m3, notes = ws.foreground_consumption(lci, [])
    assert m3 == 8000.0 and not notes
    bought = [{"name": "irrigation water", "amount": 3000.0, "unit": "m3", "water_source": "borehole"}]
    m3, notes = ws.foreground_consumption(lci, bought)
    assert m3 == 3000.0 and any("supersedes" in n for n in notes)
    bought[0]["consumptive_fraction"] = 0.5
    assert ws.foreground_consumption(lci, bought)[0] == 1500.0


def test_apply_books_regional_flow_and_strips_background_evaporation():
    q, res = FakeQ(), _res()
    onfarm = {"river-onfarm": {"name": "water", "unit": "m3", "amount": 100.0}}
    supply = {"evap": {"name": "Water", "unit": "m3", "amount": 40.0},
              "river": {"name": "Water, river", "unit": "m3", "amount": 90.0}}
    res.contribution_flows_by_source["irrigation water"] = {
        "evap": {"name": "Water", "unit": "m3", "amount": 30.0},
        "river": {"name": "Water, river", "unit": "m3", "amount": 90.0}}
    bought = [{"name": "irrigation water", "amount": 100.0, "unit": "m3", "water_source": "river"}]
    info = ws.apply(q, get_region("GH"), [{"substance": "water", "quantity": 500.0}], bought,
                    onfarm, supply, res, "EF v3.1")
    assert info and info["country"] == "Ghana" and info["m3"] == 100.0
    assert onfarm["w-gh"]["amount"] == 100.0                     # foreground, regional flow
    assert abs(supply["evap"]["amount"] - 10.0) < 1e-12          # 30 of 40 removed
    assert "evap" not in res.contribution_flows_by_source["irrigation water"]
    assert "river" in res.contribution_flows_by_source["irrigation water"]   # withdrawal kept


def test_apply_unknown_country_uses_world_flow_and_flags():
    q, res = FakeQ(), _res()
    onfarm = {}
    info = ws.apply(q, SimpleNamespace(aware_country="Atlantis", name="Atlantis"),
                    [{"substance": "water", "quantity": 10.0}], [], onfarm, {}, res, "EF v3.1")
    assert info["country"] == "World" and onfarm["w-world"]["amount"] == 10.0
    assert any("world default" in n for n in res.notes)


def test_apply_without_ingest_is_a_noted_noop():
    q, res = FakeQ(), _res()
    q.conn.execute("DELETE FROM gmg_regionalised_flows")
    onfarm = {}
    assert ws.apply(q, get_region("GH"), [{"substance": "water", "quantity": 10.0}], [],
                    onfarm, {}, res, "EF v3.1") is None
    assert not onfarm and any("not in the store" in n for n in res.notes)


def test_land_occupation_moves_to_country_flow():
    q, res = FakeQ(), _res()
    onfarm = {"occ": {"name": "land_occ", "unit": "m2a", "amount": 20000.0},
              "n2o": {"name": "N2O", "unit": "kg", "amount": 1.0}}
    info = lur.apply(q, get_region("GH"), onfarm, res)
    assert info and "occ" not in onfarm and onfarm["occ-gh"]["amount"] == 20000.0
    assert onfarm["n2o"]["amount"] == 1.0
    # Canada: not ingested in the fake -> world SQI kept, flagged
    onfarm2 = {"occ": {"name": "land_occ", "unit": "m2a", "amount": 5.0}}
    assert lur.apply(q, get_region("CA"), onfarm2, res) is None and "occ" in onfarm2


# ------------------------------------------------------------------ store-backed
def _store():
    if not DB.exists():
        pytest.skip("canonical store not present")
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    if not c.execute("SELECT 1 FROM sqlite_master WHERE name='gmg_regionalised_flows'").fetchone():
        pytest.skip("run python -m ingestion.gmg_reference ingest")
    return c


def _cf(c, flow_uid, method, cat):
    r = c.execute("SELECT cf.factor FROM characterization_factors cf JOIN impact_categories ic ON ic.uid=cf.category_uid "
                  "JOIN impact_methods m ON m.uid=ic.method_uid WHERE cf.flow_uid=? AND m.name=? AND ic.name=?",
                  (flow_uid, method, cat)).fetchone()
    return r[0] if r else None


@pytest.mark.parametrize("country,agri", [("Ghana", 16.837), ("Nigeria", 7.998), ("Senegal", 80.818),
                                          ("Burkina Faso", 16.842), ("South Africa", 40.760), ("Canada", 8.377),
                                          ("World", 45.737)])
def test_store_regional_water_cfs(country, agri):
    c = _store()
    uid = c.execute("SELECT flow_uid FROM gmg_regionalised_flows WHERE kind='water' AND country=? AND use_type='agri'",
                    (country,)).fetchone()[0]
    assert abs(_cf(c, uid, "EF v3.1", "Water use") - agri) < 1e-3
    assert _cf(c, uid, "ReCiPe 2016 v1.03, midpoint (H)", "Water use") == 1.0
    # every other method's CF copied from the ecoinvent base flow (endpoints, other packs)
    n_base = c.execute("SELECT COUNT(*) FROM characterization_factors cf JOIN gmg_regionalised_flows g "
                       "ON g.base_flow_uid=cf.flow_uid WHERE g.flow_uid=?", (uid,)).fetchone()[0]
    n_reg = c.execute("SELECT COUNT(*) FROM characterization_factors WHERE flow_uid=?", (uid,)).fetchone()[0]
    assert n_reg == n_base > 10


@pytest.mark.parametrize("country,arable", [("Ghana", 83.525), ("Nigeria", 70.94), ("Senegal", 30.392),
                                            ("Burkina Faso", 38.63), ("South Africa", 45.47), ("Canada", 26.72)])
def test_store_regional_land_cfs(country, arable):
    c = _store()
    uid = c.execute("SELECT flow_uid FROM gmg_regionalised_flows WHERE kind='land' AND country=? "
                    "AND base_flow_name='Occupation, annual crop'", (country,)).fetchone()[0]
    assert abs(_cf(c, uid, "EF v3.1", "Land use") - arable) < 0.01
    assert _cf(c, uid, "ReCiPe 2016 v1.03, midpoint (H)", "Land use") == 1.0


def test_store_lanca_world_average_reconciles_with_ef31_pack():
    """The SQI world average of every mapped land type equals the EF 3.1 CF shipped by
    ecoinvent for that occupation flow (proves the LANCA file is the EF 3.1 basis)."""
    c = _store()
    import json
    doc = json.loads((ROOT / "lcia_reference" / "lanca_sqi_occupation.json").read_text(encoding="utf-8"))
    bad = []
    for flow, lut in doc["ecoinvent_flow_to_land_type"].items():
        r = c.execute("SELECT cf.factor FROM characterization_factors cf JOIN impact_categories ic ON ic.uid=cf.category_uid "
                      "JOIN impact_methods m ON m.uid=ic.method_uid JOIN flows f ON f.uid=cf.flow_uid "
                      "WHERE m.name='EF v3.1' AND ic.name='Land use' AND f.name=? AND f.category='Elementary flows/Resource/land'",
                      (flow,)).fetchone()
        if r and abs(r[0] - doc["world_average"][lut]) > 0.01 * abs(r[0]):
            bad.append((flow, r[0], doc["world_average"][lut]))
    assert not bad, bad
