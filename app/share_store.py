"""
share_store.py — read-only share tokens for assessment results.
"""
from __future__ import annotations

import secrets
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Assessment, ShareLink, User


def _new_token() -> str:
    return secrets.token_urlsafe(32)


def create_share_link(
    db: Session,
    *,
    user: User,
    assessment_id: str,
) -> Optional[ShareLink]:
    """Create or return an existing share token for an owned assessment."""
    assessment = db.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.user_id == user.id,
        )
    )
    if assessment is None:
        return None

    existing = db.scalar(
        select(ShareLink).where(
            ShareLink.assessment_id == assessment_id,
            ShareLink.user_id == user.id,
        )
    )
    if existing is not None:
        return existing

    link = ShareLink(
        token=_new_token(),
        assessment_id=assessment_id,
        user_id=user.id,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def get_assessment_by_share_token(db: Session, token: str) -> Optional[Assessment]:
    link = db.scalar(select(ShareLink).where(ShareLink.token == token))
    if link is None:
        return None
    return db.get(Assessment, link.assessment_id)
