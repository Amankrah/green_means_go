"""Researcher study cohorts: CRUD and batch re-run."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from db import get_db
from models import Study, User
from production.models import AssessmentRequest
from production.routes import _request_archive, _run_farm_engine
from store import get_owned_assessment, replace_assessment

router = APIRouter(prefix="/studies", tags=["research-studies"])

MAX_RERUN = 20


class StudyCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    assessment_ids: list[str] = Field(default_factory=list)


class StudyUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    assessment_ids: Optional[list[str]] = None


class StudyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    user_id: str
    assessment_ids: list[str]
    created_at: datetime


def _get_owned_study(db: Session, user: User, study_id: str) -> Study | None:
    return db.scalar(
        select(Study).where(Study.id == study_id, Study.user_id == user.id)
    )


def _validate_assessment_ids(db: Session, user: User, ids: list[str]) -> list[str]:
    """Ensure every id belongs to the user; dedupe while preserving order."""
    seen: set[str] = set()
    out: list[str] = []
    for aid in ids:
        if aid in seen:
            continue
        seen.add(aid)
        row = get_owned_assessment(db, user, aid)
        if row is None:
            raise HTTPException(status_code=404, detail=f"Assessment not found: {aid}")
        out.append(aid)
    return out


@router.post("", response_model=StudyOut, status_code=status.HTTP_201_CREATED)
def create_study(
    body: StudyCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assessment_ids = _validate_assessment_ids(db, user, body.assessment_ids)
    study = Study(title=body.title, user_id=user.id, assessment_ids=assessment_ids)
    db.add(study)
    db.commit()
    db.refresh(study)
    return study


@router.get("", response_model=list[StudyOut])
def list_studies(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(Study).where(Study.user_id == user.id).order_by(Study.created_at.desc())
    )
    return list(rows)


@router.get("/{study_id}", response_model=StudyOut)
def get_study(
    study_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    study = _get_owned_study(db, user, study_id)
    if study is None:
        raise HTTPException(status_code=404, detail="Study not found")
    return study


@router.patch("/{study_id}", response_model=StudyOut)
def update_study(
    study_id: str,
    body: StudyUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    study = _get_owned_study(db, user, study_id)
    if study is None:
        raise HTTPException(status_code=404, detail="Study not found")
    if body.title is not None:
        study.title = body.title
    if body.assessment_ids is not None:
        study.assessment_ids = _validate_assessment_ids(db, user, body.assessment_ids)
    db.add(study)
    db.commit()
    db.refresh(study)
    return study


@router.delete("/{study_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_study(
    study_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    study = _get_owned_study(db, user, study_id)
    if study is None:
        raise HTTPException(status_code=404, detail="Study not found")
    db.delete(study)
    db.commit()


@router.post("/{study_id}/rerun")
async def rerun_study(
    study_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Re-run up to 20 assessments in a study; partial failures do not abort the batch."""
    study = _get_owned_study(db, user, study_id)
    if study is None:
        raise HTTPException(status_code=404, detail="Study not found")

    ids = list(study.assessment_ids or [])
    if len(ids) > MAX_RERUN:
        raise HTTPException(
            status_code=422,
            detail=f"Study has {len(ids)} assessments; batch re-run supports at most {MAX_RERUN}",
        )

    results: list[dict] = []
    succeeded = 0
    failed = 0

    for aid in ids:
        existing = get_owned_assessment(db, user, aid)
        if existing is None:
            results.append({"assessment_id": aid, "status": "error", "error": "Assessment not found"})
            failed += 1
            continue
        archive = existing.request_json or {}
        api = archive.get("api")
        if not api:
            results.append({
                "assessment_id": aid,
                "status": "error",
                "error": "No archived request_json.api; cannot re-run",
            })
            failed += 1
            continue
        try:
            req = AssessmentRequest(**{**api, "form_snapshot": None})
            engine_result = await _run_farm_engine(req)
            updated = replace_assessment(
                db,
                existing,
                payload=engine_result,
                title=existing.title,
                request_payload=_request_archive(req),
            )
            results.append({
                "assessment_id": aid,
                "status": "ok",
                "id": updated.id,
            })
            succeeded += 1
        except HTTPException as exc:
            results.append({
                "assessment_id": aid,
                "status": "error",
                "error": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
            })
            failed += 1
        except Exception as exc:
            results.append({"assessment_id": aid, "status": "error", "error": str(exc)})
            failed += 1

    return {
        "study_id": study.id,
        "results": results,
        "succeeded": succeeded,
        "failed": failed,
    }
