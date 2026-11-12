"""
fakes.py: an in-process stand-in for the model client, used by tests so they never call
the real API. It satisfies client.StructuredLLM.
"""
from __future__ import annotations

from typing import Callable, Union

Responder = Union[dict, Callable[[str, str, dict], dict]]


class FakeLLM:
    """Returns a scripted JSON answer (a dict, or a function of (system, user, schema)).
    Records every call so tests can assert whether the model was consulted."""

    def __init__(self, responder: Responder, model: str = "fake-model", error: Exception | None = None):
        self.responder = responder
        self.model = model
        self.error = error
        self.calls: list[dict] = []

    def complete_json(self, *, system: str, user: str, schema: dict,
                      max_tokens: int = 2048, effort: str = "low") -> dict:
        self.calls.append({"system": system, "user": user, "schema": schema,
                           "max_tokens": max_tokens, "effort": effort})
        if self.error is not None:
            raise self.error
        if callable(self.responder):
            return self.responder(system, user, schema)
        return dict(self.responder)
