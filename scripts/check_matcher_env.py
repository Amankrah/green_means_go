#!/usr/bin/env python3
"""Print which embedder the production API process would use."""
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1] if Path(__file__).name == "check_matcher_env.py" else Path.cwd()
# when copied to /tmp, allow explicit root
if len(sys.argv) > 1:
    root = Path(sys.argv[1])
sys.path.insert(0, str(root))
os.chdir(root)

# Load app/.env the same way uvicorn --env-file does not; mimic supervisor cwd=app
env_file = root / "app" / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

print("cwd", os.getcwd())
print("OPENAI_API_KEY set", bool(os.getenv("OPENAI_API_KEY")))
print("ANTHROPIC_API_KEY set", bool(os.getenv("ANTHROPIC_API_KEY")))

try:
    import openai
    print("openai package", openai.__version__)
except Exception as e:
    print("openai package FAIL", e)

from ingestion.matching import default_embedder, ProcessMatcher
from ingestion.canonical_store import DEFAULT_DB
from ingestion.query import CanonicalQuery

emb = default_embedder()
print("embedder", emb.name)
print("DEFAULT_DB", DEFAULT_DB, "exists", Path(DEFAULT_DB).exists())
q = CanonicalQuery(DEFAULT_DB)
m = ProcessMatcher(q, embedder=emb)
path = m._cache_path()
print("emb_cache", path, "exists", path.exists(), "size", path.stat().st_size if path.exists() else None)
m.build_index()
print("index_built", getattr(m, "name", None), "n_procs", len(getattr(m, "_uids", []) or getattr(m, "uids", []) or []))
# probe a fertiliser match
hits = m.match("urea fertiliser", top_k=3, expand=False)
print("urea_hits", [(h.get("name"), round(h.get("score", 0), 3), h.get("location")) for h in hits[:3]])
