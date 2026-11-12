#!/usr/bin/env python3
"""Reference LCIA data: normalisation factors load from the derived file built from the
spreadsheets on disk, the GWP basis is stated per method with store-verified values, the
spreadsheet-vs-store CF reconciliation is clean, and the USEtox pesticide lookup is
complete or its gaps are recorded."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

import adapter                       # noqa: E402
import gwp_basis                     # noqa: E402

REF = ROOT / "lcia_reference"
DATA = ROOT.parent / "data"
DB = DATA / "canonical" / "lca_engineer.sqlite"


def _j(name):
    return json.loads((REF / name).read_text(encoding="utf-8"))


def test_adapter_nf_loaded_from_derived_file():
    assert adapter.NF_SOURCE.endswith("normalisation_factors.json")
    d = _j("normalisation_factors.json")
    assert adapter.RECIPE_NF == d["recipe_2016"]["factors"]
    assert adapter.EF_NF == d["ef_3_1"]["factors"]


def test_fallback_constants_agree_with_file():
    d = _j("normalisation_factors.json")["recipe_2016"]["factors"]
    for k, v in adapter._RECIPE_NF_FALLBACK.items():
        assert abs(v - d[k]) / d[k] < 1e-3, k


@pytest.mark.skipif(not (DATA / "ReCipe2016").exists(), reason="ReCiPe spreadsheets not on disk")
def test_derived_nf_matches_spreadsheet():
    from ingestion.gmg_reference import parse_recipe_nf
    assert parse_recipe_nf()["factors"] == _j("normalisation_factors.json")["recipe_2016"]["factors"]


def test_single_score_uses_matching_nf_set():
    mid = {"Global warming": {"value": 7990.407652952963}}
    total, meta = adapter.single_score(mid, {}, "ReCiPe 2016 v1.03, midpoint (H)",
                                       bands={"low": 1, "high": 2, "calibrated": True, "basis": "t"})
    assert abs(meta["person_equivalents_per_kg"] - 1.0) < 1e-9


def test_gwp_basis_table_matches_pdf_and_recipe():
    g = _j("gwp_basis.json")
    assert g["table"]["AR6"] == {"CH4_non_fossil": 27.0, "CH4_fossil": 29.8, "N2O": 273}
    assert g["table"]["AR5_ccfb"]["N2O"] == 298
    if g.get("recipe_spreadsheet_gwp100_h"):
        assert g["recipe_spreadsheet_gwp100_h"]["Nitrous oxide"] == 298
        assert g["recipe_spreadsheet_gwp100_h"]["Methane"] == 34


def _q():
    if not DB.exists():
        pytest.skip("canonical store not present")
    from ingestion.query import CanonicalQuery
    return CanonicalQuery(DB)


@pytest.mark.parametrize("method,n2o,ch4,word", [("ReCiPe 2016 v1.03, midpoint (H)", 298, 34, "AR5"),
                                                 ("EF v3.1", 273, 27, "AR6")])
def test_gwp_statement_reads_store(method, n2o, ch4, word):
    st = gwp_basis.statement(SimpleNamespace(q=_q()), method)
    assert st["n2o"] == n2o and st["ch4_non_fossil"] == ch4
    assert word in st["basis"] and f"N2O {n2o:g}" in st["text"]
    assert "\u2014" not in st["text"]


def test_cf_reconciliation_recorded_and_explained():
    d = _j("cf_reconciliation.json")
    assert d["recipe"]["n_compared"] >= 50 and d["recipe"]["n_diff_gt_1pct"] == 0
    assert d["ef_3_1"]["n_compared"] >= 1000
    # every EF difference is a known matching artefact class (CAS shared by fossil and
    # biogenic variants, sea-water vs freshwater sub-compartment, energy-unit basis), not a
    # wrong CF in the pack; a new class would need a reviewer.
    known = ("biogenic", "sea water", "land use change", "methyl ether", "uranium", "peat")
    odd = [x for x in d["ef_3_1"]["differences"]
           if not any(k in (x["flow"] + " " + x.get("sub", "")) for k in known)]
    assert not odd, odd


def test_usetox_pesticide_lookup_and_gaps():
    d = _j("usetox_pesticide_cfs.json")["active_ingredients"]
    assert len(d) == 12
    missing = sorted(k for k, v in d.items() if not v["found"])
    assert missing == ["emamectin benzoate"]          # not in USEtox 2.14 (documented gap)
    for k, v in d.items():
        if v["found"]:
            assert v["emission_to_agricultural_soil"]["ecotox_freshwater_ctue_per_kg"] > 0, k
    cov = _j("cf_reconciliation.json")["pesticide_coverage"]
    assert all(cov[k]["store_flows"] for k in d), "every AI must exist as an agri-soil flow in the store"
    assert all(cov[k]["cfs"]["EF v3.1 | Ecotoxicity: freshwater"] for k in d)
