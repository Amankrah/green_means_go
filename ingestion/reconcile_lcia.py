#!/usr/bin/env python3
"""
reconcile_lcia.py: reconcile the published method spreadsheets on disk against the
ecoinvent 3.11 LCIA method pack actually used for characterisation (canonical store).

  * ReCiPe 2016 v1.1 CFs (data/ReCipe2016/ReCiPe2016_CFs_v1.1_20180117.xlsx), Hierarchist,
    vs store method "ReCiPe 2016 v1.03, midpoint (H)": a curated sample covering every
    category the engine reports for crops (climate, acidification, PM, ozone formation,
    eutrophication, land occupation, water) plus freshwater ecotoxicity of the West African
    pesticide active ingredients.
  * EF 3.1 CFs (data/EVvinronmental_Footprint_EF3.1/EF-LCIAMethod_CF(EF-v3.1).xlsx, sheet
    lciamethods_CF, global rows) vs store method "EF v3.1", matched by CAS (else name) and
    emission medium, for all non-toxicity categories plus the pesticide AIs for toxicity.

Writes engine/lcia_reference/cf_reconciliation.json with counts and every difference
> 1 %. Usage: python -m ingestion.reconcile_lcia
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from ingestion.canonical_store import DEFAULT_DB                       # noqa: E402
from ingestion.gmg_reference import (RECIPE_CF_FILE, EF_FILE, OUT, PESTICIDE_AIS,  # noqa: E402
                                     _norm_cas, _num, _wb, _rel)

TOL = 0.01
RECIPE_METHOD = "ReCiPe 2016 v1.03, midpoint (H)"
EF_METHOD = "EF v3.1"


def _rel_diff(a: float, b: float) -> float:
    if a == b:
        return 0.0
    d = max(abs(a), abs(b))
    return abs(a - b) / d if d else 0.0


def _store_cfs(conn, method: str, category: str) -> list[tuple]:
    return conn.execute(
        "SELECT f.name, f.category, f.cas, cf.factor FROM characterization_factors cf "
        "JOIN impact_categories ic ON ic.uid=cf.category_uid JOIN impact_methods m ON m.uid=ic.method_uid "
        "LEFT JOIN flows f ON f.uid=cf.flow_uid WHERE m.name=? AND ic.name=?", (method, category)).fetchall()


def _medium(cat: str | None) -> str:
    c = (cat or "").lower()
    for k in ("air", "water", "soil"):
        if f"emission to {k}" in c or f"emissions to {k}" in c:
            return k
    if "resource" in c or "land use" in c or "resources" in c:
        return "resource"
    return "other"


# ------------------------------------------------------------------ ReCiPe
_RECIPE_SAMPLE = [
    # (sheet, store category, sheet substance -> store flow name, H column index, (opt) compartment col/val)
    ("Global Warming", "Climate change", {"Carbon dioxide": "Carbon dioxide, fossil", "Methane": "Methane, non-fossil",
                                          "Fossil methane": "Methane, fossil", "Nitrous oxide": "Dinitrogen monoxide"}, 0, 4),
    ("Terrestrial acidification", "Acidification: terrestrial",
     {"NOx": "Nitrogen oxides", "NH3": "Ammonia", "SO2": "Sulfur dioxide"}, 0, 2),
    ("Particulate matter formation", "Particulate matter formation",
     {"NH3": "Ammonia", "NOx": "Nitrogen oxides", "SO2": "Sulfur dioxide", "PM2.5": "Particulates, < 2.5 um"}, 1, 3),
    ("Human damage ozone formation", "Photochemical oxidant formation: human health",
     {"nitrogen oxides (as nitrogen dioxide)": "Nitrogen oxides"}, 1, 5),
]


def reconcile_recipe(conn) -> dict:
    wb = _wb(RECIPE_CF_FILE)
    compared, diffs = 0, []

    def check(cat, store_name, val, medium=None, label=None):
        nonlocal compared
        rows = [r for r in _store_cfs(conn, RECIPE_METHOD, cat) if r[0] == store_name
                and (medium is None or _medium(r[1]) == medium)]
        if not rows or val is None:
            return
        compared += 1
        best = min(_rel_diff(val, r[3]) for r in rows)
        if best > TOL:
            diffs.append({"category": cat, "flow": label or store_name, "spreadsheet": val,
                          "store_values": sorted({r[3] for r in rows}), "rel_diff": round(best, 4)})

    for sheet, cat, names, key_col, h_col in _RECIPE_SAMPLE:
        for r in wb[sheet].iter_rows(min_row=3, values_only=True):
            k = r[key_col] if r[key_col] in names else None
            if k:
                check(cat, names[k], _num(r[h_col]))
    for r in wb["Freshwater eutrophication"].iter_rows(min_row=4, values_only=True):
        nm = str(r[0] or "").strip()
        if r[1] == "freshwater" and nm in ("Phosphorus (P)", "Phosphate (PO43-)"):
            check("Eutrophication: freshwater", "Phosphorus" if "P)" in nm else "Phosphate", _num(r[3]), "water")
    for r in wb["Marine eutrophication"].iter_rows(min_row=4, values_only=True):
        if r[0] == "NO3" and r[1] == "freshwater":
            check("Eutrophication: marine", "Nitrate", _num(r[2]), "water")
    for r in wb["Land occupation"].iter_rows(min_row=3, values_only=True):
        if r[0] and str(r[0]).startswith("Occupation"):
            check("Land use", str(r[0]).strip(), _num(r[3]), "resource")
    for r in wb["Water consumption"].iter_rows(min_row=3, values_only=True):
        if r[0] == "Water consumption":
            check("Water use", "Water", _num(r[2]), "air")
            break
    # pesticide AIs, freshwater ecotoxicity, emission to agricultural soil (H)
    cas_ai = {_norm_cas(c): ai for ai, cs in PESTICIDE_AIS.items() for c in cs}
    pest = []
    store_fw = _store_cfs(conn, RECIPE_METHOD, "Ecotoxicity: freshwater")
    for r in wb["Freshwater ecotoxicity"].iter_rows(min_row=4, values_only=True):
        cas = _norm_cas(r[0])
        if cas in cas_ai and "agricultural" in str(r[4] or ""):
            val = _num(r[6])
            rows = [s for s in store_fw if _norm_cas(s[2]) == cas and "agricultural" in (s[1] or "")]
            entry = {"ai": cas_ai[cas], "cas": cas, "spreadsheet_h": val,
                     "store_values": sorted({s[3] for s in rows})}
            if rows and val is not None:
                compared += 1
                entry["rel_diff"] = round(min(_rel_diff(val, s[3]) for s in rows), 4)
                if entry["rel_diff"] > TOL:
                    diffs.append({"category": "Ecotoxicity: freshwater", "flow": f"{cas_ai[cas]} to agri soil",
                                  "spreadsheet": val, "store_values": entry["store_values"],
                                  "rel_diff": entry["rel_diff"]})
            pest.append(entry)
    wb.close()
    return {"method": RECIPE_METHOD, "file": _rel(RECIPE_CF_FILE), "n_compared": compared,
            "n_diff_gt_1pct": len(diffs), "differences": diffs, "pesticide_fw_ecotox_agri_soil": pest}


# ------------------------------------------------------------------ EF 3.1
_EF_CAT = {
    "Climate change": "Climate change", "Acidification": "Acidification",
    "Eutrophication marine": "Eutrophication: marine",
    "Eutrophication, freshwater": "Eutrophication: freshwater",
    "Eutrophication, terrestrial": "Eutrophication: terrestrial",
    "Land use": "Land use", "Water use": "Water use",
    "EF-particulate matter": "Particulate matter formation",
    "Photochemical ozone formation - human health": "Photochemical oxidant formation: human health",
    "Ozone depletion": "Ozone depletion",
    "Ionising radiation, human health": "Ionising radiation: human health",
    "Resource use, fossils": "Energy resources: non-renewable",
    "Resource use, minerals and metals": "Material resources: metals/minerals",
}
_EF_TOX = {"Ecotoxicity, freshwater": "Ecotoxicity: freshwater",
           "Human toxicity, cancer": "Human toxicity: carcinogenic",
           "Human toxicity, non-cancer": "Human toxicity: non-carcinogenic"}


def reconcile_ef(conn) -> dict:
    wb = _wb(EF_FILE)
    pest_cas = {_norm_cas(c) for cs in PESTICIDE_AIS.values() for c in cs}
    sheet_vals: dict = {}
    for r in wb["lciamethods_CF"].iter_rows(min_row=2, values_only=True):
        cat = r[3]
        loc = (r[5] or "").strip() if isinstance(r[5], str) else r[5]
        if loc not in (None, "", "GLO"):
            continue
        store_cat = _EF_CAT.get(cat) or _EF_TOX.get(cat)
        if not store_cat:
            continue
        sheet_vals.setdefault(store_cat, []).append((str(r[1] or "").strip().lower(), _medium(r[7]),
                                                     str(r[8] or "").lower(), _num(r[4])))
    # CAS per EF flow uuid from sheet 'flows'
    ef_cas = {}
    for r in wb["flows"].iter_rows(min_row=2, values_only=True):
        if r[2]:
            ef_cas[str(r[1] or "").strip().lower()] = _norm_cas(r[2])
    wb.close()
    compared, unmatched, diffs = 0, 0, []
    for cat, vals in sheet_vals.items():
        is_tox = cat in _EF_TOX.values()
        store = _store_cfs(conn, EF_METHOD, cat)
        by_name: dict = {}
        by_cas: dict = {}
        for name, fcat, cas, fac in store:
            med = _medium(fcat)
            by_name.setdefault((str(name or "").lower(), med), []).append(fac)
            if cas:
                by_cas.setdefault((_norm_cas(cas), med), []).append(fac)
        for name, med, sub, val in vals:
            if val is None:
                continue
            cas = ef_cas.get(name)
            if is_tox and cas not in pest_cas:
                continue
            if is_tox and "agricultural" not in sub:
                continue
            cands = by_cas.get((cas, med)) if cas else None
            if not cands:
                cands = by_name.get((name, med))
            if not cands:
                unmatched += 1
                continue
            compared += 1
            best = min(_rel_diff(val, c) for c in cands)
            if best > TOL:
                diffs.append({"category": cat, "flow": name, "medium": med, "sub": sub, "cas": cas,
                              "spreadsheet": val, "store_values": sorted(set(cands))[:6],
                              "rel_diff": round(best, 4)})
    return {"method": EF_METHOD, "file": _rel(EF_FILE), "n_compared": compared,
            "n_unmatched_by_name_or_cas": unmatched, "n_diff_gt_1pct": len(diffs),
            "differences": sorted(diffs, key=lambda d: -d["rel_diff"])}


def pesticide_coverage(conn) -> dict:
    """For each AI: does an agricultural-soil emission flow exist in the store, and does it
    carry CFs under the two served methods' toxicity categories (by exact UID)?"""
    out = {}
    cats = {RECIPE_METHOD: ("Ecotoxicity: freshwater", "Human toxicity: carcinogenic", "Human toxicity: non-carcinogenic"),
            EF_METHOD: ("Ecotoxicity: freshwater", "Human toxicity: carcinogenic", "Human toxicity: non-carcinogenic")}
    for ai, cases in PESTICIDE_AIS.items():
        flows = []
        for c in cases:
            p = c.split("-")
            padded = p[0].zfill(6) + "-" + "-".join(p[1:])
            flows += conn.execute(
                "SELECT f.uid, f.name, s.name FROM flows f JOIN sources s ON s.id=f.source_id WHERE (f.cas=? OR f.cas=?) "
                "AND f.category LIKE '%Emission to soil/agricultural%' AND f.flow_type='ELEMENTARY_FLOW'",
                (c, padded)).fetchall()
        entry = {"store_flows": [{"name": f[1], "source": f[2]} for f in flows], "cfs": {}}
        for m, cs in cats.items():
            for cat in cs:
                vals = []
                for f in flows:
                    r = conn.execute(
                        "SELECT cf.factor FROM characterization_factors cf JOIN impact_categories ic ON ic.uid=cf.category_uid "
                        "JOIN impact_methods mm ON mm.uid=ic.method_uid WHERE mm.name=? AND ic.name=? AND cf.flow_uid=?",
                        (m, cat, f[0])).fetchone()
                    if r:
                        vals.append(r[0])
                entry["cfs"][f"{m} | {cat}"] = sorted(set(vals)) or None
        entry["gaps"] = ([] if flows else ["no agricultural-soil emission flow in store"]) + [
            k for k, v in entry["cfs"].items() if v is None and flows]
        out[ai] = entry
    return out


def main() -> int:
    conn = sqlite3.connect(f"file:{DEFAULT_DB}?mode=ro", uri=True)
    try:
        doc = {"generated": datetime.now(timezone.utc).date().isoformat(), "tolerance": TOL,
               "recipe": reconcile_recipe(conn), "ef_3_1": reconcile_ef(conn),
               "pesticide_coverage": pesticide_coverage(conn)}
    finally:
        conn.close()
    (OUT / "cf_reconciliation.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk.startswith("n_")}
                      for k, v in doc.items() if isinstance(v, dict) and "n_compared" in v}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
