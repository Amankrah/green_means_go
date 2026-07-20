#!/usr/bin/env python3
import json
import sqlite3
import sys

aid = sys.argv[1] if len(sys.argv) > 1 else None
db = sys.argv[2] if len(sys.argv) > 2 else "data/app/greenmeansgo.sqlite"
conn = sqlite3.connect(db)
if not aid:
    row = conn.execute(
        "select id from assessments order by created_at desc limit 1"
    ).fetchone()
    aid = row[0] if row else None
row = conn.execute(
    "select id, single_score, payload_json from assessments where id=?", (aid,)
).fetchone()
if not row:
    print("not found", aid)
    sys.exit(1)
p = json.loads(row[2])
ss = p.get("single_score") or {}
out = {
    "id": aid,
    "value": ss.get("value") if isinstance(ss, dict) else ss,
    "band": ss.get("band") if isinstance(ss, dict) else None,
    "n_categories": len(ss.get("contributions") or {}) if isinstance(ss, dict) else None,
    "contributions": ss.get("contributions") if isinstance(ss, dict) else None,
    "methodology": ss.get("methodology") if isinstance(ss, dict) else None,
    "midpoints": {
        k: {"value": v.get("value"), "unit": v.get("unit")}
        for k, v in (p.get("midpoint_impacts") or {}).items()
        if isinstance(v, dict)
    },
    "endpoints": {
        k: {"value": v.get("value"), "unit": v.get("unit")}
        for k, v in (p.get("endpoint_impacts") or {}).items()
        if isinstance(v, dict)
    },
}
print(json.dumps(out, indent=2, ensure_ascii=True))
