"""
db.py — SQLAlchemy engine, session factory, and Base for the application database.

This is the *application* store (users, farms, facilities, saved assessments). It is
separate from the read-only reference LCA store used by the inventory router
(`data/canonical/lca_engineer.sqlite`).

Defaults to a local SQLite file so development needs no infrastructure. Set
`DATABASE_URL` (e.g. a Postgres URL) to point at a hosted database in production —
the models use portable column types (String/Text/JSON), so the same schema runs on
Postgres unchanged.
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Repo root is one level up from this file's directory (app/).
_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_DB_DIR = _ROOT / "data" / "app"
_DEFAULT_DB_PATH = _DEFAULT_DB_DIR / "greenmeansgo.sqlite"


def _default_sqlite_url() -> str:
    _DEFAULT_DB_DIR.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{_DEFAULT_DB_PATH}"


DATABASE_URL = os.getenv("DATABASE_URL", _default_sqlite_url())

# check_same_thread is a SQLite-only knob; assessments run in a threadpool, so
# connections may be touched from worker threads.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """Declarative base for all application ORM models."""


def get_db():
    """FastAPI dependency that yields a request-scoped session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables that don't yet exist. Safe to call on startup for the SQLite
    dev database; production uses Alembic migrations instead."""
    import models  # noqa: F401  (ensure models are registered on Base.metadata)

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()


def _ensure_sqlite_columns() -> None:
    """Add columns introduced after the first create_all for local SQLite DBs.
    Alembic handles this in production; create_all alone never ALTERs existing tables."""
    if not DATABASE_URL.startswith("sqlite"):
        return
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "assessments" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("assessments")}
    with engine.begin() as conn:
        if "request_json" not in existing:
            conn.execute(text("ALTER TABLE assessments ADD COLUMN request_json JSON"))
