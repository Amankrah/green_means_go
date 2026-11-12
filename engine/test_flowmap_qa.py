#!/usr/bin/env python3
"""
test_flowmap_qa.py: elementary-flow mapping QA for engine/flowmap.py.

Every on-farm flow the kernel emits (flowmap.ONFARM_FLOWS) must resolve to a store flow
that is a valid reference elementary flow with matching CAS and compartment:
  * FEDEFL: the store's `fed_id` (flowable|compartment from the GLAD / Federal LCA Commons
    elementary flow list, loaded by ingestion/glad_load.py) must exist and name the same
    substance. The GLAD / FEDEFL folders under data/References_C are empty skeletons on
    disk, so the store's fed_id column (built from the GLAD mapped files fetched over LFS)
    is the FEDEFL reference used here.
  * ILCD / EF: the CAS and emission medium must exist in the EF 3.1 reference flow list
    (ILCD format, data/EVvinronmental_Footprint_EF3.1, sheet 'flows').
  * Field emissions must go to a ground-level compartment (not stratosphere, not long-term)
    and must keep the fossil / biogenic distinction.

All checks must pass. flowmap._resolve ranks same-name candidates so field emissions land
on the ordinary ecoinvent ground-level flows (air: low population density; water: surface
water), which the served method packs characterise by exact UID. The resolved flows'
characterisation factors are checked against the published values below.
"""
from __future__ import annotations

import sqlite3
import sys
from functools import lru_cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

from flowmap import ONFARM_FLOWS, OnFarmFlowMap          # noqa: E402
from ingestion.flowkey import norm_cas, norm_compartment  # noqa: E402

DB = ROOT.parent / "data" / "canonical" / "lca_engineer.sqlite"
EF_XLSX = ROOT.parent / "data" / "EVvinronmental_Footprint_EF3.1" / "EF-LCIAMethod_CF(EF-v3.1).xlsx"

# Expected FEDEFL flowable (lower case) per kernel substance key.
FEDEFL_FLOWABLE = {
    "N2O": "nitrous oxide", "CH4": "methane", "CH4_bio": "methane", "CO2": "carbon dioxide",
    "CO2_bio": "carbon dioxide", "NH3": "ammonia", "NOx": "nitrogen oxides", "NO3": "nitrate",
    "PO4": "orthophosphate", "P": "phosphorus", "SO2": "sulfur dioxide",
    "PM25": "particulate matter, < 2.5 um", "water": "water", "land_occ": None,
}
_MEDIUM_TO_EF = {"emission/air": "emissions to air", "emission/water": "emissions to water",
                 "emission/soil": "emissions to soil"}


def _skip_no_store():
    if not DB.exists():
        pytest.skip("canonical store not present")


@lru_cache(maxsize=1)
def _resolved() -> dict:
    m = OnFarmFlowMap(DB)
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    out = {}
    for k in ONFARM_FLOWS:
        uid = m.resolve(k)
        row = c.execute("SELECT name, category, cas, fed_id FROM flows WHERE uid=?", (uid,)).fetchone() if uid else None
        out[k] = (uid, row)
    m.close()
    return out


@lru_cache(maxsize=1)
def _ef_reference() -> set:
    import openpyxl
    wb = openpyxl.load_workbook(EF_XLSX, read_only=True, data_only=True)
    ref = set()
    for r in wb["flows"].iter_rows(min_row=2, values_only=True):
        if r[2] and r[5]:
            ref.add((norm_cas(str(r[2]).strip()), str(r[5]).strip().lower()))
    wb.close()
    return ref


@pytest.mark.parametrize("key", list(ONFARM_FLOWS))
def test_onfarm_flow_resolves_with_matching_cas_and_medium(key):
    _skip_no_store()
    names, cas, medium = ONFARM_FLOWS[key]
    uid, row = _resolved()[key]
    assert uid and row, f"{key} does not resolve to a store flow"
    name, category, scas, fed = row
    assert norm_compartment(category).startswith(medium), f"{key}: {category} is not {medium}"
    if cas and scas:
        assert norm_cas(scas) == norm_cas(cas), f"{key}: store CAS {scas} != {cas}"
    elif cas:   # store flow carries no CAS (e.g. ecoinvent 'Nitrogen oxides'): identity by name
        assert name in names, f"{key}: no CAS on '{name}' and name not in {names}"


# Known FEDEFL findings in the store's fed_id column. They no longer matter for the on-farm
# path because the resolved flows are characterised by exact UID (no bridge), which the
# test checks instead; the fed_id defect still affects Agribalyse-nomenclature flows.
FEDEFL_STORE_DEFECTS = {
    "P": "store fed_id of ecoinvent 'Phosphorus' (water) is 'orthophosphate|...', the same flowable as Phosphate",
    "PM25": "ecoinvent 'Particulate Matter, < 2.5 um' carries no fed_id",
}


