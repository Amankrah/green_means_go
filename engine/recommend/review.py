#!/usr/bin/env python3
"""
review.py — the agronomist review worksheet and sign-off helper.

The measure library is draft until a human signs each measure off. This tool surfaces
every claim a reviewer must check (the effect size and its basis, the economics, and the
exact source span it came from) alongside the current review status, and gives one helper
to record a decision into the append-only ledger (reviews.jsonl).

Usage:
  python review.py                 # print the worksheet for every measure
  python review.py --pending       # only measures not yet approved
  python review.py --summary       # one-line status counts

Recording a decision (from a Python shell or a small script):
  from review import record_review
  record_review("meas.n.split_application.gh", "Dr Ama Owusu",
                decision="approved", notes="Effect conservative; timing sound for GH.")
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

try:
    from .schema import load_measures, load_reviews, AbatementMeasure, _DEFAULT_REVIEWS
    from .licences import licence_status
except ImportError:
    from schema import load_measures, load_reviews, AbatementMeasure, _DEFAULT_REVIEWS
    from licences import licence_status


def _fmt_measure(m: AbatementMeasure) -> str:
    e = m.effect
    ap = m.applicability
    econ = m.economics
    unc = (f"  range {e.uncertainty_low} to {e.uncertainty_high}"
           if e.uncertainty_low is not None else "")
    yield_note = (f"  yield effect {e.yield_effect:+.2f}" if e.yield_effect is not None else "")
    status = "APPROVED by " + m.provenance.reviewed_by if m.is_reviewed else "DRAFT (not reviewed)"
    lic = licence_status(m.provenance.source)
    lines = [
        f"{'='*84}",
        f"{m.id}    [{status}]    licence: {lic}",
        f"  TITLE     {m.title}",
        f"  ACTION    {m.action_detail}",
        f"  TARGETS   {m.driver_kind} sources matching {list(m.driver_match) or '(any)'}"
        f"  ->  {m.impact_category}",
        f"  EFFECT    {e.value:+.2f} ({e.unit.value}), basis={e.basis.value}{unc}{yield_note}",
        f"            note: {e.note}" if e.note else "",
        f"  ECONOMICS capex={econ.capex} opex_delta={econ.opex_delta} {econ.opex_per} "
        f"({econ.currency}, as of {econ.as_of}); horizon={m.horizon.value}",
        f"  APPLIES   regions={list(ap.regions)} crops={list(ap.crops) or '(any)'} "
        f"systems={list(ap.systems) or '(any)'} scale={ap.scale_ha_min}-{ap.scale_ha_max}ha",
        f"            prerequisites={list(ap.prerequisites) or '(none)'}",
        f"  SOURCE    {m.provenance.citation or m.provenance.source}"
        f"  (confidence {m.provenance.extraction_confidence})",
        f"  QUOTE     \"{m.provenance.span}\"",
        f"  LICENCE   {m.provenance.licence}",
        f"  REVIEW?   effect size plausible for Ghana? economics realistic? source supports"
        f" the claim? applicability correct?",
    ]
    return "\n".join(l for l in lines if l != "")


def worksheet(*, pending_only: bool = False) -> str:
    measures = load_measures()
    if pending_only:
        measures = [m for m in measures if not m.is_reviewed]
    if not measures:
        return "No measures to review."
    return "\n".join(_fmt_measure(m) for m in measures)


def summary() -> str:
    measures = load_measures()
    approved = [m for m in measures if m.is_reviewed]
    return (f"{len(measures)} measures: {len(approved)} approved, "
            f"{len(measures) - len(approved)} draft.\n"
            f"Production (reviewed_only) would surface: {len(approved)}.")


def record_review(measure_id: str, reviewer: str, *, decision: str = "approved",
                  notes: str = "", reviewed_at: Optional[str] = None,
                  reviews_path: Optional[Path] = None) -> None:
    """Append one review decision to the ledger. reviewed_at defaults to today (resolved
    at call time; pass it explicitly for reproducible scripts). Validates the measure_id
    exists and the decision is legal before writing, so the ledger stays clean."""
    valid = {"approved", "rejected", "needs_changes"}
    if decision not in valid:
        raise ValueError(f"decision must be one of {sorted(valid)}")
    known = {m.id for m in load_measures()}
    if measure_id not in known:
        raise ValueError(f"unknown measure_id '{measure_id}'")
    if reviewed_at is None:
        from datetime import datetime, timezone
        reviewed_at = datetime.now(timezone.utc).date().isoformat()
    rec = {"measure_id": measure_id, "reviewer": reviewer, "reviewed_at": reviewed_at,
           "decision": decision, "notes": notes}
    p = reviews_path or _DEFAULT_REVIEWS
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    args = set(sys.argv[1:])
    if "--summary" in args:
        print(summary())
    else:
        print(worksheet(pending_only="--pending" in args))
        print("\n" + summary())
