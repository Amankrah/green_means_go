"""
models.py — application ORM models: users, the entities they manage (farms,
facilities), and their saved assessments.

Ownership is uniform: every managed row and every assessment carries the id of the
user who created it, and all reads are scoped to that user. Roles determine which
kind of entity a user works with (see ``UserRole``), not a separate permission table.

Column types are deliberately portable (String / Text / JSON) so the schema moves
from the SQLite dev database to hosted Postgres without change.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


class UserRole(str, enum.Enum):
    """The kinds of platform users."""

    extension_officer = "extension_officer"  # runs farm assessments for clients (no farm registry)
    farmer = "farmer"                          # owns farm profile(s); runs farm assessments
    processor = "processor"                    # owns facility profile(s); runs processing assessments
    researcher = "researcher"                  # runs farm + processing assessments (no registry)


class AssessmentType(str, enum.Enum):
    farm = "farm"
    processing = "processing"


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(String(32), nullable=False)
    organization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    email_verified: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, server_default=func.now()
    )

    farms: Mapped[list["Farm"]] = relationship(back_populates="creator", cascade="all, delete-orphan")
    facilities: Mapped[list["Facility"]] = relationship(back_populates="creator", cascade="all, delete-orphan")
    assessments: Mapped[list["Assessment"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    studies: Mapped[list["Study"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class Farm(Base):
    """A farm profile owned by a farmer user. Used to prefill assessments and keep a
    stable record. Extension officers and researchers do not own Farm rows — they enter
    farm details in the assessment wizard when assessing on a client's behalf."""

    __tablename__ = "farms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    region: Mapped[str | None] = mapped_column(String(64), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_ha: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Populated when an extension officer manages this farm on a client's behalf.
    farmer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    farmer_contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())

    creator: Mapped["User"] = relationship(back_populates="farms")
    assessments: Mapped[list["Assessment"]] = relationship(back_populates="farm")


class Facility(Base):
    """A processing facility owned by a processor user."""

    __tablename__ = "facilities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    facility_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    region: Mapped[str | None] = mapped_column(String(64), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())

    creator: Mapped["User"] = relationship(back_populates="facilities")
    assessments: Mapped[list["Assessment"]] = relationship(back_populates="facility")


class Assessment(Base):
    """A saved assessment. ``payload_json`` holds the full serializable engine response
    (including the embedded ISO report), so the record is self-contained. Replaces the
    former in-memory ``assessments_db`` / ``processing_assessments_db`` dicts."""

    __tablename__ = "assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    type: Mapped[AssessmentType] = mapped_column(String(16), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    farm_id: Mapped[str | None] = mapped_column(ForeignKey("farms.id"), index=True, nullable=True)
    facility_id: Mapped[str | None] = mapped_column(ForeignKey("facilities.id"), index=True, nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    region: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="completed", nullable=False)
    single_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    # Original submit payload so the owner can edit inputs and re-run in place.
    # Shape: {"api": <AssessmentRequest dump>, "form": <optional client form snapshot>}.
    request_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Optimistic-lock counter: bumped on every write. A concurrent recharacterize +
    # uncertainty that both read the same version can be detected and rejected (409).
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    # Points at the current AssessmentRevision (immutable history). Kept as a plain string
    # (not a FK) to avoid a circular assessments <-> assessment_revisions constraint.
    current_revision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, server_default=func.now()
    )

    owner: Mapped["User"] = relationship(back_populates="assessments")
    farm: Mapped["Farm | None"] = relationship(back_populates="assessments")
    facility: Mapped["Facility | None"] = relationship(back_populates="assessments")
    revisions: Mapped[list["AssessmentRevision"]] = relationship(
        back_populates="assessment", cascade="all, delete-orphan"
    )


class AssessmentRevision(Base):
    """An immutable snapshot of an assessment's full result payload. A new revision is
    written on every re-solve (recharacterize / uncertainty / rerun / review) instead of
    overwriting, so the result history is auditable and reproducible."""

    __tablename__ = "assessment_revisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    assessment_id: Mapped[str] = mapped_column(
        ForeignKey("assessments.id", ondelete="CASCADE"), index=True, nullable=False
    )
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    # What produced this revision: initial | recharacterize | uncertainty | rerun | review | edit.
    reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    lcia_method: Mapped[str | None] = mapped_column(String(128), nullable=True)
    single_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())

    assessment: Mapped["Assessment"] = relationship(back_populates="revisions")


class Study(Base):
    """A researcher-owned cohort grouping saved assessments for batch analysis and re-run."""

    __tablename__ = "studies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    assessment_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())

    owner: Mapped["User"] = relationship(back_populates="studies")


class BatchJob(Base):
    """An async, DB-tracked batch operation over a study (e.g. re-solving every member
    assessment). The client submits it, gets a job id back immediately, and polls status
    instead of holding a request open for minutes of CPU-bound work."""

    __tablename__ = "batch_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    study_id: Mapped[str | None] = mapped_column(ForeignKey("studies.id"), index=True, nullable=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # e.g. "study_rerun"
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )  # pending | running | completed | failed
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    succeeded: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    results_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, server_default=func.now()
    )


class ShareLink(Base):
    """Read-only token granting public GET access to one assessment's results."""

    __tablename__ = "share_links"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())
