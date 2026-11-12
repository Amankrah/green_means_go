"""
cache.py: committed, human-readable JSON caches for model answers.

Each cache is one JSON object file under engine/llm/cache/ (override the directory with
GMG_LLM_CACHE_DIR, which tests do so they never touch the committed files). Entries hold
only the normalised query, the validated label/uid, a rationale, the model id and a
timestamp: never credentials, never raw API responses.
"""
from __future__ import annotations

import json
import os
import re
import threading
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_DIR = Path(__file__).resolve().parent / "cache"
_lock = threading.Lock()


def cache_dir() -> Path:
    d = os.getenv("GMG_LLM_CACHE_DIR")
    return Path(d) if d else _DEFAULT_DIR


def normalise(text: str) -> str:
    """Lowercase, strip accents and punctuation, collapse whitespace."""
    t = unicodedata.normalize("NFKD", str(text or ""))
    t = "".join(ch for ch in t if not unicodedata.combining(ch)).lower()
    t = re.sub(r"[^a-z0-9%+\-./ ]+", " ", t)
    t = re.sub(r"[\s/]+", " ", t)
    return t.strip(" .-")


def _path(name: str) -> Path:
    return cache_dir() / f"{name}.json"


def load(name: str) -> dict:
    p = _path(name)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def get(name: str, key: str) -> dict | None:
    return load(name).get(key)


def put(name: str, key: str, entry: dict) -> None:
    """Insert one entry and rewrite the file sorted, so diffs stay reviewable."""
    entry = {**entry, "cached_at": datetime.now(timezone.utc).strftime("%Y-%m-%d")}
    with _lock:
        data = load(name)
        data[key] = entry
        p = _path(name)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(dict(sorted(data.items())), indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
        os.replace(tmp, p)
