#!/usr/bin/env python3
"""
test_regions.py - the region registry (engine/regions.py) and its reference tables.

Covers the SN / BF / ZA additions: IPCC climate parameters, aliases, store location
strings, AWARE keys, the "no silent Ghana inheritance" audit, the reference JSONs (same
schema as the Ghana tables, every value cited with a pedigree), the climate override and
irrigation-aware FracLEACH, and the starter recommendation measures.

Store / AWARE checks skip cleanly when data/ is absent.
"""
from __future__ import annotations

import dataclasses
import inspect
import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
for p in (str(ROOT), str(ROOT.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

import regions as R  # noqa: E402

REF = ROOT / "recommend" / "reference"
STORE = ROOT.parent / "data" / "canonical" / "lca_engineer.sqlite"
AWARE = ROOT.parent / "data" / "AWARE2.0" / "AWARE_country_regions_Corrected_online_20230113-1.xlsx"
NEW = ("SN", "BF", "ZA")
CONTRACT_FIELDS = ("frac_gasf", "frac_gasm", "frac_leach", "ef4", "ef5", "climate_zone",
                   "ipcc_n2o_ef1", "activity_defaults_file", "yield_guide_file",
                   "grid_ef_source", "ghana_inherited", "field_sources")


def test_contract_field_names_exist():
    names = {f.name for f in dataclasses.fields(R.Region)}
    missing = [f for f in CONTRACT_FIELDS if f not in names]
    assert not missing, f"Region is missing contract fields {missing}"


def test_all_required_regions_present():
    assert set(R.REGIONS) >= {"GH", "NG", "SN", "BF", "ZA", "CA"}


@pytest.mark.parametrize("alias,code", [
    ("Senegal", "SN"), ("senegal", "SN"), ("Sénégal", "SN"), ("sn", "SN"),
    ("Burkina Faso", "BF"), ("burkina", "BF"), ("BF", "BF"),
    ("South Africa", "ZA"), ("RSA", "ZA"), ("za", "ZA"), ("ZAF", "ZA"),
    ("Ghana", "GH"), ("Global", "CA"),
])
def test_aliases(alias, code):
    assert R.get_region(alias).code == code


def test_currency_and_method():
    assert (R.REGIONS["SN"].currency, R.REGIONS["BF"].currency, R.REGIONS["ZA"].currency) == ("XOF", "XOF", "ZAR")
    for c in NEW:
        assert R.REGIONS[c].default_method == "ReCiPe 2016 v1.03, midpoint (H)"


def test_ipcc_climate_parameters():
    # IPCC 2019 Vol 4 Ch 11 Tables 11.1 / 11.3
    for c in ("SN", "BF", "ZA"):
        r = R.REGIONS[c]
        assert r.ipcc_n2o_ef1 == 0.005, c
        assert r.ef4 == 0.005, c
        assert r.frac_leach == 0.0, c
        assert "dry" in r.climate_zone
    for c in ("GH", "NG"):
        r = R.REGIONS[c]
        assert (r.ipcc_n2o_ef1, r.ef4, r.frac_leach) == (0.016, 0.014, 0.24), c
    ca = R.REGIONS["CA"]
    assert (ca.ipcc_n2o_ef1, ca.ef4, ca.frac_leach) == (0.010, 0.010, 0.24)
    for r in R.REGIONS.values():
        assert (r.ef5, r.frac_gasf, r.frac_gasm) == (0.011, 0.11, 0.21)


def test_every_climate_value_is_cited():
    names = {f.name for f in dataclasses.fields(R.Region)}
    for r in R.REGIONS.values():
        for k in r.field_sources:
            assert k in names, f"{r.code}: field_sources key {k!r} is not a Region field"
        for k in ("ipcc_n2o_ef1", "ef4", "ef5", "frac_gasf", "frac_gasm", "frac_leach"):
            assert r.field_sources.get(k), f"{r.code}: {k} has no citation"
        if r.grid_ef_kgco2_per_kwh is not None:
            assert r.field_sources.get("grid_ef_kgco2_per_kwh"), f"{r.code}: grid EF uncited"
            assert r.field_pedigree.get("grid_ef_kgco2_per_kwh"), f"{r.code}: grid EF has no pedigree"


def test_no_silent_ghana_inheritance():
    """Any non-GH field equal to Ghana's number must be a global IPCC default, carry its
    own (different) citation, or be flagged in ghana_inherited (team brief 3b)."""
    gh = R.REGIONS["GH"]
    skip = set(R.GLOBAL_DEFAULT_FIELDS) | {"code", "name", "field_sources", "field_pedigree",
                                           "ghana_inherited", "location_prefer"}
    for r in R.REGIONS.values():
        if r.code == "GH":
            continue
        for f in dataclasses.fields(R.Region):
            if f.name in skip:
                continue
            v = getattr(r, f.name)
            own_cite = r.field_sources.get(f.name)
            independently_sourced = bool(own_cite) and own_cite != gh.field_sources.get(f.name)
            if (isinstance(v, (int, float)) and not isinstance(v, bool) and v == getattr(gh, f.name)
                    and not independently_sourced):
                assert f.name in r.ghana_inherited, (
                    f"{r.code}.{f.name} = {v} equals the Ghana value but is not flagged in ghana_inherited")
    for c in NEW:
        assert R.REGIONS[c].ghana_inherited == (), f"{c} should be fully region-sourced"


def test_location_rank_signature_unchanged():
    assert list(inspect.signature(R.location_rank).parameters) == ["region", "location"]


@pytest.mark.skipif(not STORE.exists(), reason="canonical store not present")
def test_location_prefer_strings_exist_in_store():
    con = sqlite3.connect(f"file:{STORE.as_posix()}?mode=ro", uri=True)
    locs = {row[0] for row in con.execute("select distinct location from processes")}
    con.close()
    assert "Senegal" in locs and "South Africa" in locs and "Africa" in locs
    for c in NEW:
        hits = [p for p in R.REGIONS[c].location_prefer if p in locs]
        assert "Rest of World" in hits and "Global" in hits, c
    assert "Burkina Faso" not in locs  # documented: BF falls to RAF/RoW


@pytest.mark.skipif(not AWARE.exists(), reason="AWARE 2.0 xlsx not present")
def test_aware_country_keys_exist():
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.load_workbook(AWARE, read_only=True)
    names = {row[0] for row in wb["AWARE-annual"].iter_rows(values_only=True) if row and row[0]}
    for r in R.REGIONS.values():
        assert r.aware_country in names, f"{r.code}: AWARE key {r.aware_country!r} not in AWARE 2.0"


def _load(name):
    return json.loads((REF / name).read_text(encoding="utf-8"))


def test_reference_files_exist_and_match_ghana_schema():
    gh = _load("ghana_farm_activity_defaults.json")
    gh_row_ids = {r["id"] for r in gh["rows"]}
    gh_row_keys = {k for r in gh["rows"] for k in r}
    for c in NEW:
        r = R.REGIONS[c]
        for fn in (r.activity_defaults_file, r.yield_guide_file, r.grid_ef_source, r.price_feed_file):
            assert fn and (REF / fn).exists(), f"{c}: missing reference file {fn}"
        ad = _load(r.activity_defaults_file)
        assert set(gh) <= set(ad), f"{c}: activity defaults lack Ghana top-level keys {set(gh) - set(ad)}"
        assert {row["id"] for row in ad["rows"]} == gh_row_ids
        for row in ad["rows"]:
            assert set(row) <= gh_row_keys | {"irrigation_mode"}
            assert isinstance(row["diesel_l_per_ha"], (int, float)) and row["diesel_l_per_ha"] >= 0
            assert isinstance(row["electricity_kwh_per_ha"], (int, float)) and row["electricity_kwh_per_ha"] >= 0
            assert row["yield_guides_kg_per_ha"].get("_default", 0) > 0
            assert row["provenance"]["source"] and row["provenance"]["span"]
            assert set(row["provenance"]["pedigree"]) == {"reliability", "completeness", "temporal",
                                                          "geographical", "technological"}
        # not a copy of Ghana
        gh_pairs = [(x["diesel_l_per_ha"], x["electricity_kwh_per_ha"], x["yield_guides_kg_per_ha"]) for x in gh["rows"]]
        ad_pairs = [(x["diesel_l_per_ha"], x["electricity_kwh_per_ha"], x["yield_guides_kg_per_ha"]) for x in ad["rows"]]
        assert gh_pairs != ad_pairs


def test_grid_reference_matches_registry():
    for c in NEW:
        r = R.REGIONS[c]
        g = _load(r.grid_ef_source)
        assert g["factors"]["all_other_projects"]["value"] == r.grid_ef_kgco2_per_kwh
        assert g["provenance"]["span"] and g["provenance"]["source"]
    gh = _load(R.REGIONS["GH"].grid_ef_source)
    assert gh["factors"]["all_other_projects"]["value"] == R.REGIONS["GH"].grid_ef_kgco2_per_kwh


def test_yield_and_price_files_have_pedigree():
    for c in NEW:
        r = R.REGIONS[c]
        y = _load(r.yield_guide_file)
        assert y["crops"], c
        for crop, v in y["crops"].items():
            assert v["value"] > 0 and v["unit"] == "kg/ha" and v["pedigree"], (c, crop)
        p = _load(r.price_feed_file)
        assert p["currency"] == r.currency
        for crop, v in p["prices"].items():
            assert v["price_per_kg"] > 0 and v["unit"] == f"{r.currency}/kg" and v["pedigree"], (c, crop)


def test_common_crops_have_yield_guides():
    want = {"SN": ("groundnut", "millet", "rice", "tomato", "onion"),
            "BF": ("cotton", "maize", "sorghum", "sesame", "tomato"),
            "ZA": ("maize", "sugarcane", "citrus", "grapes", "apple")}
    for c, crops in want.items():
        y = _load(R.REGIONS[c].yield_guide_file)["crops"]
        assert all(k in y for k in crops), (c, [k for k in crops if k not in y])


def test_with_climate_override():
    za_wet = R.with_climate(R.REGIONS["ZA"], "wet")
    assert (za_wet.ipcc_n2o_ef1, za_wet.ef4, za_wet.frac_leach) == (0.016, 0.014, 0.24)
    assert "wet" in za_wet.climate_zone
    assert R.REGIONS["ZA"].ipcc_n2o_ef1 == 0.005  # registry untouched
    ng_dry = R.with_climate(R.REGIONS["NG"], "dry")
    assert ng_dry.ipcc_n2o_ef1 == 0.005 and ng_dry.ghana_inherited == ()
    with pytest.raises(ValueError):
        R.with_climate(R.REGIONS["ZA"], "humid")


def test_frac_leach_for_irrigation():
    sn = R.REGIONS["SN"]
    assert R.frac_leach_for(sn, None) == 0.0
    assert R.frac_leach_for(sn, "None (Rainfed)") == 0.0
    assert R.frac_leach_for(sn, "Drip") == 0.0
    assert R.frac_leach_for(sn, "Furrow") == 0.24
    assert R.frac_leach_for(sn, "Centre pivot sprinkler") == 0.24
    assert R.frac_leach_for(R.REGIONS["GH"], "Drip") == 0.24  # wet region keeps 0.24


def test_field_gsd_from_pedigree():
    sn_gsd = R.field_gsd(R.REGIONS["SN"], "grid_ef_kgco2_per_kwh")
    za_gsd = R.field_gsd(R.REGIONS["ZA"], "grid_ef_kgco2_per_kwh")
    assert sn_gsd and za_gsd and sn_gsd > za_gsd > 1.0  # older, consultant-derived SN figure is wider
    assert R.field_gsd(R.REGIONS["CA"], "grid_ef_kgco2_per_kwh") is None


def test_service_region_resolution_prefers_explicit_region():
    try:
        from service import _region_of
    except ImportError:
        from engine.service import _region_of
    assert _region_of({"country": "Global", "region": "SN"}, None) == "SN"
    assert _region_of({"country": "Global", "region": "ZA"}, None) == "ZA"
    assert _region_of({"country": "Global", "region": "CA"}, None) == "CA"
    assert _region_of({"country": "Ghana", "region": "Northern"}, None) == "GH"
    assert _region_of({"country": "Global", "region": "SN"}, "BF") == "BF"


def test_starter_measures_per_new_region():
    try:
        from recommend.schema import load_measures
        from recommend.licences import licence_status
    except ImportError:
        from engine.recommend.schema import load_measures
        from engine.recommend.licences import licence_status
    ms = load_measures()
    for c in NEW:
        mine = [m for m in ms if c in m.applicability.regions]
        assert len(mine) >= 3, f"{c}: expected a starter set, got {len(mine)}"
        for m in mine:
            assert licence_status(m.provenance.source) != "unconfirmed", m.id
            assert m.provenance.span and m.provenance.citation, m.id


def test_case_studies_present():
    cs = ROOT / "case_studies"
    for stem, code in (("senegal_groundnut_rainfed", "SN"), ("burkina_faso_maize_compost", "BF"),
                       ("south_africa_irrigated_maize", "ZA")):
        d = json.loads((cs / f"{stem}.json").read_text(encoding="utf-8"))
        assert d["region"] == code and d["country"] == "Global"
        assert (cs / f"{stem}.sources.md").exists()


@pytest.mark.skipif(not STORE.exists(), reason="canonical store not present")
@pytest.mark.parametrize("code,pattern", [("ZA", "Electricity, low voltage {ZA}%"),
                                          ("SN", "Electricity, low voltage {SN}%")])
def test_grid_calibration_lands_on_official_factor(code, pattern):
    """The new regions' grid EF flows through engine/grid_calibration.py unchanged."""
    import grid_calibration
    from ingestion.query import CanonicalQuery
    q = CanonicalQuery(str(STORE))
    r = R.REGIONS[code]
    uid = sqlite3.connect(f"file:{STORE.as_posix()}?mode=ro", uri=True).execute(
        "select uid from processes where name like ? limit 1", (pattern,)).fetchone()[0]
    sc = q.cradle_to_gate(uid, amount=1.0)
    info = grid_calibration.apply(q, {"kind": "electricity", "amount": 1.0},
                                  sc.elementary_flows, r, r.default_method)
    assert info is not None and abs(info["climate_after"] - r.grid_ef_kgco2_per_kwh) < 1e-3
    assert info["climate_before"] < r.grid_ef_kgco2_per_kwh  # ecoinvent understates both
