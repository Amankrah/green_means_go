#!/usr/bin/env python3
import json
import sqlite3
import sys
from pathlib import Path

db = Path(sys.argv[1])
aid = sys.argv[2]
conn = sqlite3.connect(db)
row = conn.execute(
    "select payload_json, request_json from assessments where id=?", (aid,)
).fetchone()
if not row:
    raise SystemExit("not found")
p = json.loads(row[0])
r = json.loads(row[1] or "{}")
ss = p.get("single_score") or {}
out = {
    "id": aid,
    "score": ss.get("value"),
    "band": ss.get("band"),
    "contributions": ss.get("contributions"),
    "midpoints": {
        k: v.get("value")
        for k, v in (p.get("midpoint_impacts") or {}).items()
        if isinstance(v, dict)
    },
    "contribution_split": p.get("contribution") or p.get("contributions_by_stage"),
    "notes": p.get("notes") or [],
    "matches": [
        {
            "name": m.get("name"),
            "amount": m.get("amount"),
            "unit": m.get("unit"),
            "matched": (m.get("matched") or {}).get("name")
            if isinstance(m.get("matched"), dict)
            else m.get("matched"),
        }
        for m in (p.get("input_matches") or [])
    ],
    "inventory_land_like": [],
    "request_foods": [
        {k: f.get(k) for k in ("name", "quantity_kg", "area_allocated")}
        for f in (r.get("foods") or [])
    ],
}
# inventory may be dict of flow_uid -> {name, amount, unit} or other shapes
inv = p.get("inventory") or {}
out["inventory_type"] = type(inv).__name__
out["inventory_len"] = len(inv) if hasattr(inv, "__len__") else None
if isinstance(inv, dict):
    for uid, rec in list(inv.items())[:5]:
        out.setdefault("inventory_sample", []).append({"key": uid, "val_type": type(rec).__name__, "val": rec})
    for uid, rec in inv.items():
        if isinstance(rec, dict):
            name = str(rec.get("name") or uid)
            amount = rec.get("amount")
            unit = rec.get("unit")
        else:
            name = str(uid)
            amount = rec
            unit = None
        lname = name.lower()
        if any(x in lname for x in ("land", "occup", "nitrate", "n2o", "nitrous")):
            out["inventory_land_like"].append(
                {"uid": uid, "name": name, "amount": amount, "unit": unit}
            )
# contribution split keys often expose on_farm land
contrib = p.get("contribution") or {}
if isinstance(contrib, dict):
    out["contribution_keys"] = list(contrib.keys())
    for stage, cats in contrib.items():
        if not isinstance(cats, dict):
            continue
        for cat in ("Land use", "Marine eutrophication", "Global warming", "Fossil depletion"):
            if cat in cats:
                out.setdefault("contribution_values", {})[f"{stage}:{cat}"] = cats[cat]
# also check nested engine fields
for key in ("lci_inventory", "on_farm_inventory"):
    if key in p:
        out[key + "_len"] = len(p[key]) if hasattr(p[key], "__len__") else type(p[key]).__name__

print(json.dumps(out, indent=2, ensure_ascii=True, default=str))
