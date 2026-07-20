"""
share/routes.py — read-only public access to assessment results via share token.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from db import get_db
from models import User
from share_store import create_share_link, get_assessment_by_share_token
from store import get_owned_assessment

router = APIRouter(tags=["research-share"])


def _read_only_payload(payload: dict) -> dict:
    """Strip fields that imply mutability or owner-only operations."""
    return {
        k: v
        for k, v in payload.items()
        if k not in {"share_token"}
    }


@router.post("/me/assessments/{assessment_id}/share")
def create_assessment_share_link(
    assessment_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate (or return) a read-only share token for an owned assessment."""
    owned = get_owned_assessment(db, user, assessment_id)
    if owned is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    link = create_share_link(db, user=user, assessment_id=assessment_id)
    if link is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return {
        "assessment_id": assessment_id,
        "token": link.token,
        "share_path": f"/share/{link.token}",
    }


@router.get("/share/{token}")
def get_shared_assessment(token: str, db: Session = Depends(get_db)):
    """Return assessment payload read-only; no authentication required."""
    row = get_assessment_by_share_token(db, token)
    if row is None:
        raise HTTPException(status_code=404, detail="Share link not found")
    payload = row.payload_json or {}
    return {
        "id": row.id,
        "type": row.type.value if hasattr(row.type, "value") else str(row.type),
        "title": row.title,
        "read_only": True,
        "assessment": _read_only_payload(payload),
    }
