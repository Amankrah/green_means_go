"""
client.py: the one place the engine talks to the Anthropic API.

Design rules (see engine/llm/__init__.py):
  * The key is read at runtime from the process environment or app/.env (python-dotenv),
    held in a private module variable, and passed straight to the SDK. It is never logged,
    printed, written to a cache file, or put in an exception message.
  * Every call is a structured-output call (JSON schema), so the model can only answer
    inside a shape the caller defines. Callers validate the answer again in code.
  * Timeouts and retries are bounded; any SDK/API failure becomes an LLMError that carries
    only the exception class name and HTTP status, never the request or response object.
  * GMG_LLM=0 disables every model call. Tests inject a fake object with the same
    `complete_json` method instead of the real client.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Optional, Protocol

_REPO = Path(__file__).resolve().parents[2]
_ENV_FILE = _REPO / "app" / ".env"

# Model id from the claude-api skill (current default Opus model, 2026-10 table).
# Override with GMG_LLM_MODEL if a deployment wants a different tier.
DEFAULT_MODEL = "claude-opus-5-5"

# Bounded network behaviour: wall clock per call is at most TIMEOUT_S x (MAX_RETRIES + 1).
TIMEOUT_S = float(os.getenv("GMG_LLM_TIMEOUT", "60"))
MAX_RETRIES = int(os.getenv("GMG_LLM_MAX_RETRIES", "2"))

_key_lock = threading.Lock()
_key_cache: dict[str, Optional[str]] = {}
_client_singleton: Optional["AnthropicJSONClient"] = None


class LLMError(RuntimeError):
    """A model call failed. The message never contains credentials or request bodies."""


class StructuredLLM(Protocol):
    """What classify / adjudicate / the narrative generator need from a model client."""

    model: str

    def complete_json(self, *, system: str, user: str, schema: dict,
                      max_tokens: int = 2048, effort: str = "low") -> dict: ...


def _flag_off(name: str) -> bool:
    return os.getenv(name, "").strip() == "0"


def llm_globally_disabled() -> bool:
    """True when GMG_LLM=0: no model calls anywhere, deterministic rules only."""
    return _flag_off("GMG_LLM")


def _api_key() -> Optional[str]:
    """Resolve the key once per process: env var first, then app/.env. Never returned to
    callers outside this module, never logged."""
    with _key_lock:
        if "k" not in _key_cache:
            key = os.environ.get("ANTHROPIC_API_KEY")
            if not key and _ENV_FILE.exists():
                try:
                    from dotenv import dotenv_values
                    key = dotenv_values(_ENV_FILE).get("ANTHROPIC_API_KEY")
                except Exception:
                    key = None
            _key_cache["k"] = (key or "").strip() or None
        return _key_cache["k"]


def has_api_key() -> bool:
    return _api_key() is not None


def _scrub(text: str) -> str:
    key = _api_key()
    if key and key in text:
        text = text.replace(key, "[redacted]")
    return text


def _text_of(response: Any) -> str:
    """First text block of a Messages response, tolerant of block types the installed SDK
    version does not model (thinking, fallback, ...)."""
    for block in getattr(response, "content", None) or []:
        btype = getattr(block, "type", None)
        if btype is None and isinstance(block, dict):
            btype = block.get("type")
        if btype == "text":
            text = getattr(block, "text", None)
            if text is None and isinstance(block, dict):
                text = block.get("text")
            if text:
                return text
    return ""


class AnthropicJSONClient:
    """Thin wrapper over the official `anthropic` SDK for structured-output calls.

    Uses `output_config.format` (JSON schema) and `output_config.effort`. The installed SDK
    may predate those typed parameters, so they are sent through `extra_body`, which every
    SDK method accepts. Thinking is left at the model default (adaptive; it cannot be
    disabled on Opus 5.5), and the effort level keeps it short for routine calls.
    """

    def __init__(self, model: Optional[str] = None):
        import anthropic  # imported lazily so GMG_LLM=0 runs never need the SDK

        key = _api_key()
        if not key:
            raise LLMError("no ANTHROPIC_API_KEY configured")
        self.model = model or os.getenv("GMG_LLM_MODEL", DEFAULT_MODEL)
        self._anthropic = anthropic
        self._sdk = anthropic.Anthropic(api_key=key, timeout=TIMEOUT_S, max_retries=MAX_RETRIES)

    def __repr__(self) -> str:  # never show the SDK object (it holds the key)
        return f"AnthropicJSONClient(model={self.model!r})"

    def complete_json(self, *, system: str, user: str, schema: dict,
                      max_tokens: int = 2048, effort: str = "low") -> dict:
        extra_body: dict = {"output_config": {"effort": effort,
                                              "format": {"type": "json_schema", "schema": schema}}}
        extra_headers: dict = {}
        if not _flag_off("GMG_LLM_FALLBACKS"):
            # Server-side refusal fallback (claude-api skill default for Opus 5.5).
            extra_body["fallbacks"] = "default"
            extra_headers["anthropic-beta"] = "server-side-fallback-2026-07-01"
        a = self._anthropic
        try:
            resp = self._sdk.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                extra_body=extra_body,
                extra_headers=extra_headers or None,
            )
        except a.APIStatusError as e:  # 4xx / 5xx after SDK retries
            raise LLMError(f"Anthropic API error {type(e).__name__} (HTTP {e.status_code})") from None
        except a.APIConnectionError as e:  # network / timeout after SDK retries
            raise LLMError(f"Anthropic connection error {type(e).__name__}") from None
        except Exception as e:  # anything else: class name only
            raise LLMError(_scrub(f"Anthropic client failure {type(e).__name__}")) from None

        stop = getattr(resp, "stop_reason", None)
        if stop == "refusal":
            raise LLMError("model declined the request (stop_reason=refusal)")
        if stop == "max_tokens":
            raise LLMError("model output truncated (stop_reason=max_tokens)")
        text = _text_of(resp)
        try:
            data = json.loads(text)
        except (TypeError, ValueError):
            raise LLMError("model returned non-JSON output") from None
        if not isinstance(data, dict):
            raise LLMError("model returned JSON that is not an object")
        return data


def get_client() -> Optional[StructuredLLM]:
    """The process-wide real client, or None when GMG_LLM=0 or no key is configured."""
    global _client_singleton
    if llm_globally_disabled() or not has_api_key():
        return None
    if _client_singleton is None:
        try:
            _client_singleton = AnthropicJSONClient()
        except Exception:
            return None
    return _client_singleton


def _reset_for_tests() -> None:
    global _client_singleton
    _client_singleton = None
    with _key_lock:
        _key_cache.clear()
