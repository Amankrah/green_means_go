"""
intelligence/routes.py: HTTP surface of the intelligence layer (engine/llm).

  POST /classify           free text -> controlled-vocabulary label + confirmation flag,
                           so the wizard can ask "did you mean X? confirm".
  POST /reports/narrative  grounded plain-language or ISO 14044 narrative for an assessment
                           (number-guarded; deterministic template when the model is off).
  GET  /intelligence/health  which features are live (never reveals the key).

All endpoints require a signed-in user, like the assessment endpoints, so anonymous traffic
cannot spend model calls.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.llm import classify as _classify  # noqa: E402
from engine.llm.client import DEFAULT_MODEL, has_api_key, llm_globally_disabled  # noqa: E402
from engine.llm.vocab import KINDS, VOCABULARIES  # noqa: E402

from auth.deps import get_current_user  # noqa: E402
from db import get_db  # noqa: E402
from models import User  # noqa: E402
from services.ai_report_generator import generate_narrative  # noqa: E402
from services.report_grounding import MissingIsoReportError  # noqa: E402
from store import get_owned_assessment  # noqa: E402

router = APIRouter(tags=["intelligence"])

Kind = Literal["crop", "fertiliser", "fuel", "raw_material", "packaging"]


class ClassifyRequest(BaseModel):
    kind: Kind
    text: str = Field(..., min_length=1, max_length=200)


class ClassifyItem(BaseModel):
    kind: Kind
    text: str = Field(..., min_length=1, max_length=200)


class ClassifyBatchRequest(BaseModel):
    items: List[ClassifyItem] = Field(..., min_length=1, max_length=50)


class ClassifyResponse(BaseModel):
    text: str
    kind: str
    label: Optional[str]
    confidence: float
    needs_confirmation: bool
    model: str
    cached: bool
    source: str
    suggestion_prompt: Optional[str] = None
    vocabulary_size: int


def _respond(kind: str, text: str) -> ClassifyResponse:
    r = _classify(kind, text)
    prompt = None
    if r["label"] and r["needs_confirmation"]:
        prompt = f"Did you mean '{r['label']}'?"
    elif r["label"] is None:
        prompt = "We could not recognise this entry. Please pick the closest option from the list."
    return ClassifyResponse(text=text, kind=kind, label=r["label"], confidence=r["confidence"],
                            needs_confirmation=r["needs_confirmation"], model=r["model"],
                            cached=r["cached"], source=r["source"], suggestion_prompt=prompt,
                            vocabulary_size=len(VOCABULARIES[kind]))


@router.post("/classify", response_model=ClassifyResponse)
async def classify_text(req: ClassifyRequest, user: User = Depends(get_current_user)):
    """Classify one free-text entry. A label with needs_confirmation=true should be shown
    as a suggestion the user confirms; a null label means the user must pick from the list."""
    return await run_in_threadpool(_respond, req.kind, req.text)


@router.post("/classify/batch", response_model=List[ClassifyResponse])
async def classify_batch(req: ClassifyBatchRequest, user: User = Depends(get_current_user)):
    return await run_in_threadpool(lambda: [_respond(i.kind, i.text) for i in req.items])


@router.get("/classify/vocabulary/{kind}")
async def classify_vocabulary(kind: Kind) -> dict:
    """The controlled vocabulary for a kind, so the UI can offer the full pick list."""
    return {"kind": kind, "labels": VOCABULARIES[kind]}


class NarrativeRequest(BaseModel):
    style: Literal["plain", "iso"] = "plain"
    assessment_id: Optional[str] = None
    assessment_data: Optional[dict] = None


@router.post("/reports/narrative")
async def report_narrative(req: NarrativeRequest, user: User = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    """Grounded narrative for an assessment the user owns (or inline data they hold)."""
    data = req.assessment_data
    if data is None and req.assessment_id:
        owned = get_owned_assessment(db, user, req.assessment_id)
        data = owned.payload_json if owned is not None else None
    if data is None:
        raise HTTPException(status_code=404, detail="No assessment context provided. "
                            "Pass assessment_data or a known assessment_id.")
    try:
        return await run_in_threadpool(generate_narrative, data, req.style)
    except MissingIsoReportError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/intelligence/health")
async def intelligence_health() -> dict:
    live = not llm_globally_disabled() and has_api_key()
    return {"status": "ok", "model": DEFAULT_MODEL, "model_calls_enabled": live,
            "kinds": list(KINDS)}
