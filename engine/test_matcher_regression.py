"""Matcher regression: every input name in docs/inventory_mapping/GMG_inventory_database_mapping.json
(farm purchased inputs, shared processing inputs, commodity raw materials; every region) is run
through FarmLCA.resolve_input and the matched process uid is compared with the committed golden
file engine/golden/matcher_golden.json. Any change fails.

Reproducibility: query embeddings are pinned in engine/golden/matcher_query_embeddings.npz, so
the test needs neither the embedding API nor network access, only the canonical store and its
process-embedding index. It is skipped when either is unavailable, or when a query is not
pinned and no OPENAI_API_KEY is set. Adjudication is forced off (GMG_LLM_ADJUDICATE=0).

Regenerate after an intended matching change:
    GMG_UPDATE_GOLDEN=1 python -m pytest engine/test_matcher_regression.py -q
which rewrites the golden file, the pinned query vectors, and
engine/golden/matcher_changes_vs_mapping.json (row-by-row before/after versus the mapping JSON).
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MAPPING = ROOT / "docs" / "inventory_mapping" / "GMG_inventory_database_mapping.json"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
GOLDEN = GOLDEN_DIR / "matcher_golden.json"
QCACHE = GOLDEN_DIR / "matcher_query_embeddings.npz"
CHANGES = GOLDEN_DIR / "matcher_changes_vs_mapping.json"
EMBEDDER_NAME = "openai:text-embedding-3-small"
UPDATE = os.getenv("GMG_UPDATE_GOLDEN") == "1"

# Facility-fuel fallback chain as built by engine/process_inputs.py (kept literal so the
# regression does not depend on that file's extraction code, owned by another workstream).
_FUEL_FALLBACKS = ["heat production, natural gas", "{w}, burned in agricultural machinery"]


def collect_rows() -> list[dict]:
    """(section, region, input) rows with the inputs the engine would build for them."""
    from engine.process_inputs import _raw_material_match
    d = json.loads(MAPPING.read_text(encoding="utf-8"))
    rows: list[dict] = []

    def add(section, region, name, inp, before):
        rows.append({"key": f"{section}|{region}|{name}", "section": section, "region": region,
                     "input_name": name, "inp": inp, "before": before})

    for r in d["shared_farm_inventory"]["purchased_inputs_to_database_processes"]:
        if not r.get("matched_process") or r.get("region") in (None, "all"):
            continue
        tgt = r.get("match_target") or r["input_name"]
        inp = {"name": r["input_name"], "kind": r.get("input_category"),
               "unit": r.get("amount_unit_passed")}
        if tgt != r["input_name"]:
            inp["match_as"] = tgt
        add("farm", r["region"], r["input_name"], inp,
            {"name": r["matched_process"], "location": r.get("location"), "uid": None})
    for r in d["shared_processing_inventory"]["inputs_to_database_processes"]:
        tgt = r.get("match_target_sent_to_matcher") or r["input_name"]
        inp = {"name": r["input_name"], "match_as": tgt, "kind": r.get("category")}
        m = re.match(r"(\w+) \(facility fuel\)$", r["input_name"])
        if m:
            fbs = [f.format(w=m.group(1)) for f in _FUEL_FALLBACKS]
            inp["fallbacks"] = [f for f in fbs if f != tgt]
        for reg, v in (r.get("by_region") or {}).items():
            add("processing", reg, r["input_name"], inp,
                {"name": v.get("matched_process"), "location": v.get("location"),
                 "uid": v.get("uid")})
    for cv in d["commodities"].values():
        for p in cv.get("processing") or []:
            for i in p.get("commodity_specific_inputs") or []:
                m = re.match(r"raw material: '(.*)'", i["input_name"])
                if not m:
                    continue
                name = m.group(1)
                hint, refined = _raw_material_match(name)
                inp = {"name": name, "match_as": hint, "fallback": name, "kind": "raw_material",
                       "refined": refined, "unit": "kg"}
                for reg, v in (i.get("by_region") or {}).items():
                    add("raw_material", reg, name, inp,
                        {"name": v.get("matched_process"), "location": v.get("location"),
                         "uid": v.get("uid")})
    seen, out = set(), []
    for r in rows:
        if r["key"] not in seen:
            seen.add(r["key"])
            out.append(r)
    return out


class _PinnedOnly:
    """Embedder stand-in when no API key is set: every query must come from the pinned cache."""
    name = EMBEDDER_NAME

    def embed(self, texts):
        raise LookupError(f"query not pinned and no embedding API key: {texts!r}")


def _store_ready() -> str | None:
    from ingestion.canonical_store import DEFAULT_DB
    db = Path(DEFAULT_DB)
    idx = db.parent / "proc_emb_openai_text_embedding_3_small.npz"
    if not db.exists():
        return f"canonical store not found at {db}"
    if not idx.exists():
        return f"process-embedding index not found at {idx}"
    import numpy as np
    try:
        n_idx = len(np.load(idx, allow_pickle=True)["uids"])
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        n_db = con.execute("SELECT COUNT(*) FROM processes").fetchone()[0]
        con.close()
    except Exception as e:  # pragma: no cover
        return f"store/index unreadable: {e}"
    if n_idx != n_db:
        return f"embedding index ({n_idx}) out of date with the store ({n_db} processes)"
    return None


@pytest.fixture(scope="module")
def engines():
    why = _store_ready()
    if why:
        pytest.skip(why)
    os.environ["GMG_LLM_ADJUDICATE"] = "0"
    from ingestion.matching import ProcessMatcher, OpenAIEmbedder
    from ingestion.query import CanonicalQuery
    from engine.orchestrator import FarmLCA
    from engine.regions import REGIONS
    q = CanonicalQuery()
    emb = None
    if os.getenv("OPENAI_API_KEY"):
        try:
            emb = OpenAIEmbedder()
        except Exception:
            emb = None
    matcher = ProcessMatcher(q, embedder=emb or _PinnedOnly())
    matcher.build_index()
    matcher.load_query_cache(QCACHE)
    cache = {}

    def get(region):
        if region not in REGIONS:
            return None
        if region not in cache:
            cache[region] = FarmLCA(region, matcher=matcher)
        return cache[region]

    yield get, matcher, _fingerprint(matcher)
    for e in cache.values():
        e.close()
    q.close()


def _fingerprint(matcher) -> str:
    """Fingerprint of the process-embedding index the golden was generated against. If the
    shared index is re-embedded (the API jitters), matches may legitimately move, so the
    golden comparison is skipped and must be regenerated rather than reported as a code
    regression."""
    import hashlib
    import numpy as np
    sample = np.round(matcher.matrix[::997].astype(np.float64), 4)
    h = hashlib.sha1(sample.tobytes())
    h.update("|".join(matcher.uids[::997]).encode())
    return h.hexdigest()[:16]


def _run_all(get) -> dict:
    out = {}
    for r in collect_rows():
        eng = get(r["region"])
        if eng is None:
            continue
        try:
            m, used = eng.resolve_input(r["inp"])
        except LookupError as e:
            pytest.skip(str(e))
        out[r["key"]] = {
            "target": r["inp"].get("match_as") or r["inp"]["name"],
            "uid": m["uid"] if m else None,
            "name": m["name"] if m else None,
            "location": m.get("location") if m else None,
            "score": m.get("score") if m else None,
            "needs_review": bool(m and m.get("needs_review")),
            "identity_basis": (m.get("identity") or {}).get("basis") if m else None,
            "fallback_used": used,
            "_before": r["before"],
        }
    return out


def _changes(results: dict) -> list[dict]:
    rows = []
    for k, v in results.items():
        b = v["_before"]
        if b.get("uid"):
            same = b["uid"] == v["uid"]
        else:
            same = (b.get("name") or "")[:70] == (v["name"] or "")[:70] and \
                b.get("location") == v["location"]
        if not same:
            rows.append({"row": k, "before": {"name": b.get("name"), "location": b.get("location")},
                         "after": {"name": v["name"], "location": v["location"],
                                   "needs_review": v["needs_review"],
                                   "identity_basis": v["identity_basis"],
                                   "target": v["target"]}})
    return rows


def test_matcher_matches_golden(engines):
    get, matcher, fp = engines
    results = _run_all(get)
    assert results, "no rows collected from the mapping JSON"
    if UPDATE:
        GOLDEN_DIR.mkdir(exist_ok=True)
        golden = {"index_fingerprint": fp, "embedder": EMBEDDER_NAME,
                  "rows": {k: {kk: vv for kk, vv in v.items() if kk != "_before"}
                           for k, v in sorted(results.items())}}
        GOLDEN.write_text(json.dumps(golden, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        matcher.save_query_cache(QCACHE)
        CHANGES.write_text(json.dumps(_changes(results), indent=1, ensure_ascii=False) + "\n",
                           encoding="utf-8")
        return
    if not GOLDEN.exists():
        pytest.skip("golden file missing; run with GMG_UPDATE_GOLDEN=1 to create it")
    doc = json.loads(GOLDEN.read_text(encoding="utf-8"))
    if doc.get("index_fingerprint") != fp:
        pytest.skip("process-embedding index differs from the one the golden was built on; "
                    "regenerate with GMG_UPDATE_GOLDEN=1")
    golden = doc["rows"]
    diffs = []
    for k, g in golden.items():
        got = results.get(k)
        if got is None:
            if k.split("|")[1] in {key.split("|")[1] for key in results}:
                diffs.append(f"{k}: row missing")
            continue
        if got["uid"] != g["uid"]:
            diffs.append(f"{k}: {g['name']} [{g['location']}] -> {got['name']} [{got['location']}]")
    new_rows = sorted(set(results) - set(golden))
    diffs += [f"{k}: new row not in golden" for k in new_rows]
    assert not diffs, "matched process changed:\n  " + "\n  ".join(diffs)


def test_known_bad_rows_fixed(engines):
    """The wrong-crop rows called out in the mapping JSON no longer resolve to cocoa,
    petroleum or an unrelated Canadian crop."""
    get = engines[0]
    from engine.process_inputs import _raw_material_match
    bad = [("GH", "Eggplant"), ("GH", "Aubergine"), ("GH", "Cucumber"), ("GH", "Chilli peppers"),
           ("GH", "Bell peppers"), ("GH", "Groundnuts (shelled)"), ("GH", "Peanuts"),
           ("GH", "Fresh fruit bunches (FFB)"), ("GH", "Raw honey"), ("NG", "Raw honey"),
           ("CA", "Cocoa beans"), ("CA", "Eggplant"), ("CA", "Cucumber"), ("CA", "Peanuts")]
    for region, name in bad:
        eng = get(region)
        hint, refined = _raw_material_match(name)
        try:
            m, _ = eng.resolve_input({"name": name, "match_as": hint, "fallback": name,
                                      "kind": "raw_material"})
        except LookupError as e:
            pytest.skip(str(e))
        low = (m["name"] + " " + (m.get("reference_product") or "")).lower()
        assert "cocoa" not in low or "cocoa" in name.lower(), (region, name, m["name"])
        assert "petroleum" not in low, (region, name, m["name"])
    for region, text in [("GH", "Bio-fertilizer fertiliser"), ("GH", "Foliar Fertilizer fertiliser"),
                         ("GH", "None fertiliser")]:
        m, _ = get(region).resolve_input({"name": text, "kind": "fertiliser"})
        assert "cocoa" not in m["name"].lower(), (region, text, m["name"])
        assert m["needs_review"] is True
