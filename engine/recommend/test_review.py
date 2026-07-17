#!/usr/bin/env python3
"""
test_review.py - proves the review overlay flips the reviewed gate and the licence gate
drops blocked-licence measures.

Run:  python3 test_review.py   (from engine/recommend/)
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

try:
    from .schema import load_measures, load_reviews
    from .matcher import match_measures
    from .licences import licence_status, is_commercial_ok
    from .review import record_review
except ImportError:
    from schema import load_measures, load_reviews
    from matcher import match_measures
    from licences import licence_status, is_commercial_ok
    from review import record_review

_AS_OF = date(2026, 7, 15)


def _ghana_maize_payload() -> dict:
    return {
        "country": "Ghana",
        "breakdown_by_food": {"maize (1000kg)": {}},
        "input_matches": [
            {"input": "Urea 46-0-0 fertiliser", "kind": "fertiliser", "matched": "urea"},
            {"input": "diesel, burned in agricultural machinery", "kind": "fuel", "matched": "d"},
        ],
        "contribution_by_source": {
            "Urea 46-0-0 fertiliser": {"Climate change": {"value": 0.6, "unit": "kg CO2-eq"}},
            "diesel, burned in agricultural machinery": {"Climate change": {"value": 0.4, "unit": "kg CO2-eq"}},
        },
        "iso_report": {"interpretation": {"contribution_analysis": {"by_source": [
            {"source": "Urea 46-0-0 fertiliser", "per_kg": 0.6, "share": 0.6},
            {"source": "diesel, burned in agricultural machinery", "per_kg": 0.4, "share": 0.4},
        ]}}},
    }


def _temp_reviews(records: list[dict]) -> Path:
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    return Path(path)


# --- review overlay ---------------------------------------------------------------

def test_default_library_all_draft() -> None:
    measures = load_measures()
    assert all(not m.is_reviewed for m in measures), "some measure is reviewed with an empty ledger"
    print("[ok] empty ledger -> every measure is draft")


def test_approved_review_flips_gate() -> None:
    rp = _temp_reviews([
        {"measure_id": "meas.n.nitrification_inhibitor.gh", "reviewer": "Dr Ama Owusu",
         "reviewed_at": "2026-07-20", "decision": "approved", "notes": "sound for GH"},
    ])
    try:
        measures = load_measures(reviews_path=rp)
        by_id = {m.id: m for m in measures}
        approved = by_id["meas.n.nitrification_inhibitor.gh"]
        assert approved.is_reviewed, "approved measure did not flip to reviewed"
        assert "Ama Owusu" in approved.provenance.reviewed_by
        # everything else stays draft
        others = [m for m in measures if m.id != "meas.n.nitrification_inhibitor.gh"]
        assert all(not m.is_reviewed for m in others), "an un-reviewed measure was flipped"
    finally:
        os.remove(rp)
    print("[ok] approved review stamps reviewed_by and flips only that measure")


def test_rejected_and_needs_changes_stay_draft() -> None:
    rp = _temp_reviews([
        {"measure_id": "meas.n.split_application.gh", "reviewer": "R", "decision": "rejected"},
        {"measure_id": "meas.n.compost_substitution.gh", "reviewer": "R", "decision": "needs_changes"},
    ])
    try:
        by_id = {m.id: m for m in load_measures(reviews_path=rp)}
        assert not by_id["meas.n.split_application.gh"].is_reviewed
        assert not by_id["meas.n.compost_substitution.gh"].is_reviewed
    finally:
        os.remove(rp)
    print("[ok] rejected / needs_changes leave a measure draft")


def test_re_review_supersedes() -> None:
    """Append-only: a later approval overrides an earlier rejection (last line wins)."""
    rp = _temp_reviews([
        {"measure_id": "meas.pest.ipm.gh", "reviewer": "R", "decision": "rejected"},
        {"measure_id": "meas.pest.ipm.gh", "reviewer": "R2", "reviewed_at": "2026-08-01",
         "decision": "approved"},
    ])
    try:
        by_id = {m.id: m for m in load_measures(reviews_path=rp)}
        assert by_id["meas.pest.ipm.gh"].is_reviewed, "re-review did not supersede"
        assert "R2" in by_id["meas.pest.ipm.gh"].provenance.reviewed_by
    finally:
        os.remove(rp)
    print("[ok] last decision per measure wins (re-review supersedes)")


def test_reviewed_only_surfaces_approved() -> None:
    rp = _temp_reviews([
        {"measure_id": "meas.n.nitrification_inhibitor.gh", "reviewer": "Dr X",
         "decision": "approved"},
    ])
    try:
        lib = load_measures(reviews_path=rp)
        res = match_measures(_ghana_maize_payload(), measures=lib, reviewed_only=True, as_of=_AS_OF)
        ids = [r.id for r in res]
        assert ids == ["meas.n.nitrification_inhibitor.gh"], f"reviewed_only surfaced {ids}"
    finally:
        os.remove(rp)
    print("[ok] reviewed_only surfaces exactly the approved measure")


def test_record_review_roundtrip() -> None:
    rp = _temp_reviews([])  # empty
    try:
        record_review("meas.rice.awd.gh", "Dr Y", decision="approved",
                      notes="AWD ok where water control reliable", reviewed_at="2026-07-21",
                      reviews_path=rp)
        loaded = load_reviews(rp)
        assert loaded["meas.rice.awd.gh"]["decision"] == "approved"
        assert loaded["meas.rice.awd.gh"]["reviewer"] == "Dr Y"
        # unknown measure id is rejected before writing
        bad = False
        try:
            record_review("meas.does.not.exist", "Z", reviews_path=rp)
        except ValueError:
            bad = True
        assert bad, "record_review accepted an unknown measure_id"
    finally:
        os.remove(rp)
    print("[ok] record_review appends a valid decision and rejects unknown ids")


# --- licence gate -----------------------------------------------------------------

def test_licence_status_map() -> None:
    assert licence_status("CCAFS-CSA-Ghana") == "nc"
    assert licence_status("IPCC-2019") == "permission"
    assert licence_status("Ecological-Processes-EastGonja") == "cite"
    assert licence_status("internal-data-quality") == "clean"
    # unknown source is unconfirmed (safe default), so blocked for commercial
    assert licence_status("some-new-source") == "unconfirmed"
    assert not is_commercial_ok("some-new-source")
    assert is_commercial_ok("Ecological-Processes-EastGonja")
    print("[ok] licence status map + unknown-source defaults to blocked")


def test_commercial_gate_drops_blocked_licences() -> None:
    payload = _ghana_maize_payload()
    both = match_measures(payload, reviewed_only=False, as_of=_AS_OF)
    comm = match_measures(payload, reviewed_only=False, commercial=True, as_of=_AS_OF)
    comm_ids = [r.id for r in comm]

    # a cite-licensed measure survives; a permission-blocked one is dropped
    assert "meas.n.nitrification_inhibitor.gh" in comm_ids, "cite-licensed measure dropped"
    assert "meas.n.split_application.gh" not in comm_ids, "IPCC-permission measure leaked commercially"
    assert "meas.pest.ipm.gh" not in comm_ids, "CC BY-NC measure leaked commercially"
    # commercial mode is a strict subset of the full set
    assert set(comm_ids).issubset({r.id for r in both})
    assert len(comm) < len(both), "commercial gate dropped nothing"
    # every surviving measure is genuinely commercial-ok
    assert all(is_commercial_ok(r.measure.provenance.source) for r in comm)
    print(f"[ok] commercial gate: {len(both)} -> {len(comm)} measures, only clean/cite survive")


def _run_all() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failed += 1
            print(f"[FAIL] {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            import traceback
            print(f"[ERROR] {t.__name__}: {type(e).__name__}: {e}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_all())
