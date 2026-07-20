"""Researcher study cohorts: CRUD and batch re-run."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from db import SessionLocal, get_db
from models import Assessment, BatchJob, Study, User
from production.models import AssessmentRequest
from production.routes import _request_archive, _run_farm_engine
from research_export import build_cohort_csv, build_export_json
from store import get_owned_assessment, replace_assessment

router = APIRouter(prefix="/studies", tags=["research-studies"])

MAX_RERUN = 20        # legacy synchronous /rerun cap (kept for back-compat)
MAX_BATCH = 500       # async /runs sanity bound

# Session factory the background job uses (its OWN session, independent of the request's).
# Overridable in tests so the job runs against the test database.
job_session_factory = SessionLocal


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
                reason="rerun",
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


# --------------------------------------------------------------------------------------
# Async batch re-run: submit a job, poll for progress. Lifts the synchronous 20-cap and
# the request-timeout constraint, so a whole cohort can be re-solved off the request path.
# --------------------------------------------------------------------------------------

class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    status: str
    study_id: Optional[str] = None
    total: int
    completed: int
    succeeded: int
    failed: int
    results_json: list
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


async def _run_study_rerun_job(job_id: str, user_id: str, assessment_ids: list[str]) -> None:
    """Background worker: re-solve each assessment, writing progress to the job row. Opens
    its OWN session (the request's is already gone) and never raises out."""
    db = job_session_factory()
    try:
        job = db.get(BatchJob, job_id)
        if job is None:
            return
        job.status = "running"
        db.commit()

        results: list[dict] = []
        succeeded = 0
        failed = 0
        for aid in assessment_ids:
            existing = db.scalar(
                select(Assessment).where(Assessment.id == aid, Assessment.user_id == user_id)
            )
            if existing is None:
                results.append({"assessment_id": aid, "status": "error", "error": "Assessment not found"})
                failed += 1
            else:
                api = (existing.request_json or {}).get("api")
                if not api:
                    results.append({"assessment_id": aid, "status": "error",
                                    "error": "No archived request_json.api; cannot re-run"})
                    failed += 1
                else:
                    try:
                        req = AssessmentRequest(**{**api, "form_snapshot": None})
                        engine_result = await _run_farm_engine(req)
                        replace_assessment(
                            db, existing, payload=engine_result, title=existing.title,
                            request_payload=_request_archive(req), reason="rerun",
                        )
                        results.append({"assessment_id": aid, "status": "ok"})
                        succeeded += 1
                    except Exception as exc:  # isolate per-item failures
                        results.append({"assessment_id": aid, "status": "error", "error": str(exc)})
                        failed += 1
            job.completed = succeeded + failed
            job.succeeded = succeeded
            job.failed = failed
            job.results_json = list(results)
            db.commit()

        job.status = "completed"
        db.commit()
    except Exception as exc:  # never let the worker die silently
        try:
            job = db.get(BatchJob, job_id)
            if job is not None:
                job.status = "failed"
                job.error = str(exc)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@router.post("/{study_id}/runs", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
def submit_study_rerun(
    study_id: str,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit an async batch re-run of every assessment in the study. Returns 202 with a
    job id immediately; poll GET /studies/{id}/runs/{job_id} for progress and results."""
    study = _get_owned_study(db, user, study_id)
    if study is None:
        raise HTTPException(status_code=404, detail="Study not found")
    ids = list(study.assessment_ids or [])
    if len(ids) > MAX_BATCH:
        raise HTTPException(
            status_code=422,
            detail=f"Study has {len(ids)} assessments; batch re-run supports at most {MAX_BATCH}",
        )

    job = BatchJob(
        user_id=user.id, study_id=study.id, kind="study_rerun",
        status="pending", total=len(ids), results_json=[],
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(_run_study_rerun_job, job.id, user.id, ids)
    return job


@router.get("/{study_id}/runs/{job_id}", response_model=JobOut)
def get_study_run(
    study_id: str,
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Poll a batch re-run job's status, progress counters, and per-item results."""
    job = db.scalar(
        select(BatchJob).where(
            BatchJob.id == job_id,
            BatchJob.study_id == study_id,
            BatchJob.user_id == user.id,
        )
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{study_id}/export.csv", tags=["research-export"])
def export_study_cohort_csv(
    study_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The whole cohort as one tidy long-format CSV (assessment_id, title, section,
    category, metric, value, unit) so a researcher loads the study in a single read_csv."""
    study = _get_owned_study(db, user, study_id)
    if study is None:
        raise HTTPException(status_code=404, detail="Study not found")

    exports: list[dict] = []
    for aid in (study.assessment_ids or []):
        row = get_owned_assessment(db, user, aid)
        if row is None:
            continue  # skip a member that was deleted since it was added
        a_type = row.type.value if hasattr(row.type, "value") else str(row.type)
        exports.append(build_export_json(
            assessment_id=row.id, a_type=a_type, title=row.title,
            payload=row.payload_json or {}, request_json=row.request_json,
        ))

    csv_text = build_cohort_csv(exports)
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="study_{study_id}.csv"'},
    )
