#!/usr/bin/env python3
"""
gmg_reference.py: ingest the reference LCIA datasets that sit on disk under data/ but
were never read (AWARE, LANCA / EF soil quality index, USEtox 2.14, ReCiPe 2016 and
EF 3.1 spreadsheets, IPCC GWP table) into

  1. small DERIVED JSON lookups committed under engine/lcia_reference/ (so a result is
     reproducible from git without re-reading 100 MB of spreadsheets), and
  2. the canonical store (data/canonical/lca_engineer.sqlite), which stays the canonical
     copy. Everything is ADDITIVE: new gmg_* tables, one new `sources` row, new
     regionalised elementary flows, and new characterization_factors rows for those new
     flows only. No existing row is altered or deleted.

Regionalised foreground flows (the reason the store needs new flows, not just tables)
---------------------------------------------------------------------------------
The ecoinvent 3.11 method pack carries only GLOBAL water and land CFs:
  * EF 3.1 "Water use" = 42.95 m3 world-eq per m3 evaporated, which is exactly the AWARE
    "World, UNKNOWN" aggregate (AWARE country file, sheet AWARE-annual, row
    "World, UNKNOWN" = 42.9535). ReCiPe 2016 "Water use" = 1.0 m3 consumed.
  * EF 3.1 "Land use" occupation CFs are the SQI world averages of De Laurentiis et al.
    (2019) (mmc2, sheet Occupation_SQI, indicator Total), e.g. arable = 50.191 Pt/m2a.
To apply COUNTRY CFs to on-farm irrigation water and land occupation without forking the
characterisation path, we add one elementary flow per (base flow, country). Each new flow
copies every CF of its ecoinvent base flow in every method, except the EF v3.x "Water use"
/ "Land use" CF, which is replaced by the country value. The engine then simply books
on-farm water / land on the regionalised flow (engine/water_scarcity.py,
engine/land_use_regional.py) and the single validated path (query.characterize_flows)
does the rest, including method switches, endpoints and Monte Carlo.

Usage
-----
  python -m ingestion.gmg_reference build     # (re)write engine/lcia_reference/*.json
  python -m ingestion.gmg_reference ingest    # write tables + regionalised flows to store
  python -m ingestion.gmg_reference all
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from ingestion.canonical_store import DEFAULT_DB  # noqa: E402

DATA = _ROOT / "data"
OUT = _ROOT / "engine" / "lcia_reference"

AWARE_FILE = DATA / "AWARE2.0" / "AWARE_country_regions_Corrected_online_20230113-1.xlsx"
AWARE_OTHER_FILE = DATA / "AWARE2.0" / "AWARE_other_indicators_country_regions-world_20230113-1.xlsx"
LANCA_FILE = DATA / "LANCA" / "1-s2.0-S095965261833960X-mmc2.xlsx"
USETOX_DIR = DATA / "USEtox_2.14" / "Results"
RECIPE_NF_FILE = DATA / "ReCipe2016" / "Normalization scores ReCiPe2016v1.1_20190514.xlsx"
RECIPE_CF_FILE = DATA / "ReCipe2016" / "ReCiPe2016_CFs_v1.1_20180117.xlsx"
EF_FILE = DATA / "EVvinronmental_Footprint_EF3.1" / "EF-LCIAMethod_CF(EF-v3.1).xlsx"
GWP_PDF = DATA / "IPCC GWP" / "Global-Warming-Potential-Values (August 2024).pdf"

# Countries served by the region registry (GH, NG, SN, BF, ZA, CA). Names are the AWARE /
# LANCA spreadsheet spellings, which are also Region.aware_country values.
COUNTRIES = ("Ghana", "Nigeria", "Senegal", "Burkina Faso", "South Africa", "Canada")
WORLD = "World"

REGIONAL_SOURCE_NAME = "gmg_regionalised_lcia"
REGIONAL_SOURCE_VERSION = "1.0"

# ecoinvent occupation flow name -> LANCA / SQI land-use type (De Laurentiis et al. 2019,
# mmc2 Occupation_SQI column B). The world average of each type equals the EF 3.1 CF of the
# ecoinvent flow in the store (checked at ingest, see _reconcile_land()).
LAND_TYPE_MAP = {
    "Occupation, annual crop": "arable",
    "Occupation, annual crop, non-irrigated": "arable, non-irrigated",
    "Occupation, annual crop, non-irrigated, extensive": "arable, non-irrigated, extensive",
    "Occupation, annual crop, non-irrigated, intensive": "arable, non-irrigated, intensive",
    "Occupation, annual crop, irrigated": "arable, irrigated",
    "Occupation, annual crop, irrigated, extensive": "arable, irrigated, extensive",
    "Occupation, annual crop, irrigated, intensive": "arable, irrigated, intensive",
    "Occupation, annual crop, flooded crop": "arable, flooded crops",
    "Occupation, permanent crop": "permanent crops",
    "Occupation, permanent crop, non-irrigated": "permanent crops, non-irrigated",
    "Occupation, permanent crop, non-irrigated, extensive": "permanent crops, non-irrigated, extensive",
    "Occupation, permanent crop, non-irrigated, intensive": "permanent crops, non-irrigated, intensive",
    "Occupation, permanent crop, irrigated": "permanent crops, irrigated",
    "Occupation, permanent crop, irrigated, extensive": "permanent crops, irrigated, extensive",
    "Occupation, permanent crop, irrigated, intensive": "permanent crops, irrigated, intensive",
}

# Common West African pesticide active ingredients (CAS as listed in USEtox 2.14).
PESTICIDE_AIS = {
    "glyphosate": ("1071-83-6",),
    "paraquat": ("4685-14-7", "1910-42-5"),
    "atrazine": ("1912-24-9",),
    "2,4-D": ("94-75-7",),
    "lambda-cyhalothrin": ("91465-08-6",),
    "cypermethrin": ("52315-07-8",),
    "chlorpyrifos": ("2921-88-2",),
    "mancozeb": ("8018-01-7",),
    "imidacloprid": ("138261-41-3", "105827-78-9"),
    "emamectin benzoate": ("155569-91-8", "137512-74-4"),   # not in USEtox 2.14 (gap)
    "metalaxyl": ("57837-19-1", "70630-17-0"),
    "copper": ("15158-11-9", "7440-50-8"),   # USEtox lists copper as Cu(II) ion
}


# ------------------------------------------------------------------ helpers
def _sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def _wb(path: Path):
    import openpyxl  # local import: only the build step needs it
    return openpyxl.load_workbook(path, read_only=True, data_only=True)


def _num(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return None


def _norm_cas(c) -> str:
    s = str(c or "").strip()
    if s.isdigit() and len(s) > 3:          # ReCiPe stores CAS as an integer (100005)
        s = f"{s[:-3]}-{s[-3:-1]}-{s[-1]}"
    parts = s.split("-")
    if len(parts) == 3:
        parts[0] = parts[0].lstrip("0") or "0"
        s = "-".join(parts)
    return s


# ------------------------------------------------------------------ AWARE
def parse_aware() -> dict:
    """AWARE country CFs (annual, m3 world-eq deprived per m3 consumed).
    Sheet 'AWARE-annual' columns: country, Agg_CF_irri (agri), Agg_CF_non_irri
    (non-agri), Agg_CF_unspecified; plus 'World AGRI', 'World NON-AGRI',
    'World, UNKNOWN' rows at the bottom."""
    wb = _wb(AWARE_FILE)
    ws = wb["AWARE-annual"]
    countries: dict = {}
    world: dict = {}
    for row in ws.iter_rows(min_row=3, values_only=True):
        name = row[0]
        if not name:
            continue
        name = str(name).strip()
        if name == "World AGRI":
            world["agri"] = _num(row[1])
        elif name == "World NON-AGRI":
            world["non_agri"] = _num(row[1])
        elif name == "World, UNKNOWN":
            world["unspecified"] = _num(row[1])
        elif _num(row[1]) is not None or _num(row[2]) is not None:
            countries[name] = {"agri": _num(row[1]), "non_agri": _num(row[2]),
                               "unspecified": _num(row[3])}
    wb.close()
    return {"countries": countries, "world": world}


# ------------------------------------------------------------------ LANCA / SQI
def parse_lanca_sqi() -> dict:
    """EF soil quality index occupation CFs (Pt per m2a) by country and land-use type,
    De Laurentiis et al. (2019) J. Clean. Prod. 215:63-74, Supplementary mmc2, sheet
    Occupation_SQI, indicator 'Total'. Column C = world area-weighted average."""
    wb = _wb(LANCA_FILE)
    ws = wb["Occupation_SQI"]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    hdr = rows[1]
    col = {str(h).strip(): i for i, h in enumerate(hdr) if h}
    out: dict = {"world_average": {}, "countries": {}}
    indicator = None
    for r in rows[2:]:
        if r[0]:
            indicator = str(r[0]).strip()
        if indicator != "Total" or not r[1]:
            continue
        lut = str(r[1]).strip()
        out["world_average"][lut] = _num(r[2])
        for cname, i in col.items():
            if i < 5:
                continue
            v = _num(r[i])
            if v is not None:
                out["countries"].setdefault(cname, {})[lut] = v
    return out


# ------------------------------------------------------------------ USEtox
_ECO_COLS = {"household_indoor_air": 3, "industrial_indoor_air": 4, "urban_air": 5,
             "rural_air": 6, "freshwater": 7, "sea_water": 8, "natural_soil": 9,
             "agricultural_soil": 10}
_HT_COLS = {"household_indoor_air": 3, "industrial_indoor_air": 6, "urban_air": 9,
            "rural_air": 12, "freshwater": 15, "sea_water": 18, "natural_soil": 21,
            "agricultural_soil": 24}


def parse_usetox() -> list[dict]:
    """USEtox 2.14 pre-calculated MIDPOINT CFs (organics + inorganics):
    ecotox freshwater [PAF.m3.day/kg = CTUe/kg] (sheet 'Ecotox CF', cols D..K) and human
    health cancer / non-cancer [cases/kg = CTUh/kg] (sheet 'Human tox CF', cols D..AB,
    3 columns per compartment). 'n/a' -> None."""
    out: list[dict] = []
    for kind in ("organics", "inorganics"):
        path = USETOX_DIR / f"USEtox_results_{kind}.xlsx"
        wb = _wb(path)
        eco = {}
        for r in wb["Ecotox CF"].iter_rows(min_row=5, values_only=True):
            if not r[1]:
                continue
            eco[(str(r[1]).strip(), str(r[2]).strip())] = (
                {k: _num(r[i]) for k, i in _ECO_COLS.items()}, r[19] if len(r) > 19 else None)
        for r in wb["Human tox CF"].iter_rows(min_row=5, values_only=True):
            if not r[1]:
                continue
            key = (str(r[1]).strip(), str(r[2]).strip())
            e, eflag = eco.get(key, ({}, None))
            out.append({
                "cas": _norm_cas(key[0]), "name": key[1], "kind": kind,
                "ecotox_fw_ctue": e,
                "human_cancer_ctuh": {k: _num(r[i]) for k, i in _HT_COLS.items()},
                "human_noncancer_ctuh": {k: _num(r[i + 1]) for k, i in _HT_COLS.items()},
                "flag_ecotox": (str(eflag).strip() or None) if eflag else None,
                "flag_human": " / ".join(str(x) for x in r[57:59] if x) or None,
            })
        wb.close()
    return out


# ------------------------------------------------------------------ normalisation
def parse_recipe_nf() -> dict:
    """ReCiPe 2016 v1.1 midpoint normalisation (World 2010, per person per year),
    Hierarchist column, sheet 'Final normalization scores'. Returned keyed by the
    engine's frontend category names (adapter.MIDPOINT_MAP targets)."""
    wb = _wb(RECIPE_NF_FILE)
    rows = list(wb["Final normalization scores"].iter_rows(values_only=True))
    wb.close()
    by_label = {}
    for r in rows:
        if r and r[0]:
            by_label[str(r[0]).strip()] = r
    # columns: A label, B unit, C Individualist, D Hierarchist, E Egalitarian
    def h(label):
        return _num(by_label[label][3])   # column D = midpoint Hierarchic (C=I, E=E)
    fossil_parts = {k: h(k) for k in ("Crude oil", "Natural gas", "Hard coal", "Brown coal")}
    nf = {
        "Global warming": h("Global Warming - Human health"),
        "Land use": h("Land use - occupation"),
        "Water consumption": h("Water consumption - human health"),
        "Terrestrial acidification": h("Acidification - Terrestrial ecosystems"),
        "Freshwater eutrophication": h("Eutrophication - Freshwater ecosystems"),
        "Marine eutrophication": h("Eutrophication - marine ecosystems"),
        "Fossil depletion": sum(fossil_parts.values()),
        "Mineral depletion": h("Mineral resource scarcity"),
        "Particulate matter formation": h("Fine particulate matter formation - Human health"),
        "Photochemical oxidation": h("Photochemical ozone formation - Human health"),
    }
    return {"factors": nf, "fossil_components_kg_oil_eq": fossil_parts}


