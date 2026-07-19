"""
assessment_stream.py — Server-Sent Events (SSE) bridge for long-running assessments.

The engine solve is synchronous and CPU-bound (a minute or two). Instead of making the
client wait on a single POST, the streaming endpoints run the solve in a worker thread and
stream the engine's own stage callbacks back as SSE `progress` events, then a terminal
`result` (or `error`) event. The frontend renders the live stage in its progress view.

Cross-thread bridge: the blocking work runs via loop.run_in_executor; its progress callback
(called from the worker thread) hands events to the event loop with call_soon_threadsafe, and
the async generator drains an asyncio.Queue and yields SSE frames.
"""
from __future__ import annotations

import asyncio
import json
import traceback
from typing import Any, AsyncIterator, Callable

# text/event-stream frame. Each event is one JSON object on a single `data:` line.
SSE_MEDIA_TYPE = "text/event-stream"
SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # disable proxy buffering (nginx) so events flush immediately
}


def _frame(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


async def stream_assessment(
    run_fn: Callable[[Callable[..., None]], dict[str, Any]],
    *,
    save_fn: Callable[[dict[str, Any]], None] | None = None,
) -> AsyncIterator[str]:
    """Run `run_fn(on_progress)` (a blocking engine call) in a worker thread and yield SSE
    frames: one `progress` event per engine stage, then a single `result` or `error` event.

    run_fn receives an `on_progress(stage, detail="", index=None, total=None)` callback.
    save_fn, if given, persists the result (in the worker thread, with its own DB session)
    before the `result` event is emitted, so the client can navigate to the saved id.
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def on_progress(stage: str, detail: str = "", index=None, total=None) -> None:
        loop.call_soon_threadsafe(
            queue.put_nowait,
            {"type": "progress", "stage": stage, "detail": detail, "index": index, "total": total},
        )

    def work() -> None:
        try:
            result = run_fn(on_progress)
            if save_fn is not None:
                save_fn(result)
            loop.call_soon_threadsafe(queue.put_nowait, {"type": "result", "data": result})
        except Exception as exc:  # noqa: BLE001 — surface any failure to the client as an event
            traceback.print_exc()
            loop.call_soon_threadsafe(
                queue.put_nowait, {"type": "error", "message": str(exc) or "Assessment failed"}
            )

    # Kick off the blocking work; we do not await it directly — the terminal queue event
    # (result/error) is our signal that it finished.
    loop.run_in_executor(None, work)

    # Emit an immediate frame so the connection opens and the client shows progress at once.
    yield _frame({"type": "progress", "stage": "prepare", "detail": "Starting the assessment"})

    while True:
        item = await queue.get()
        yield _frame(item)
        if item["type"] in ("result", "error"):
            break
