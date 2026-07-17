"""
chat/routes.py — streaming, plain-language results chat for the farmer.

Replaces the old pre-generated AI report. Instead of a canned write-up, the farmer
opens a chat that is grounded on THEIR OWN computed results and can ask follow-up
questions. Context comes only from services.report_grounding (score, band, category
contributions, recommendations, matched-dataset names) — never raw ecoinvent rows.

Streaming is Server-Sent Events (SSE) over POST. The client holds the conversation
history and resends it each turn (stateless server).

A retrieval (RAG) seam is left in `retrieve_context()` for a future farmer-guide
knowledge base; it currently returns nothing.
"""
from __future__ import annotations

import json
import os
from typing import Any, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import anthropic

from services.report_grounding import (
    GROUNDING_RULES,
    MissingIsoReportError,
    format_grounding_for_prompt,
)
from db import get_db
from models import User
from auth.deps import get_current_user
from store import get_owned_assessment

router = APIRouter(prefix="/chat", tags=["chat"])

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 1024
TEMPERATURE = 0.3
MAX_TURNS = 16  # keep the last N messages so the prompt stays bounded

# One async client for the process; None if no key, so the endpoint can 503 cleanly.
_API_KEY = os.getenv("ANTHROPIC_API_KEY")
_client: Optional[anthropic.AsyncAnthropic] = (
    anthropic.AsyncAnthropic(api_key=_API_KEY) if _API_KEY else None
)

SYSTEM_INSTRUCTIONS = (
    "You are a friendly guide that explains a farm's life cycle assessment (LCA) "
    "results in plain, everyday language to the farmer who owns them.\n"
    "Rules for how you answer:\n"
    "- Use only the grounding data provided for this farm. Never invent numbers, "
    "methods, or claims. If something was not measured in this study, say so plainly.\n"
    "- Write as if talking to a smart person who is not a scientist. Short sentences. "
    "Avoid jargon; if a technical term is unavoidable, explain it in a few plain words.\n"
    "- Be concrete and point to the farm's own figures: the single score and its band, "
    "the biggest contributors, and the practical recommendations.\n"
    "- When asked how to improve, give practical, farm-level suggestions that follow from "
    "what actually drives this farm's impact.\n"
    "- Do not use em dashes. Do not use markdown headings or tables. Short paragraphs and "
    "simple bullet points are fine.\n"
    "- Keep answers focused and reasonably brief. These are screening results and a draft "
    "pending independent review, so gently note the uncertainty if a number is treated as exact.\n"
    + GROUNDING_RULES
)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(default_factory=list)
    assessment_id: Optional[str] = None
    assessment_data: Optional[dict] = None


def retrieve_context(assessment: dict) -> List[str]:
    """Grounded guidance for the farmer-guide layer.

    Returns short, cited practice snippets drawn from the deterministic recommendation
    engine — matched to THIS farm's hotspots and read from structured measure records, so
    there is nothing for the model to invent. Assessment-driven (not query-driven) so the
    grounding block stays byte-stable across a conversation and keeps the prompt cache.
    Never raises: guidance is additive, and chat must work even if it's unavailable.
    """
    try:
        from recommendations.service import guidance_for_chat
        return guidance_for_chat(assessment)
    except Exception:
        return []


def _resolve_assessment(req: ChatRequest, user: User, db: Session) -> dict:
    # Inline data (the client already holds this farm's result) is trusted for the
    # owner's own session; otherwise look the saved assessment up scoped to the user.
    if req.assessment_data:
        return req.assessment_data
    if req.assessment_id:
        owned = get_owned_assessment(db, user, req.assessment_id)
        if owned is not None:
            return owned.payload_json
    raise HTTPException(
        status_code=404,
        detail="No assessment context provided. Pass assessment_data or a known assessment_id.",
    )


def _build_system(grounding: str, assessment: dict) -> list[dict]:
    """System prompt as two blocks: static instructions, then this farm's grounding
    (plus any retrieved guidance). The grounding block is marked cacheable so repeated
    turns in the same conversation do not re-pay for it.

    The guidance is labelled distinctly from the farm's own measured results, and each
    line carries a source, so the model can tell 'this farm measured X' from 'general
    practice guidance says Y' — a grounding requirement, not decoration."""
    context = "GROUNDING (this farm's computed results, JSON):\n" + grounding
    extra = retrieve_context(assessment)
    if extra:
        context += (
            "\n\nPRACTICAL GUIDANCE (general good-practice measures matched to this "
            "farm's biggest impact sources; each is a suggestion with a source, NOT a "
            "measured result for this farm — present them as options and cite the source "
            "if asked):\n" + "\n".join(f"- {s}" for s in extra)
        )
    return [
        {"type": "text", "text": SYSTEM_INSTRUCTIONS},
        {"type": "text", "text": context, "cache_control": {"type": "ephemeral"}},
    ]


@router.post("/stream")
async def chat_stream(
    req: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stream a grounded, plain-language answer as Server-Sent Events.

    Emits `data: {"delta": "..."}` per token chunk, a terminal `event: done`, or an
    `event: error` if the model call fails mid-stream.
    """
    if _client is None:
        raise HTTPException(
            status_code=503,
            detail="Chat is unavailable: ANTHROPIC_API_KEY is not configured on the server.",
        )
    if not req.messages or req.messages[-1].role != "user":
        raise HTTPException(status_code=400, detail="messages must end with a user turn.")

    assessment = _resolve_assessment(req, user, db)
    try:
        grounding = format_grounding_for_prompt(assessment)
    except MissingIsoReportError as e:
        raise HTTPException(status_code=400, detail=str(e))

    system = _build_system(grounding, assessment)
    messages = [{"role": m.role, "content": m.content} for m in req.messages][-MAX_TURNS:]

    async def event_stream():
        try:
            async with _client.messages.stream(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                system=system,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    yield f"data: {json.dumps({'delta': text})}\n\n"
            yield "event: done\ndata: {}\n\n"
        except Exception as e:  # surface a clean error to the client, do not crash the app
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/health")
async def chat_health() -> dict[str, Any]:
    return {"status": "ok", "model": MODEL, "available": _client is not None}