# EF 3.1 global normalisation factors (per person per year). NOT in the EF 3.1 CF workbook on
# disk (data/EVvinronmental_Footprint_EF3.1 holds CFs only: sheets flows, lciamethods,
# lciamethods_CF). Source: Andreasson J., Sala S. et al. (2024), "Updated characterisation
# and normalisation factors for the Environmental Footprint 3.1 method", JRC Technical
# Report JRC130796, EUR 31474 EN, Table 2 (global normalisation factors, EF 3.1).
EF31_NF_JRC = {
    "Global warming": 7550.0,                  # kg CO2-eq
    "Terrestrial acidification": 55.6,         # mol H+-eq (EF "Acidification")
    "Freshwater eutrophication": 1.61,         # kg P-eq
    "Marine eutrophication": 19.5,             # kg N-eq
    "Land use": 819000.0,                      # Pt (soil quality index)
    "Mineral depletion": 0.0636,               # kg Sb-eq
    "Particulate matter formation": 5.95e-4,   # disease incidence
    "Photochemical oxidation": 40.9,           # kg NMVOC-eq
    "Water consumption": 11500.0,              # m3 world-eq deprived
    "Fossil depletion": 65000.0,               # MJ
}


# ------------------------------------------------------------------ GWP basis
GWP_TABLE = {
    # GHG Protocol (2024) "IPCC Global Warming Potential Values", v2.0, 7 Aug 2024, table p.1
    # (data/IPCC GWP/...pdf), adapted from IPCC AR6 WG1 Ch.7 Table 7.15 (Forster et al. 2021).
    "AR4": {"CH4_non_fossil": 25, "CH4_fossil": None, "N2O": 298},
    "AR5": {"CH4_non_fossil": 28, "CH4_fossil": 30, "N2O": 265},
    "AR6": {"CH4_non_fossil": 27.0, "CH4_fossil": 29.8, "N2O": 273},
    # AR5 WITH climate-carbon feedbacks: IPCC AR5 WG1 Ch.8 Table 8.7 (Myhre et al. 2013);
    # this is the set ReCiPe 2016 v1.1 Hierarchist uses (ReCiPe2016_CFs_v1.1, sheet
    # 'Global Warming', GWP100 H: Methane 34, Fossil methane 36, Nitrous oxide 298).
    "AR5_ccfb": {"CH4_non_fossil": 34, "CH4_fossil": 36, "N2O": 298},
}


