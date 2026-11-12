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

try:
    from .canonical_store import DEFAULT_DB
    from .query import CanonicalQuery
except ImportError:
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

# ecoinvent category paths are enormous ("A:Agriculture.../01:Crop.../0111:Growing...").
# The process NAME carries most of the signal, so cap the embedded text: this keeps
# token cost (and cost in $) bounded without hurting match quality.
MAX_EMB_CHARS = 300


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

    # OpenAI caps a single embeddings request at 300k tokens; a full ecoinvent+
    # Agribalyse index is ~46k processes (millions of tokens), so we MUST batch.
    BATCH = 1000

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        texts = [(t or " ")[:MAX_EMB_CHARS] for t in texts]  # never send empty; cap tokens
        out: list[list[float]] = []
        total = len(texts)
        for i in range(0, total, self.BATCH):
            chunk = texts[i:i + self.BATCH]
            resp = self.client.embeddings.create(model=self.model, input=chunk)
            out.extend(d.embedding for d in resp.data)
            if total > self.BATCH:
                print(f"    embedded {min(i + self.BATCH, total)}/{total} ...", flush=True)
        vecs = np.array(out, dtype=np.float32)
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
            try:
                data = np.load(cache, allow_pickle=True)
                matrix = data["matrix"]   # touch the array so a bad CRC surfaces here
                if len(data["uids"]) == len(procs) and len(procs) > 0:
                    self.uids = list(data["uids"])
                    self.meta = list(data["meta"])
                    self.matrix = matrix
                    return len(self.uids)
            except Exception as e:
                # a corrupt/unreadable cache must not crash an assessment: fall through and
                # rebuild it (needs the embedder). Old behaviour raised a cryptic "Bad CRC-32".
                import warnings
                warnings.warn(f"embedding cache at {cache} is unreadable ({e}); rebuilding it.")
        if not procs:
            self.uids, self.meta, self.matrix = [], [], np.zeros((0, 1), np.float32)
            return 0
        self.uids = [p["uid"] for p in procs]
        self.meta = procs
        self.matrix = self.embedder.embed([self._emb_text(p) for p in procs])
        np.savez(cache, uids=np.array(self.uids, dtype=object),
                 meta=np.array(self.meta, dtype=object), matrix=self.matrix)
        return len(self.uids)

    # ---- query embedding cache -------------------------------------------------------
    # Dense embedding APIs jitter in the 4th decimal between calls, which can flip a
    # near-tie between two candidates. Caching each query vector makes repeated matches of
    # the same text inside one process identical (and cheaper). load/save_query_cache let a
    # test pin the vectors on disk so a golden comparison is reproducible without the API.
    def _query_vec(self, text: str) -> np.ndarray:
        cache = self.__dict__.setdefault("_qcache", {})
        key = (self.embedder.name, text)
        v = cache.get(key)
        if v is None:
            v = self.embedder.embed([text])[0]
            cache[key] = v
            self.__dict__.setdefault("_qcache_new", set()).add(key)
        return v

    def load_query_cache(self, path) -> int:
        """Load pinned query vectors for this embedder. Returns how many were loaded."""
        p = Path(path)
        if not p.exists():
            return 0
        data = np.load(p, allow_pickle=False)
        if str(data["embedder"]) != self.embedder.name:
            return 0
        cache = self.__dict__.setdefault("_qcache", {})
        vecs = data["vectors"].astype(np.float32)
        for t, v in zip(data["texts"], vecs):
            cache[(self.embedder.name, str(t))] = v
        return len(vecs)

    def save_query_cache(self, path) -> int:
        """Persist every cached query vector for this embedder (float16, compressed)."""
        cache = self.__dict__.get("_qcache", {})
        items = sorted((t, v) for (e, t), v in cache.items() if e == self.embedder.name)
        if not items:
            return 0
        np.savez_compressed(Path(path), embedder=np.array(self.embedder.name),
                            texts=np.array([t for t, _ in items]),
                            vectors=np.stack([v for _, v in items]).astype(np.float16))
        return len(items)

    def new_query_count(self) -> int:
        """How many query vectors were embedded live (not served from the cache)."""
        return len(self.__dict__.get("_qcache_new", ()))

    # ---- reference products -----------------------------------------------------------
    def reference_product(self, uid: str) -> Optional[str]:
        """Name of the process's reference product flow (ecoinvent: the product after the
        '|' in the activity name; Agribalyse: usually the process name itself)."""
        refs = self.__dict__.get("_refprod")
        if refs is None:
            refs = {}
            try:
                for r in self.q.conn.execute(
                        "SELECT p.uid, f.name FROM processes p "
                        "LEFT JOIN flows f ON f.uid = p.ref_flow"):
                    refs[r[0]] = r[1]
            except Exception:
                refs = {}
            self._refprod = refs
        return refs.get(uid)

    def _row_of(self, uid: str) -> Optional[int]:
        rows = self.__dict__.get("_rows")
        if rows is None or len(rows) != len(self.uids):
            rows = {u: i for i, u in enumerate(self.uids)}
            self._rows = rows
        return rows.get(uid)

    def _cand(self, i: int, score: float) -> dict:
        return {
            "uid": self.uids[i],
            "name": self.meta[i].get("name"),
            "location": self.meta[i].get("location"),
            "category": self.meta[i].get("category"),
            "reference_product": self.reference_product(self.uids[i]),
            "score": round(float(score), 4),
        }

    def match(self, text: str, top_k: int = 5, expand: bool = False) -> list[dict]:
        if self.matrix is None:
            self.build_index()
        if self.matrix is None or self.matrix.shape[0] == 0:
            return []
        query_text = llm_expand(text) if expand else text
        qv = self._query_vec(query_text)
        sims = self.matrix @ qv
        k = min(top_k, len(self.uids))
        top = np.argpartition(-sims, k - 1)[:k]
        # stable order: score desc, then uid, so equal scores never reorder between runs
        top = sorted(top, key=lambda i: (-float(sims[i]), self.uids[i]))
        return [self._cand(i, sims[i]) for i in top]

    def score_uids(self, text: str, uids, top_k: int = 25) -> list[dict]:
        """Score an explicit subset of processes against `text`. Recall path for the
        product-identity gate: datasets of the right product whose embedding fell outside
        the global top-k."""
        if self.matrix is None:
            self.build_index()
        rows = [r for r in (self._row_of(u) for u in uids) if r is not None]
        if not rows:
            return []
        qv = self._query_vec(text)
        sims = self.matrix[rows] @ qv
        order = sorted(range(len(rows)), key=lambda j: (-float(sims[j]), self.uids[rows[j]]))
        return [self._cand(rows[j], sims[j]) for j in order[:top_k]]


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
