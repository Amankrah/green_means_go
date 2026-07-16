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

from models import Assessment, AssessmentType, User


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
        company_name=payload.get("company_name"),
        country=payload.get("country"),
        region=payload.get("region"),
        single_score=extract_single_score(payload),
        payload_json=payload,
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment


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