def parse_recipe_gwp() -> dict:
    wb = _wb(RECIPE_CF_FILE)
    out = {}
    for r in wb["Global Warming"].iter_rows(min_row=4, values_only=True):
        if r[0] in ("Methane", "Fossil methane", "Nitrous oxide", "Carbon dioxide"):
            out[r[0]] = _num(r[4])   # column E = GWP100 Hierarchist
    wb.close()
    return out


def gwp_basis() -> dict:
    rg = parse_recipe_gwp() if RECIPE_CF_FILE.exists() else {}
    return {
        "source_pdf": _rel(GWP_PDF),
        "source_pdf_title": "GHG Protocol, IPCC Global Warming Potential Values, v2.0 (7 Aug 2024)",
        "table": GWP_TABLE,
        "recipe_spreadsheet_gwp100_h": rg,
        "decision": (
            "Each LCIA method keeps its NATIVE GWP basis, as published and as shipped in the "
            "ecoinvent 3.11 method pack, so that background and foreground are characterised "
            "consistently within a method. ReCiPe 2016 v1.03 midpoint (H): IPCC AR5 GWP100 "
            "including climate-carbon feedbacks (CH4 non-fossil 34, CH4 fossil 36, N2O 298; "
            "Myhre et al. 2013, AR5 WG1 Table 8.7). EF 3.1: IPCC AR6 GWP100 (CH4 non-fossil 27.0, "
            "CH4 fossil 29.8, N2O 273; Forster et al. 2021, AR6 WG1 Table 7.15). Results under "
            "the two methods are therefore not directly comparable for N2O- and CH4-dominated "
            "systems; the report states which basis was used."),
        "methods": {
            "ReCiPe 2016 v1.03, midpoint (H)": {"basis": "IPCC AR5 GWP100 incl. climate-carbon feedbacks",
                                                "expected": GWP_TABLE["AR5_ccfb"]},
            "EF v3.1": {"basis": "IPCC AR6 GWP100", "expected": GWP_TABLE["AR6"]},
        },
    }


