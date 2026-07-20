"""
store.py — persistence helpers for saved assessments, shared by the production,
processing, chat, and workspace routers.

All reads are scoped to the owning user (the creator). Roles decide which entity a
user works with, not visibility: a farmer, an extension officer, and a processor each
see only the assessments they created. The full engine response is stored verbatim in
`Assessment.payload_json`, so `AssessmentResponse(**assessment.payload_json)` round-trips.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Assessment, AssessmentRevision, AssessmentType, User


class ConcurrencyError(Exception):
    """Raised when an optimistic-locked write is attempted against a stale version."""

    def __init__(self, expected: int, actual: int):
        self.expected = expected
        self.actual = actual
        super().__init__(f"stale write: expected version {expected}, current is {actual}")


def extract_single_score(payload: dict[str, Any]) -> Optional[float]:
    """The engine's single_score is a bare float (simple) or a {'value': ...} dict
    (comprehensive). Return a float for the indexed column, or None."""
    score = payload.get("single_score")
    if isinstance(score, dict):
        score = score.get("value")
    try:
        return float(score) if score is not None else None
    except (TypeError, ValueError):
        return None


def save_assessment(
    db: Session,
    *,
    user_id: str,
    a_type: AssessmentType,
    payload: dict[str, Any],
    farm_id: Optional[str] = None,
    facility_id: Optional[str] = None,
    title: Optional[str] = None,
    request_payload: Optional[dict[str, Any]] = None,
) -> Assessment:
    """Persist an engine result as an owned Assessment row. Uses the engine-minted id
    from the payload as the primary key so existing id-based links keep working."""
    # Use the engine-minted id when present; otherwise mint one now (not at flush time)
    # so the row id and the stored payload's id always match and reads round-trip.
    assessment_id = payload.get("id") or str(uuid.uuid4())
    payload["id"] = assessment_id

    assessment = Assessment(
        id=assessment_id,
        type=a_type,
        user_id=user_id,
        farm_id=farm_id,
        facility_id=facility_id,
        title=title,
        company_name=payload.get("company_name")
        or (payload.get("facility_profile") or {}).get("company_name"),
        country=payload.get("country"),
        region=payload.get("region"),
        single_score=extract_single_score(payload),
        payload_json=payload,
        request_json=request_payload,
        version=1,
    )
    db.add(assessment)
    db.flush()  # assign the row before writing its first revision
    _write_revision(db, assessment, payload, reason="initial")
    db.commit()
    db.refresh(assessment)
    return assessment


def _write_revision(
    db: Session, assessment: Assessment, payload: dict[str, Any], *, reason: str
) -> AssessmentRevision:
    """Append an immutable revision snapshot and point the assessment at it. Uses the
    assessment's current ``version`` as the revision number so the two stay aligned."""
    rev = AssessmentRevision(
        assessment_id=assessment.id,
        revision_no=assessment.version,
        reason=reason,
        lcia_method=payload.get("lcia_method"),
        single_score=extract_single_score(payload),
        payload_json=dict(payload),
    )
    db.add(rev)
    db.flush()
    assessment.current_revision_id = rev.id
    return rev


def replace_assessment(
    db: Session,
    assessment: Assessment,
    *,
    payload: dict[str, Any],
    title: Optional[str] = None,
    farm_id: Optional[str] = None,
    facility_id: Optional[str] = None,
    request_payload: Optional[dict[str, Any]] = None,
    reason: str = "edit",
    expected_version: Optional[int] = None,
) -> Assessment:
    """Update the current result and append an immutable revision (history is preserved,
    not overwritten). ``expected_version`` opts into optimistic locking: if it does not
    match the row's current version, a ConcurrencyError is raised so a stale concurrent
    write (e.g. recharacterize + uncertainty racing) is rejected rather than silently
    clobbering the other."""
    if expected_version is not None and assessment.version != expected_version:
        raise ConcurrencyError(expected_version, assessment.version)

    # Keep the existing row id. Mutate the caller's dict too so API responses that
    # return the engine result dict do not expose a freshly minted uuid (404 on GET).
    payload["id"] = assessment.id
    stored = dict(payload)

    assessment.version = (assessment.version or 1) + 1
    assessment.payload_json = stored
    assessment.company_name = stored.get("company_name") or (
        (stored.get("facility_profile") or {}).get("company_name")
    )
    assessment.country = stored.get("country")
    assessment.region = stored.get("region")
    assessment.single_score = extract_single_score(stored)
    assessment.status = "completed"
    if title is not None:
        assessment.title = title
    if farm_id is not None:
        assessment.farm_id = farm_id
    if facility_id is not None:
        assessment.facility_id = facility_id
    if request_payload is not None:
        assessment.request_json = request_payload

    db.add(assessment)
    db.flush()
    _write_revision(db, assessment, stored, reason=reason)
    db.commit()
    db.refresh(assessment)
    return assessment


def list_revisions(db: Session, assessment: Assessment) -> list[AssessmentRevision]:
    """Immutable revisions for an assessment, newest first. Synthesizes a single 'current'
    entry for rows created before revision history existed (no stored revisions)."""
    stmt = (
        select(AssessmentRevision)
        .where(AssessmentRevision.assessment_id == assessment.id)
        .order_by(AssessmentRevision.revision_no.desc())
    )
    rows = list(db.scalars(stmt))
    if rows:
        return rows
    # Legacy row (pre-history): present its current payload as revision 1.
    return [
        AssessmentRevision(
            id=assessment.current_revision_id or assessment.id,
            assessment_id=assessment.id,
            revision_no=assessment.version or 1,
            reason="current",
            lcia_method=(assessment.payload_json or {}).get("lcia_method"),
            single_score=assessment.single_score,
            payload_json=assessment.payload_json or {},
            created_at=assessment.updated_at,
        )
    ]


def get_revision(
    db: Session, assessment: Assessment, revision_no: int
) -> Optional[AssessmentRevision]:
    """One revision by number (ownership already enforced by the caller's assessment)."""
    stmt = select(AssessmentRevision).where(
        AssessmentRevision.assessment_id == assessment.id,
        AssessmentRevision.revision_no == revision_no,
    )
    row = db.scalar(stmt)
    if row is not None:
        return row
    # Legacy fallback: the synthesized current revision.
    revs = list_revisions(db, assessment)
    return next((r for r in revs if r.revision_no == revision_no), None)


def delete_owned_assessment(
    db: Session,
    user: User,
    assessment_id: str,
) -> bool:
    """Delete if owned by `user`. Returns True when a row was removed."""
    assessment = get_owned_assessment(db, user, assessment_id)
    if assessment is None:
        return False
    db.delete(assessment)
    db.commit()
    return True


def get_owned_assessment(
    db: Session,
    user: User,
    assessment_id: str,
    a_type: Optional[AssessmentType] = None,
) -> Optional[Assessment]:
    """Return the assessment if it exists AND belongs to `user`, else None. Not owned
    is indistinguishable from not found on purpose (no existence leak)."""
    stmt = select(Assessment).where(
        Assessment.id == assessment_id,
        Assessment.user_id == user.id,
    )
    if a_type is not None:
        stmt = stmt.where(Assessment.type == a_type)
    return db.scalar(stmt)


def list_owned_assessments(
    db: Session,
    user: User,
    a_type: Optional[AssessmentType] = None,
) -> list[Assessment]:
    stmt = select(Assessment).where(Assessment.user_id == user.id)
    if a_type is not None:
        stmt = stmt.where(Assessment.type == a_type)
    stmt = stmt.order_by(Assessment.created_at.desc())
    return list(db.scalars(stmt))
