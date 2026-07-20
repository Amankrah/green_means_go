#!/usr/bin/env python3
"""Compare two saved assessment payloads (ids) from a sqlite DB."""
import json
import sqlite3
import sys
from pathlib import Path


def load(db: Path, aid: str) -> dict:
    conn = sqlite3.connect(db)
    row = conn.execute(
        "select payload_json from assessments where id=?", (aid,)
    ).fetchone()
    if not row:
        raise SystemExit(f"not found {aid} in {db}")
    return json.loads(row[0])


def summary(p: dict) -> dict:
    ss = p.get("single_score") or {}
    mi = p.get("midpoint_impacts") or {}
    notes = p.get("notes") or []
    if not notes and isinstance(p.get("data_quality"), dict):
        notes = p["data_quality"].get("notes") or []
    matches = p.get("input_matches") or []
    return {
        "company": p.get("company_name"),
        "country": p.get("country"),
        "region": p.get("region"),
        "score": ss.get("value") if isinstance(ss, dict) else ss,
        "band": ss.get("band") if isinstance(ss, dict) else None,
        "contributions": ss.get("contributions") if isinstance(ss, dict) else None,
        "midpoints": {
            k: {"value": v.get("value"), "unit": v.get("unit")}
            for k, v in mi.items()
            if isinstance(v, dict)
        },
        "endpoints": {
            k: v.get("value")
            for k, v in (p.get("endpoint_impacts") or {}).items()
            if isinstance(v, dict)
        },
        "notes": notes,
        "matches": [
            {
                "name": m.get("name"),
                "amount": m.get("amount"),
                "unit": m.get("unit"),
                "matched": (m.get("matched") or {}).get("name")
                if isinstance(m.get("matched"), dict)
                else m.get("matched"),
            }
            for m in matches
        ],
        "foods": (p.get("farm_profile") or {}).get("crops")
        or p.get("foods")
        or (p.get("request") or {}).get("foods"),
    }


def main():
    db = Path(sys.argv[1])
    aid = sys.argv[2]
    p = load(db, aid)
    print(json.dumps(summary(p), indent=2, ensure_ascii=True, default=str))


if __name__ == "__main__":
    main()