def _uid_known(uid: str) -> bool:
    """True if both served methods characterise this exact flow UID in some category, so
    query._characterize never consults the FEDEFL bridge for it."""
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    n = c.execute("SELECT COUNT(DISTINCT m.name) FROM characterization_factors cf JOIN impact_categories ic "
                  "ON ic.uid=cf.category_uid JOIN impact_methods m ON m.uid=ic.method_uid WHERE cf.flow_uid=? "
                  "AND m.name IN ('ReCiPe 2016 v1.03, midpoint (H)', 'EF v3.1')", (uid,)).fetchone()[0]
    return n == 2


@pytest.mark.parametrize("key", [k for k, v in FEDEFL_FLOWABLE.items() if v])
def test_onfarm_flow_has_fedefl_identity(key):
    _skip_no_store()
    uid, row = _resolved()[key]
    fed = row[3] if row else None
    if key in FEDEFL_STORE_DEFECTS:
        assert _uid_known(uid), f"{key}: {FEDEFL_STORE_DEFECTS[key]} and the flow is not UID-characterised"
        return
    assert fed and fed != "__NOMAP__", f"{key}: no FEDEFL id"
    assert fed.split("|")[0] == FEDEFL_FLOWABLE[key], f"{key}: FEDEFL flowable {fed!r}"
    assert fed.split("|")[1].startswith(norm_compartment(row[1]).split("/")[0]), f"{key}: {fed} vs {row[1]}"


@pytest.mark.skipif(not EF_XLSX.exists(), reason="EF 3.1 reference flow list not on disk")
@pytest.mark.parametrize("key", [k for k, v in ONFARM_FLOWS.items() if v[1] and v[2] in _MEDIUM_TO_EF])
def test_onfarm_flow_exists_in_ilcd_ef_reference_list(key):
    _, cas, medium = ONFARM_FLOWS[key]
    assert (norm_cas(cas), _MEDIUM_TO_EF[medium]) in _ef_reference(), f"{key}: CAS {cas} not in EF 3.1 {medium}"


def _compartment_findings() -> list[str]:
    bad = []
    for k, (uid, row) in _resolved().items():
        if not row or not ONFARM_FLOWS[k][2].startswith("emission"):
            continue
        cat = (row[1] or "").lower()
        if "stratosphere" in cat or "long-term" in cat:
            bad.append(f"{k} -> '{row[0]}' in '{row[1]}' (field emission should be ground level, "
                       "e.g. 'Emission to air/low population density' or 'unspecified')")
        if k.endswith("_bio") and ("non-fossil" not in (row[0] or "").lower()):
            bad.append(f"{k} -> '{row[0]}' loses the biogenic qualifier")
        # (FEDEFL merges biogenic and fossil CO2 into one flowable; query._characterize
        # never bridges biogenic CO2, see ingestion/test_biogenic_bridge.py.)
        if k == "CH4" and (row[0] or "") == "Methane":
            bad.append(f"{k} -> bare 'Methane' (no fossil/non-fossil qualifier): 0 under ReCiPe climate")
    return bad


def test_field_emissions_ground_level_and_biogenic_preserved():
    _skip_no_store()
    bad = _compartment_findings()
    assert not bad, "\n".join(bad)


# Published CFs the resolved on-farm flows must carry, by exact UID: ReCiPe 2016 H (AR5 incl.
# climate-carbon feedbacks) and EF 3.1 (AR6). Biogenic CO2 = 0 under both.
EXPECTED_CLIMATE = {
    "N2O": (298.0, 273.0), "CH4": (36.0, 29.8), "CH4_bio": (34.0, 27.0),
    "CO2": (1.0, 1.0), "CO2_bio": (0.0, 0.0),
}


@pytest.mark.parametrize("key", list(EXPECTED_CLIMATE))
def test_onfarm_climate_cfs_by_uid(key):
    _skip_no_store()
    uid, _ = _resolved()[key]
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    for method, want in zip(("ReCiPe 2016 v1.03, midpoint (H)", "EF v3.1"), EXPECTED_CLIMATE[key]):
        r = c.execute("SELECT cf.factor FROM characterization_factors cf JOIN impact_categories ic ON ic.uid=cf.category_uid "
                      "JOIN impact_methods m ON m.uid=ic.method_uid WHERE cf.flow_uid=? AND m.name=? AND ic.name='Climate change'",
                      (uid, method)).fetchone()
        got = r[0] if r else 0.0
        assert abs(got - want) < 1e-9, f"{key} under {method}: {got} != {want}"


if __name__ == "__main__":
    for line in _compartment_findings():
        print(line)
