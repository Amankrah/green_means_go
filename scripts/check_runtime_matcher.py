#!/usr/bin/env python3
"""Check what the live API workers would use for matching."""
import os
import sys
from pathlib import Path

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
sys.path.insert(0, str(root))
os.chdir(root)

# Mimic uvicorn --env-file app/.env
env_path = root / "app" / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ[k.strip()] = v.strip().strip('"').strip("'")

print("openai_import", end=" ")
try:
    import openai
    print("OK", openai.__version__)
except Exception as e:
    print("FAIL", e)

from ingestion.matching import default_embedder
emb = default_embedder()
print("embedder", emb.name)

# Inspect newest assessment
import json
import sqlite3

db = root / "data" / "app" / "greenmeansgo.sqlite"
conn = sqlite3.connect(db)
rows = conn.execute(
    "select id, single_score, created_at, substr(payload_json,1,1) from assessments "
    "order by created_at desc limit 5"
).fetchall()
print("recent_assessments:")
for r in rows:
    print(" ", r[0], "score_col", r[1], "created", r[2])

aid = sys.argv[2] if len(sys.argv) > 2 else rows[0][0]
p = json.loads(
    conn.execute("select payload_json from assessments where id=?", (aid,)).fetchone()[0]
)
ss = p.get("single_score") or {}
print("focus", aid)
print("value", ss.get("value") if isinstance(ss, dict) else ss)
print("band", ss.get("band") if isinstance(ss, dict) else None)
print("n_cats", len(ss.get("contributions") or {}) if isinstance(ss, dict) else None)
print("contrib", ss.get("contributions") if isinstance(ss, dict) else None)
print("midpoint_keys", sorted((p.get("midpoint_impacts") or {}).keys()))
notes = p.get("notes") or (p.get("data_quality") or {}).get("notes") or []
if isinstance(notes, list):
    print("notes_sample", notes[:12])
matches = p.get("input_matches") or []
print("input_matches", len(matches))
for m in matches[:8]:
    print(" ", m.get("name"), "->", (m.get("matched") or {}).get("name") if isinstance(m.get("matched"), dict) else m.get("matched"))
