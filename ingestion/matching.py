#!/usr/bin/env python3
"""
matching.py — AI matching subsystem (DEVELOPER_GUIDE.md §5.1).

Maps free-text farm/processing inputs ("NPK 15-15-15, 50 kg", "diesel for
ploughing", "local maize") to candidate processes in the canonical store, ranked
by similarity, so a human/expert confirms the final pick.

Hybrid design, grounded in the entity-linking research (semantic-only ≈5% top-5;
LLM+context ≈48%):
  user text ──[optional LLM expansion]──▶ normalised description ──embed──▶ cosine
            ──▶ over pre-embedded process index ──▶ top-k candidates + scores

Pluggable embedding backends:
  - LexicalEmbedder  (default; pure numpy, deterministic, NO api key) — char-trigram
    + word hashing. Good enough to bootstrap + to run offline/in CI.
  - OpenAIEmbedder   (optional; text-embedding-3-small) — set OPENAI_API_KEY.
Optional LLM query expansion uses anthropic or openai if a key is present; else
it is skipped (non-fatal). The pipeline ALWAYS returns ranked candidates for
human confirmation — it never auto-commits a match.

CLI:
    python3 matching.py "NPK fertilizer 15-15-15" --top 5
    python3 matching.py "maize grain" --expand        # use LLM expansion if key set
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Optional, Sequence

import numpy as np

from canonical_store import DEFAULT_DB
from query import CanonicalQuery

# Load API keys from a .env so the standalone CLI behaves like the FastAPI app
# (which calls load_dotenv()). Searches app/.env then repo-root .env. Non-fatal.
try:
    from dotenv import load_dotenv
    _repo = Path(__file__).resolve().parents[1]
    for _envp in (_repo / "app" / ".env", _repo / ".env"):
        if _envp.exists():
            load_dotenv(_envp)
except Exception:
    pass

EMB_CACHE = Path(DEFAULT_DB).parent


# --------------------------- embedding backends ----------------------------
class LexicalEmbedder:
    """Deterministic hashing embedder: words + char-trigrams -> fixed dim, L2-normed."""

    name = "lexical-2048"

    def __init__(self, dim: int = 2048):
        self.dim = dim

    @staticmethod
    def _tokens(text: str) -> list[str]:
        text = (text or "").lower()
        words = re.findall(r"[a-z0-9]+", text)
        toks: list[str] = []
        for w in words:
            toks.append(w)
            s = f"#{w}#"
            for i in range(len(s) - 2):
                toks.append(s[i:i + 3])
        return toks

    def _hash(self, tok: str) -> int:
        return int(hashlib.md5(tok.encode()).hexdigest(), 16) % self.dim

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            for tok in self._tokens(t):
                out[i, self._hash(tok)] += 1.0
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return out / norms


class OpenAIEmbedder:
    """Optional dense embedder via OpenAI. Requires OPENAI_API_KEY + `pip install openai`."""

    def __init__(self, model: str = "text-embedding-3-small"):
        from openai import OpenAI  # raises if not installed
        self.client = OpenAI()
        self.model = model
        self.name = f"openai:{model}"

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        resp = self.client.embeddings.create(model=self.model, input=list(texts))
        vecs = np.array([d.embedding for d in resp.data], dtype=np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vecs / norms


def default_embedder():
    """OpenAI if a key + package are available, else the lexical fallback."""
    if os.getenv("OPENAI_API_KEY"):
        try:
            return OpenAIEmbedder()
        except Exception:
            pass
    return LexicalEmbedder()


# --------------------------- optional LLM expansion -------------------------
def llm_expand(text: str) -> str:
    """Turn terse user input into a normalised process description. Non-fatal: returns
    the input unchanged if no LLM is configured."""
    prompt = (
        "Rewrite this agricultural/industrial input as a concise LCA process "
        "description (material, form, production route) in one line, no preamble:\n"
        f"INPUT: {text}\nPROCESS DESCRIPTION:"
    )
    # Try Anthropic, then OpenAI; silently fall back.
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            import anthropic
            c = anthropic.Anthropic()
            m = c.messages.create(
                model="claude-haiku-4-5-20251001", max_tokens=80,
                messages=[{"role": "user", "content": prompt}],
            )
            return f"{text}. {m.content[0].text.strip()}"
        except Exception:
            pass
    if os.getenv("OPENAI_API_KEY"):
        try:
            from openai import OpenAI
            r = OpenAI().chat.completions.create(
                model="gpt-4o-mini", max_tokens=80,
                messages=[{"role": "user", "content": prompt}],
            )
            return f"{text}. {r.choices[0].message.content.strip()}"
        except Exception:
            pass
    return text


# ------------------------------- matcher -----------------------------------
class ProcessMatcher:
    def __init__(self, query: CanonicalQuery, embedder=None):
        self.q = query
        self.embedder = embedder or default_embedder()
        self.uids: list[str] = []
        self.meta: list[dict] = []
        self.matrix: Optional[np.ndarray] = None

    @staticmethod
    def _emb_text(p: dict) -> str:
        return " | ".join(str(x) for x in (p.get("name"), p.get("category"), p.get("location")) if x)

    def _cache_path(self) -> Path:
        safe = re.sub(r"[^a-z0-9]+", "_", self.embedder.name.lower())
        return EMB_CACHE / f"proc_emb_{safe}.npz"

    def build_index(self, force: bool = False) -> int:
        procs = [dict(r) for r in self.q.conn.execute(
            "SELECT uid, name, category, location FROM processes ORDER BY uid").fetchall()]
        cache = self._cache_path()
        if not force and cache.exists():
            data = np.load(cache, allow_pickle=True)
            if len(data["uids"]) == len(procs) and len(procs) > 0:
                self.uids = list(data["uids"])
                self.meta = list(data["meta"])
                self.matrix = data["matrix"]
                return len(self.uids)
        if not procs:
            self.uids, self.meta, self.matrix = [], [], np.zeros((0, 1), np.float32)
            return 0
        self.uids = [p["uid"] for p in procs]
        self.meta = procs
        self.matrix = self.embedder.embed([self._emb_text(p) for p in procs])
        np.savez(cache, uids=np.array(self.uids, dtype=object),
                 meta=np.array(self.meta, dtype=object), matrix=self.matrix)
        return len(self.uids)

    def match(self, text: str, top_k: int = 5, expand: bool = False) -> list[dict]:
        if self.matrix is None:
            self.build_index()
        if self.matrix is None or self.matrix.shape[0] == 0:
            return []
        query_text = llm_expand(text) if expand else text
        qv = self.embedder.embed([query_text])[0]
        sims = self.matrix @ qv
        k = min(top_k, len(self.uids))
        top = np.argpartition(-sims, k - 1)[:k]
        top = top[np.argsort(-sims[top])]
        return [
            {
                "uid": self.uids[i],
                "name": self.meta[i].get("name"),
                "location": self.meta[i].get("location"),
                "category": self.meta[i].get("category"),
                "score": round(float(sims[i]), 4),
            }
            for i in top
        ]


# ------------------------------- CLI ---------------------------------------
def _main(argv=None) -> int:
    import argparse, json
    ap = argparse.ArgumentParser(description="Match free-text input to canonical processes.")
    ap.add_argument("text")
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--expand", action="store_true", help="LLM-expand the query first (if a key is set)")
    ap.add_argument("--reindex", action="store_true")
    args = ap.parse_args(argv)
    with CanonicalQuery(args.db) as q:
        m = ProcessMatcher(q)
        n = m.build_index(force=args.reindex)
        print(f"# index: {n} processes, embedder={m.embedder.name}")
        print(json.dumps(m.match(args.text, args.top, args.expand), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
