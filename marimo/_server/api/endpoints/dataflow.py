# Copyright 2026 Marimo. All rights reserved.
"""Dataflow API endpoints.

Exposes a marimo notebook as a typed reactive function via:

- ``GET  /api/v1/dataflow/schema`` — typed input/output/trigger schema.
- ``POST /api/v1/dataflow/run`` — push input overrides, stream subscribed
  variable values back as Server-Sent Events.

These run on the same Starlette app as the editor when ``marimo edit`` is
launched with ``--enable-dataflow`` (or under ``marimo dataflow serve``).
The dataflow API and the editor websocket are both ``SessionConsumer``s
on the *same* :class:`Session`, so values pushed by one are observable
by the other in real time.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import msgspec
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse

from marimo import _loggers
from marimo._dataflow.protocol import (
    DataflowEvent,
    HeartbeatEvent,
    RunEvent,
    SchemaChangedEvent,
    SchemaEvent,
    SupersededEvent,
    TriggerResultEvent,
    VarErrorEvent,
    VarEvent,
    encode_event,
)
from marimo._dataflow.session import DataflowSessionManager
from marimo._runtime.commands import HTTPRequest
from marimo._server.api.deps import AppState
from marimo._server.router import APIRouter

LOGGER = _loggers.marimo_logger()

router = APIRouter()

_EVENT_TYPE_NAMES: dict[type, str] = {
    RunEvent: "run",
    VarEvent: "var",
    VarErrorEvent: "var-error",
    HeartbeatEvent: "heartbeat",
    SchemaEvent: "schema",
    SchemaChangedEvent: "schema-changed",
    SupersededEvent: "superseded",
    TriggerResultEvent: "trigger-result",
}


class DataflowRunRequest(msgspec.Struct, rename="camel"):
    """Request body for ``POST /run``."""

    inputs: dict[str, Any] = msgspec.field(default_factory=dict)
    subscribe: list[str] = msgspec.field(default_factory=list)
    session_id: str | None = None
    encoding: dict[str, str] | None = None


def _dataflow_manager(request: Request) -> DataflowSessionManager:
    """Return the per-server :class:`DataflowSessionManager`, lazy-initing it."""
    app_state = AppState(request)
    state = app_state.app.state
    mgr = getattr(state, "dataflow_manager", None)
    if mgr is None:
        mgr = DataflowSessionManager(app_state.session_manager)
        state.dataflow_manager = mgr
    return mgr


def _resolve_file_key(request: Request) -> str:
    """Determine which file the request targets.

    Single-notebook servers (the common ``marimo edit foo.py`` case) have
    one canonical file key; we use it when the client doesn't supply one.
    Multi-file servers must include ``?file=…``.
    """
    file_key = request.query_params.get("file")
    if file_key:
        return file_key
    smgr = AppState(request).session_manager
    unique = smgr.file_router.get_unique_file_key()
    if unique is None:
        raise ValueError(
            "Multi-file dataflow servers must include ?file=… in the URL"
        )
    return unique


@router.get("/schema")
async def get_schema(request: Request) -> Response:
    """
    parameters:
        - in: query
          name: file
          schema:
            type: string
          required: false
    responses:
        200:
            description: Dataflow schema (inputs, outputs, triggers)
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/DataflowSchema"
    """
    file_key = _resolve_file_key(request)
    bundle = _dataflow_manager(request).get_bundle(file_key)
    schema = await bundle.get_schema()
    return JSONResponse(
        content=msgspec.to_builtins(schema),
        headers={"Access-Control-Allow-Origin": "*"},
    )


@router.post("/run")
async def run_dataflow(request: Request) -> Response:
    """
    parameters:
        - in: query
          name: file
          schema:
            type: string
          required: false
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/DataflowRunRequest"
    responses:
        200:
            description: SSE stream of DataflowEvent
            content:
                text/event-stream:
                    schema:
                        type: string
    """
    body_bytes = await request.body()
    body = msgspec.json.decode(body_bytes, type=DataflowRunRequest)

    file_key = _resolve_file_key(request)
    bundle = _dataflow_manager(request).get_bundle(file_key)

    consumer_id = f"dataflow-sse-{uuid4().hex[:8]}"
    run_id = body.session_id or uuid4().hex[:8]
    schema = await bundle.get_schema()

    subscribed = (
        set(body.subscribe) if body.subscribe else {o.name for o in schema.outputs}
    )

    async def event_stream():
        async for event in bundle.run(
            inputs=body.inputs,
            subscribed=subscribed,
            consumer_id=consumer_id,
            run_id=run_id,
            request=HTTPRequest.from_request(request),
        ):
            yield _format_sse(event)
        yield _format_sse(HeartbeatEvent(timestamp=__import__("time").time()))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Dataflow-Consumer-Id": consumer_id,
            "X-Dataflow-Run-Id": run_id,
        },
    )


def _format_sse(event: DataflowEvent) -> str:
    data = encode_event(event).decode("utf-8")
    event_type = _EVENT_TYPE_NAMES.get(type(event), "unknown")
    return f"event: {event_type}\ndata: {data}\n\n"
