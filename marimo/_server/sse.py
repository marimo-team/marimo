# Copyright 2026 Marimo. All rights reserved.
"""Server-sent events (SSE) framing and connection utilities.

Shared by every endpoint that streams `text/event-stream` responses (the
session `/sse` transport and the scratchpad `/api/kernel/execute` stream).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.requests import Request

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    # Disable proxy buffering (nginx) so events are delivered immediately
    "X-Accel-Buffering": "no",
}

HEARTBEAT_EVENT = ": keep-alive\n\n"


def format_sse_event(data: str, event: str | None = None) -> str:
    """Frame `data` as a server-sent event.

    Multi-line payloads are split into one `data:` line each, per the SSE
    spec; clients rejoin them with newlines.
    """
    lines = "".join(f"data: {line}\n" for line in data.split("\n"))
    if event is None:
        return f"{lines}\n"
    return f"event: {event}\n{lines}\n"


def format_close_event(code: int, reason: str) -> str:
    """Frame the SSE equivalent of a WebSocket close frame."""
    return format_sse_event(
        json.dumps({"code": code, "reason": reason}), event="close"
    )


async def wait_for_http_disconnect(request: Request) -> None:
    """Wait until the client disconnects.

    `request._receive` is the ASGI `receive` callable; reading it is the
    standard way to detect disconnects. Note that on ASGI servers
    advertising spec_version < 2.4 (e.g. uvicorn), Starlette's
    `StreamingResponse` also listens on the same receive channel and
    cancels the response on disconnect — so callers must not rely on this
    helper as their only cleanup path; treat it as a prompt-shutdown
    signal and put teardown in a `finally` that also runs on cancellation.
    """
    while True:
        message = await request._receive()
        if message.get("type") == "http.disconnect":
            return
