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


def test_ef_nf_and_weights_cover_16_categories():
    d = _j("normalisation_factors.json")["ef_3_1"]
    assert len(d["factors"]) == 16 and set(d["factors"]) == set(d["weighting_pct"])
    assert abs(sum(d["weighting_pct"].values()) - 100.0) < 1e-9
    w = d["weighting_pct"]
    assert (w["Global warming"], w["Particulate matter formation"], w["Water consumption"],
            w["Fossil depletion"], w["Human toxicity, non-cancer"]) == (21.06, 8.96, 8.51, 8.32, 1.84)
    # every EF NF key is a frontend category the adapter actually produces
    produced = {front for front, _u in adapter.MIDPOINT_MAP.values()}
    assert set(d["factors"]) <= produced


def test_generator_reproduces_ef_block_and_recipe_extras():
    """ingestion/gmg_reference.py must regenerate the same EF 3.1 16-category NFs + weights and
    the ReCiPe reported-only NFs that the engine uses (a rerun must not drop them)."""
    gr = pytest.importorskip("ingestion.gmg_reference")
    d = _j("normalisation_factors.json")
    assert gr.EF31_NF_JRC == d["ef_3_1"]["factors"]
    assert gr.EF31_WEIGHTING_PCT == d["ef_3_1"]["weighting_pct"]
    if (DATA / "ReCipe2016").exists():
        assert gr.parse_recipe_nf_reported() == d["recipe_2016"]["factors_reported_not_in_score"]


AGB = DATA / "AGRIBALYSE3.2" / "AGRIBALYSE3.2_partie agriculture_conv_PublieNOV25.xlsx"


@pytest.mark.skipif(not AGB.exists(), reason="AGRIBALYSE 3.2 workbook not on disk")
def test_ef_single_score_reproduces_agribalyse_published_scores():
    """EF 3.1 NF x weights reproduce AGRIBALYSE 3.2's published 'Score unique EF3.1'."""
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.load_workbook(AGB, read_only=True, data_only=True)
    ws = wb["AGB 3.2 agricole conventionnel"]
    cols = ["Global warming", "Ozone depletion", "Ionising radiation", "Photochemical oxidation",
            "Particulate matter formation", "Human toxicity, non-cancer", "Human toxicity, cancer",
            "Terrestrial acidification", "Freshwater eutrophication", "Marine eutrophication",
            "Terrestrial eutrophication", "Freshwater ecotoxicity", "Land use", "Water consumption",
            "Fossil depletion", "Mineral depletion"]
    errs = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i < 3 or not isinstance(row[4], (int, float)):
            continue
        mids = {c: {"value": float(row[5 + k])} for k, c in enumerate(cols)}
        upt, _ = adapter.single_score(mids, {}, "EF v3.1",
                                      bands={"low": 1, "high": 2, "calibrated": False, "basis": ""})
        errs.append(abs(upt / 1000.0 - row[4]) / row[4])          # µPt -> mPt
    errs.sort()
    assert len(errs) > 200
    assert errs[len(errs) // 2] < 1e-3 and errs[-1] < 0.05


def test_ef_single_score_is_weighted_and_recipe_is_labelled_equal_weight():
    bands = {"low": 1, "high": 2, "calibrated": True, "basis": "t"}
    mid = {"Global warming": {"value": 7550.0}}           # exactly one person-year of CC
    _, meta = adapter.single_score(mid, {}, "EF v3.1", bands=bands)
    assert abs(meta["person_equivalents_per_kg"] - 0.2106) < 1e-12
    assert "§4.4.5" in meta["iso_14044_disclosure"]
    _, meta_r = adapter.single_score({"Global warming": {"value": 7990.407652952963}}, {},
                                     "ReCiPe 2016 v1.03, midpoint (H)", bands=bands)
    assert "not an official ReCiPe" in meta_r["label"]
    assert set(meta_r["weighting_factors"].values()) == {1.0}


def test_ef_band_never_borrows_recipe_cutoffs(monkeypatch):
    monkeypatch.setattr(adapter, "_BANDS_FILE_EF", str(ROOT / "does_not_exist.json"))
    monkeypatch.setattr(adapter, "_BANDS_CACHE_EF", None)
    _, meta = adapter.single_score({"Global warming": {"value": 1.0}}, {}, "EF v3.1")
    assert meta["band"] == "Unavailable" and meta["band_cutoffs"]["low"] is None


@pytest.mark.parametrize("method", ["EF v3.1", "ReCiPe 2016 v1.03, midpoint (H)"])
def test_every_store_category_is_mapped_or_a_declared_subindicator(method):
    q = _q()
    m = q.find_method(method)
    names = [r[0] for r in q.conn.execute(
        "SELECT name FROM impact_categories WHERE method_uid=?", (m["uid"],))]
    missing = [n for n in names if n not in adapter.MIDPOINT_MAP and n not in adapter.MIDPOINT_SUBINDICATORS]
    assert not missing, missing
    # no two categories of one method collapse onto the same display name
    fronts = [adapter.MIDPOINT_MAP[n][0] for n in names if n in adapter.MIDPOINT_MAP]
    assert len(fronts) == len(set(fronts))


def test_coproduct_allocation_rules():
    wheat = {"name": "Wheat", "residue_management": {"fraction_removed": 1.0, "removed_residue_use": "sold"}}
    a = adapter.coproduct_allocation(wheat)
    straw = 1.3 * 0.89                                   # IPCC 2019 Table 11.1A R_AG x DRY
    assert a["applied"] and a["factor"] == pytest.approx(1 / (1 + straw / 29.70))
    # removed but use unknown -> not a co-product, disclosed
    b = adapter.coproduct_allocation({"name": "Wheat", "residue_management": {"fraction_removed": 1.0}})
    assert not b["applied"] and b["factor"] == 1.0 and "not stated" in b["note"]
    # co-product but no citable price ratio (maize: no stover dataset) -> not allocated
    c = adapter.coproduct_allocation({"name": "Maize", "residue_management":
                                      {"fraction_removed": 0.5, "residue_use": "fed"}})
    assert not c["applied"] and "no citable" in c["note"]
    assert adapter.coproduct_allocation({"name": "Buckwheat", "residue_management":
                                         {"fraction_removed": 1, "residue_use": "sold"}})["applied"] is False
    assert adapter.coproduct_allocation({"name": "Rice"})["note"] is None


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
