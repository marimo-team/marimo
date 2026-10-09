# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from contextlib import aclosing
from typing import TYPE_CHECKING

import msgspec
from starlette.authentication import requires
from starlette.responses import Response, StreamingResponse

from marimo._server.api.deps import AppState
from marimo._server.router import APIRouter
from marimo._server.sse import (
    HEARTBEAT_EVENT,
    SSE_HEADERS,
    wait_for_http_disconnect,
)
from marimo._utils.http import HTTPException, HTTPStatus

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from starlette.requests import Request
    from starlette.types import Receive, Scope, Send

pair_router = APIRouter()
PING_INTERVAL = 15.0


class _HandoffResponse(StreamingResponse):
    def __init__(self, stream: AsyncGenerator[bytes, None]) -> None:
        super().__init__(
            stream, media_type="text/event-stream", headers=SSE_HEADERS
        )
        self._stream = stream

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        # Cancellation during send can leave the generator suspended at yield.
        async with aclosing(self._stream):
            await super().__call__(scope, receive, send)


@pair_router.get("/notebooks/{id}/events", include_in_schema=False)
@requires("edit")
async def events(request: Request) -> StreamingResponse:
    """Attach to a notebook and receive live handoffs over SSE."""
    state = AppState(request)
    state.require_pair_preview()
    session = state.session_by_stable_id(request.path_params["id"])

    attachment = state.attachment_from_request()

    async def stream() -> AsyncGenerator[bytes, None]:
        handle = session.handoffs.attach(attachment)

        async def watch_disconnect() -> None:
            await wait_for_http_disconnect(request)
            session.handoffs.release(handle)

        disconnect_task = asyncio.create_task(watch_disconnect())
        try:
            while True:
                try:
                    event = await asyncio.wait_for(
                        handle.queue.get(), timeout=PING_INTERVAL
                    )
                except asyncio.TimeoutError:
                    yield HEARTBEAT_EVENT.encode("utf-8")
                    continue
                if event is None:
                    break
                yield event
        finally:
            disconnect_task.cancel()
            session.handoffs.release(handle)

    return _HandoffResponse(stream())


@pair_router.post("/notebooks/{id}/handoffs", include_in_schema=False)
@requires("edit")
async def handoffs(request: Request) -> Response:
    """Send any JSON content to all agents attached to the notebook."""
    state = AppState(request)
    state.require_pair_preview()
    session = state.session_by_stable_id(request.path_params["id"])
    try:
        payload = msgspec.json.decode(await request.body())
    except msgspec.DecodeError as error:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Invalid JSON handoff payload.",
        ) from error

    if not any(a.kind == "agent" for a in session.handoffs.attachments()):
        raise HTTPException(
            status_code=409,
            detail="No agent attached",
        )
    session.handoffs.publish(payload)
    return Response(status_code=202)