# ------------------------------------------------------------------ build JSON
def _pesticide_lookup(usetox: list[dict]) -> dict:
    by_cas: dict = {}
    for r in usetox:
        by_cas.setdefault(r["cas"], []).append(r)
    out = {}
    for ai, cases in PESTICIDE_AIS.items():
        hit = None
        for c in cases:
            if by_cas.get(_norm_cas(c)):
                hit = by_cas[_norm_cas(c)][0]
                break
        if not hit:
            out[ai] = {"cas_searched": list(cases), "found": False}
            continue
        out[ai] = {
            "found": True, "cas": hit["cas"], "usetox_name": hit["name"], "kind": hit["kind"],
            "emission_to_agricultural_soil": {
                "ecotox_freshwater_ctue_per_kg": hit["ecotox_fw_ctue"].get("agricultural_soil"),
                "human_cancer_ctuh_per_kg": hit["human_cancer_ctuh"].get("agricultural_soil"),
                "human_noncancer_ctuh_per_kg": hit["human_noncancer_ctuh"].get("agricultural_soil"),
            },
            "emission_to_freshwater": {
                "ecotox_freshwater_ctue_per_kg": hit["ecotox_fw_ctue"].get("freshwater"),
                "human_cancer_ctuh_per_kg": hit["human_cancer_ctuh"].get("freshwater"),
                "human_noncancer_ctuh_per_kg": hit["human_noncancer_ctuh"].get("freshwater"),
            },
            "emission_to_rural_air": {
                "ecotox_freshwater_ctue_per_kg": hit["ecotox_fw_ctue"].get("rural_air"),
                "human_cancer_ctuh_per_kg": hit["human_cancer_ctuh"].get("rural_air"),
                "human_noncancer_ctuh_per_kg": hit["human_noncancer_ctuh"].get("rural_air"),
            },
            "flags": {"ecotox": hit["flag_ecotox"], "human": hit["flag_human"]},
        }
    return out


