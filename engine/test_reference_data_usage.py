#!/usr/bin/env python3
"""
Every dataset on disk is either ingested and used by a named code path, or documented as
intentionally unused (engine/lcia_reference/data_usage.json). Also loads the Tier1 price
feed and every case study, so those are exercised by a test, not only by scripts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(REPO))

REG = json.loads((ROOT / "lcia_reference" / "data_usage.json").read_text(encoding="utf-8"))["entries"]
BY_PATH = {e["path"]: e for e in REG}
DATA = REPO / "data"


def _covered(rel: str) -> bool:
    """A path is covered if it, or one of its parent folders, is registered."""
    p = rel
    while p:
        if p in BY_PATH:
            return True
        p = p.rsplit("/", 1)[0] if "/" in p else ""
    return False


def _data_items() -> list[str]:
    """Top-level files/folders of each data/ source plus each Tier1/Tier2 file."""
    if not DATA.exists():
        return []
    out = []
    for src in sorted(DATA.iterdir()):
        if src.name in ("recommendations",):
            for tier in sorted(src.iterdir()):
                out += [f"data/recommendations/{tier.name}/{f.name}" for f in sorted(tier.iterdir())]
        elif src.is_dir():
            out += [f"data/{src.name}/{f.name}" for f in sorted(src.iterdir())]
    return out


def test_every_data_item_is_registered():
    items = _data_items()
    if not items:
        pytest.skip("data/ not present")
    missing = [i for i in items if not _covered(i)]
    assert not missing, f"unregistered datasets (add to data_usage.json): {missing}"


def test_every_reference_json_and_case_study_is_registered():
    refs = [f"engine/recommend/reference/{p.name}" for p in (ROOT / "recommend" / "reference").glob("*.json")]
    cases = [f"engine/case_studies/{p.name}" for p in (ROOT / "case_studies").glob("*.json")]
    missing = [r for r in refs + cases if r not in BY_PATH]
    assert not missing, missing


@pytest.mark.parametrize("entry", [e for e in REG if e["status"] == "ingested_and_used"], ids=lambda e: e["path"])
def test_used_entries_point_at_real_code(entry):
    code = REPO / entry["code_path"]
    assert code.is_file(), entry["code_path"]
    assert entry["evidence"] in code.read_text(encoding="utf-8", errors="ignore"), entry


@pytest.mark.parametrize("entry", [e for e in REG if e["status"] == "documented_unused"], ids=lambda e: e["path"])
def test_unused_entries_have_a_reason(entry):
    assert len(entry.get("reason", "")) > 20


def test_no_em_dash_in_registry():
    assert "—" not in (ROOT / "lcia_reference" / "data_usage.json").read_text(encoding="utf-8")


def test_tier1_price_feed_loads():
    csv = DATA / "recommendations" / "Tier1" / "Commodity prices _04.11.25.csv"
    if not csv.exists():
        pytest.skip("Tier1 price CSV not present")
    from engine.recommend.prices import PriceBook
    book = PriceBook.load()
    assert book.n_rows > 0


@pytest.mark.parametrize("case", sorted((ROOT / "case_studies").glob("*.json")), ids=lambda p: p.stem)
def test_case_study_loads_and_extracts_inputs(case):
    from engine.inputs import extract_purchased_inputs
    from engine.regions import get_region
    a = json.loads(case.read_text(encoding="utf-8"))
    assert a.get("foods"), case.name
    get_region(a.get("region") or a.get("country"))
    inputs, notes = extract_purchased_inputs(a)
    assert isinstance(inputs, list) and isinstance(notes, list)