def build(out_dir: Path = OUT) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).date().isoformat()
    written = {}

    aware = parse_aware()
    sub = {c: aware["countries"][c] for c in COUNTRIES if c in aware["countries"]}
    doc = {
        "id": "aware.country.annual",
        "title": "AWARE water scarcity characterisation factors, country annual aggregates",
        "unit": "m3 world-eq deprived per m3 consumed",
        "source": ("Boulay A-M et al. (2018) The WULCA consensus characterization model for water "
                   "scarcity footprints (AWARE). Int J LCA 23:368-378. Country aggregation file "
                   "AWARE_country_regions_Corrected_online_20230113, sheet AWARE-annual "
                   "(agri = Agg_CF_irri, non_agri = Agg_CF_non_irri)."),
        "file": _rel(AWARE_FILE), "sha256": _sha256(AWARE_FILE),
        "version_note": ("The folder is named AWARE2.0 but the country file is the WULCA corrected "
                         "release of 2023-01-13 (AWARE 1.2c aggregation); the watershed file is "
                         "AWARE_watersheds_v12_20240531. 'World, UNKNOWN' (42.95) equals the EF 3.1 "
                         "'Water use' CF shipped in the ecoinvent 3.11 method pack."),
        "licence": "WULCA, free for use with citation",
        "world": aware["world"], "countries": sub, "all_countries": aware["countries"],
        "built": now,
    }
    (out_dir / "aware_country_cfs.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    written["aware"] = len(aware["countries"])

    lanca = parse_lanca_sqi()
    doc = {
        "id": "lanca.sqi.occupation",
        "title": "EF soil quality index (LANCA-based) occupation CFs by country",
        "unit": "Pt per m2a (dimensionless soil quality index points)",
        "source": ("De Laurentiis V, Secchi M, Bos U, Horn R, Laurent A, Sala S (2019). Soil quality "
                   "index: exploring options for a comprehensive assessment of land use impacts in "
                   "LCA. J Clean Prod 215:63-74. Supplementary file mmc2, sheet Occupation_SQI, "
                   "indicator Total (LANCA v2.5 indicators aggregated as in EF 3.x)."),
        "file": _rel(LANCA_FILE), "sha256": _sha256(LANCA_FILE),
        "licence": "Elsevier supplementary data; factors are those adopted by EF 3.x (JRC)",
        "ecoinvent_flow_to_land_type": LAND_TYPE_MAP,
        "world_average": lanca["world_average"],
        "countries": {c: lanca["countries"].get(c, {}) for c in COUNTRIES},
        "built": now,
    }
    (out_dir / "lanca_sqi_occupation.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    written["lanca_countries"] = len(lanca["countries"])

    usetox = parse_usetox()
    doc = {
        "id": "usetox214.pesticides",
        "title": "USEtox 2.14 midpoint CFs for common West African pesticide active ingredients",
        "units": {"ecotox": "CTUe per kg emitted (PAF.m3.day/kg)", "human": "CTUh per kg emitted (cases/kg)"},
        "source": ("USEtox 2.14 pre-calculated results (built 20-Aug-2024), organics database 2.01 / "
                   "inorganics; data/USEtox_2.14/Results/USEtox_results_{organics,inorganics}.xlsx, "
                   "sheets 'Ecotox CF' (midpoint, freshwater) and 'Human tox CF' (midpoint)."),
        "files": [_rel(USETOX_DIR / "USEtox_results_organics.xlsx"),
                  _rel(USETOX_DIR / "USEtox_results_inorganics.xlsx")],
        "licence": "USEtox, free for non-commercial and commercial use with citation (usetox.org)",
        "note": ("Reference lookup only. Toxicity is CHARACTERISED with the method pack as shipped "
                 "(ReCiPe 2016 1,4-DCB-eq or EF 3.1 CTUe/CTUh, the latter USEtox 2.1-based with EF "
                 "adaptations), so background and foreground use the same toxicity model. This table "
                 "lets a reviewer compare against USEtox 2.14 and documents gaps."),
        "active_ingredients": _pesticide_lookup(usetox),
        "built": now,
    }
    (out_dir / "usetox_pesticide_cfs.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    written["usetox_substances"] = len(usetox)

    rnf = parse_recipe_nf()
    doc = {
        "id": "normalisation.factors",
        "title": "Midpoint normalisation factors (per person per year) for the single score",
        "recipe_2016": {
            "factors": rnf["factors"],
            "source": ("ReCiPe 2016 v1.1 normalisation, World 2010, Hierarchist, midpoint; "
                       "data/ReCipe2016/Normalization scores ReCiPe2016v1.1_20190514.xlsx, sheet "
                       "'Final normalization scores', column D (Hierarchist)."),
            "file": _rel(RECIPE_NF_FILE), "sha256": _sha256(RECIPE_NF_FILE),
            "fossil_components_kg_oil_eq": rnf["fossil_components_kg_oil_eq"],
            "caveat": ("Fossil depletion = crude oil + natural gas + hard coal + brown coal rows of the "
                       "spreadsheet. The natural gas row reads 0.40 kg oil-eq/person/yr in the published "
                       "file, which looks like a unit slip (crude oil reads 570); it is carried as "
                       "published and flagged for review."),
        },
        "ef_3_1": {
            "factors": EF31_NF_JRC,
            "source": ("Andreasson J, Sala S et al. (2024) Updated characterisation and normalisation "
                       "factors for the Environmental Footprint 3.1 method, JRC130796, EUR 31474 EN, "
                       "Table 2 (global NF). Not present in data/EVvinronmental_Footprint_EF3.1, which "
                       "holds characterisation factors only."),
        },
        "built": now,
    }
    (out_dir / "normalisation_factors.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")

    (out_dir / "gwp_basis.json").write_text(json.dumps({**gwp_basis(), "built": now}, indent=1),
                                            encoding="utf-8")
    return written


# ------------------------------------------------------------------ store ingest
_TABLES = """
CREATE TABLE IF NOT EXISTS gmg_reference_sources (
    id INTEGER PRIMARY KEY, dataset TEXT NOT NULL, version TEXT, file TEXT, sha256 TEXT,
    citation TEXT, licence TEXT, n_rows INTEGER, ingested_at TEXT NOT NULL,
    UNIQUE(dataset, version));
CREATE TABLE IF NOT EXISTS gmg_aware_country_cfs (
    country TEXT PRIMARY KEY, cf_agri REAL, cf_non_agri REAL, cf_unspecified REAL,
    ref_source_id INTEGER REFERENCES gmg_reference_sources(id));
CREATE TABLE IF NOT EXISTS gmg_lanca_sqi_occupation (
    country TEXT NOT NULL, land_type TEXT NOT NULL, cf REAL,
    ref_source_id INTEGER REFERENCES gmg_reference_sources(id), PRIMARY KEY(country, land_type));
CREATE TABLE IF NOT EXISTS gmg_usetox_cfs (
    cas TEXT, name TEXT NOT NULL, kind TEXT, compartment TEXT NOT NULL,
    ecotox_fw_ctue REAL, human_cancer_ctuh REAL, human_noncancer_ctuh REAL, flags TEXT,
    ref_source_id INTEGER REFERENCES gmg_reference_sources(id), PRIMARY KEY(name, kind, compartment));
CREATE TABLE IF NOT EXISTS gmg_normalisation_factors (
    method TEXT NOT NULL, category TEXT NOT NULL, nf REAL NOT NULL,
    ref_source_id INTEGER REFERENCES gmg_reference_sources(id), PRIMARY KEY(method, category));
CREATE TABLE IF NOT EXISTS gmg_gwp_values (
    basis TEXT NOT NULL, gas TEXT NOT NULL, gwp100 REAL,
    ref_source_id INTEGER REFERENCES gmg_reference_sources(id), PRIMARY KEY(basis, gas));
CREATE TABLE IF NOT EXISTS gmg_regionalised_flows (
    flow_uid TEXT PRIMARY KEY, kind TEXT NOT NULL, country TEXT NOT NULL, use_type TEXT,
    base_flow_uid TEXT NOT NULL, base_flow_name TEXT, regional_cf REAL, regional_cf_unit TEXT,
    n_cfs_copied INTEGER, ref_source_id INTEGER REFERENCES gmg_reference_sources(id));
"""


def _ref_source(conn, dataset, version, file: Path | None, citation, licence, n_rows) -> int:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO gmg_reference_sources(dataset, version, file, sha256, citation, "
        "licence, n_rows, ingested_at) VALUES (?,?,?,?,?,?,?,?)",
        (dataset, version, _rel(file) if file else None, _sha256(file) if file else None,
         citation, licence, n_rows, now))
    return conn.execute("SELECT id FROM gmg_reference_sources WHERE dataset=? AND version=?",
                        (dataset, version)).fetchone()[0]


def _regional_source_id(conn) -> int:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO sources(name, version, license, notes, created_at) VALUES (?,?,?,?,?)",
        (REGIONAL_SOURCE_NAME, REGIONAL_SOURCE_VERSION,
         "AWARE (WULCA) and EF SQI (JRC/De Laurentiis 2019) factors, citation required",
         "Regionalised on-farm water and land flows added by ingestion/gmg_reference.py; "
         "CFs copied from the ecoinvent base flow except EF v3.x Water use / Land use.",
         now))
    return conn.execute("SELECT id FROM sources WHERE name=? AND version=?",
                        (REGIONAL_SOURCE_NAME, REGIONAL_SOURCE_VERSION)).fetchone()[0]


def regional_uid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "gmg:regionalised:" + name))


def water_flow_name(country: str, use: str) -> str:
    return f"Water, consumptive use, {use.replace('_', '-')}, {country} (AWARE)"


def land_flow_name(base_name: str, country: str) -> str:
    return f"{base_name}, {country} (EF soil quality index)"


def _base_flow(conn, name: str, category: str) -> str | None:
    r = conn.execute(
        "SELECT f.uid FROM flows f JOIN sources s ON s.id=f.source_id WHERE f.name=? AND "
        "f.category=? AND f.flow_type='ELEMENTARY_FLOW' AND s.name='ecoinvent'",
        (name, category)).fetchone()
    return r[0] if r else None


def _is_ef_cat(method_name: str, cat_name: str, which: str) -> bool:
    return (method_name or "").startswith("EF v3") and (cat_name or "").lower().startswith(which)


def _add_regional_flow(conn, src_id, ref_id, base_uid, base_name, base_cat, name, kind,
                       country, use_type, regional_cf, unit, which) -> int:
    uid = regional_uid(name)
    has_fed = "fed_id" in {r[1] for r in conn.execute("PRAGMA table_info(flows)")}
    if conn.execute("SELECT 1 FROM flows WHERE uid=?", (uid,)).fetchone():
        return 0
    ref_unit = conn.execute("SELECT ref_unit FROM flows WHERE uid=?", (base_uid,)).fetchone()[0]
    cols = "uid, source_id, name, category, flow_type, ref_unit, cas, formula, flow_key, cas_key"
    vals = [uid, src_id, name, base_cat, "ELEMENTARY_FLOW", ref_unit, None, None, None, None]
    if has_fed:
        cols += ", fed_id"
        vals.append("__NOMAP__")       # never bridged: CFs are attached by UID
    conn.execute(f"INSERT INTO flows({cols}) VALUES ({','.join('?' * len(vals))})", vals)
    n = 0
    for r in conn.execute(
        "SELECT cf.category_uid, cf.factor, cf.unit, ic.name, m.name FROM characterization_factors cf "
        "JOIN impact_categories ic ON ic.uid=cf.category_uid JOIN impact_methods m ON m.uid=ic.method_uid "
        "WHERE cf.flow_uid=?", (base_uid,)).fetchall():
        cat_uid, fac, cunit, cname, mname = r
        if regional_cf is not None and _is_ef_cat(mname, cname, which):
            fac = regional_cf
        conn.execute("INSERT INTO characterization_factors(category_uid, flow_uid, flow_name, factor, unit) "
                     "VALUES (?,?,?,?,?)", (cat_uid, uid, name, fac, cunit))
        n += 1
    conn.execute(
        "INSERT INTO gmg_regionalised_flows(flow_uid, kind, country, use_type, base_flow_uid, "
        "base_flow_name, regional_cf, regional_cf_unit, n_cfs_copied, ref_source_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (uid, kind, country, use_type, base_uid, base_name, regional_cf, unit, n, ref_id))
    return 1


def ingest(db: Path = DEFAULT_DB, ref_dir: Path = OUT) -> dict:
    """Load engine/lcia_reference/*.json + the full spreadsheets into the store (additive)."""
    aware_doc = json.loads((ref_dir / "aware_country_cfs.json").read_text(encoding="utf-8"))
    lanca_doc = json.loads((ref_dir / "lanca_sqi_occupation.json").read_text(encoding="utf-8"))
    nf_doc = json.loads((ref_dir / "normalisation_factors.json").read_text(encoding="utf-8"))
    gwp_doc = json.loads((ref_dir / "gwp_basis.json").read_text(encoding="utf-8"))
    full_lanca = parse_lanca_sqi() if LANCA_FILE.exists() else {"countries": lanca_doc["countries"],
                                                                 "world_average": lanca_doc["world_average"]}
    usetox = parse_usetox() if USETOX_DIR.exists() else []

    conn = sqlite3.connect(str(db), timeout=120)
    counts = {}
    try:
        conn.executescript(_TABLES)
        with conn:
            rid = _ref_source(conn, "AWARE", "country annual, corrected 2023-01-13", AWARE_FILE,
                              aware_doc["source"], aware_doc["licence"], len(aware_doc["all_countries"]) + 3)
            for c, v in aware_doc["all_countries"].items():
                conn.execute("INSERT OR IGNORE INTO gmg_aware_country_cfs VALUES (?,?,?,?,?)",
                             (c, v["agri"], v["non_agri"], v["unspecified"], rid))
            w = aware_doc["world"]
            conn.execute("INSERT OR IGNORE INTO gmg_aware_country_cfs VALUES (?,?,?,?,?)",
                         (WORLD, w["agri"], w["non_agri"], w["unspecified"], rid))
            counts["aware_rows"] = len(aware_doc["all_countries"]) + 1

            lid = _ref_source(conn, "EF SQI (LANCA) occupation", "De Laurentiis et al. 2019 mmc2",
                              LANCA_FILE, lanca_doc["source"], lanca_doc["licence"], None)
            n = 0
            for lut, v in full_lanca["world_average"].items():
                conn.execute("INSERT OR IGNORE INTO gmg_lanca_sqi_occupation VALUES (?,?,?,?)",
                             (WORLD, lut, v, lid)); n += 1
            for c, d in full_lanca["countries"].items():
                for lut, v in d.items():
                    conn.execute("INSERT OR IGNORE INTO gmg_lanca_sqi_occupation VALUES (?,?,?,?)",
                                 (c, lut, v, lid)); n += 1
            counts["lanca_rows"] = n

            if usetox:
                uid_ = _ref_source(conn, "USEtox", "2.14 (results built 2024-08-20)", USETOX_DIR,
                                   "USEtox 2.14 pre-calculated midpoint results, organics db 2.01 + inorganics",
                                   "USEtox licence, citation required", len(usetox))
                n = 0
                for r in usetox:
                    for comp in _ECO_COLS:
                        conn.execute("INSERT OR IGNORE INTO gmg_usetox_cfs VALUES (?,?,?,?,?,?,?,?,?)",
                                     (r["cas"], r["name"], r["kind"], comp, r["ecotox_fw_ctue"].get(comp),
                                      r["human_cancer_ctuh"].get(comp), r["human_noncancer_ctuh"].get(comp),
                                      json.dumps({"ecotox": r["flag_ecotox"], "human": r["flag_human"]}), uid_))
                        n += 1
                counts["usetox_rows"] = n

            nid = _ref_source(conn, "Normalisation factors", "ReCiPe 2016 v1.1 + EF 3.1 (JRC 2024)",
                              RECIPE_NF_FILE, nf_doc["recipe_2016"]["source"] + " | " + nf_doc["ef_3_1"]["source"],
                              "ReCiPe: RIVM, free with citation; EF: JRC, CC-BY", None)
            for cat, v in nf_doc["recipe_2016"]["factors"].items():
                conn.execute("INSERT OR IGNORE INTO gmg_normalisation_factors VALUES (?,?,?,?)",
                             ("ReCiPe 2016 midpoint (H)", cat, v, nid))
            for cat, v in nf_doc["ef_3_1"]["factors"].items():
                conn.execute("INSERT OR IGNORE INTO gmg_normalisation_factors VALUES (?,?,?,?)",
                             ("EF v3.1", cat, v, nid))

            gid = _ref_source(conn, "IPCC GWP100", "GHG Protocol table v2.0 2024-08-07", GWP_PDF,
                              gwp_doc["source_pdf_title"], "IPCC, citation required", None)
            for basis, gases in gwp_doc["table"].items():
                for gas, v in gases.items():
                    conn.execute("INSERT OR IGNORE INTO gmg_gwp_values VALUES (?,?,?,?)", (basis, gas, v, gid))

            # ---- regionalised foreground flows
            src_id = _regional_source_id(conn)
            nflows = 0
            water_base = _base_flow(conn, "Water", "Elementary flows/Emission to air/unspecified")
            if water_base:
                for c in (*COUNTRIES, WORLD):
                    v = (aware_doc["countries"].get(c) or aware_doc["all_countries"].get(c)
                         if c != WORLD else aware_doc["world"])
                    if not v:
                        continue
                    for use in ("agri", "non_agri"):
                        if v.get(use) is None:
                            continue
                        nflows += _add_regional_flow(
                            conn, src_id, rid, water_base, "Water", "Elementary flows/Emission to air/unspecified",
                            water_flow_name(c, use), "water", c, use, v[use],
                            "m3 world-eq deprived per m3", "water use")
            for base_name, lut in LAND_TYPE_MAP.items():
                base = _base_flow(conn, base_name, "Elementary flows/Resource/land")
                if not base:
                    continue
                for c in COUNTRIES:
                    v = (full_lanca["countries"].get(c) or {}).get(lut)
                    if v is None:
                        continue
                    nflows += _add_regional_flow(
                        conn, src_id, lid, base, base_name, "Elementary flows/Resource/land",
                        land_flow_name(base_name, c), "land", c, lut, v, "Pt per m2a", "land use")
            counts["regionalised_flows_added"] = nflows
    finally:
        conn.close()
    return counts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("action", choices=["build", "ingest", "all"])
    ap.add_argument("--db", default=str(DEFAULT_DB))
    a = ap.parse_args(argv)
    if a.action in ("build", "all"):
        print("build:", build())
    if a.action in ("ingest", "all"):
        print("ingest:", ingest(Path(a.db)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
