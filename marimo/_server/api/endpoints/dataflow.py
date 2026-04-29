# Copyright 2026 Marimo. All rights reserved.
"""Dataflow API endpoints.

Exposes a marimo notebook as a typed reactive function via:
- GET  /api/v1/dataflow/schema — static input/output/trigger schema
- POST /api/v1/dataflow/run    — run with inputs, stream subscribed vars (SSE)
"""

from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

import msgspec
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from marimo import _loggers
from marimo._dataflow.protocol import (
    DataflowSchema,
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
from marimo._server.api.deps import AppState
from marimo._server.router import APIRouter

LOGGER = _loggers.marimo_logger()

router = APIRouter()

# Module-level session manager — initialized lazily on first request.
_session_managers: dict[str, DataflowSessionManager] = {}

_schema_encoder = msgspec.json.Encoder()

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
    """Request body for POST /run."""

    inputs: dict[str, Any] = msgspec.field(default_factory=dict)
    subscribe: list[str] = msgspec.field(default_factory=list)
    session_id: str | None = None
    encoding: dict[str, str] | None = None


def register_dataflow_app(
    file_key: str, session_manager: DataflowSessionManager
) -> None:
    """Register a DataflowSessionManager for a file key.

    Used both by the server lifecycle and for testing.
    """
    _session_managers[file_key] = session_manager


def _get_session_manager(request: Request) -> DataflowSessionManager:
    """Get or create the DataflowSessionManager for this app."""
    file_key = request.query_params.get("file", "__default__")

    if file_key in _session_managers:
        return _session_managers[file_key]

    # Fall back to AppState for full server context
    app_state = AppState(request)
    smgr = app_state.session_manager

    # For single-file mode (marimo edit foo.py), use the unique file key
    if file_key == "__default__":
        unique_key = smgr.file_router.get_unique_file_key()
        if unique_key is not None:
            file_key = unique_key

    file_mgr = smgr.file_router.get_file_manager(file_key, None)
    _session_managers[file_key] = DataflowSessionManager(file_mgr.app)
    return _session_managers[file_key]


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
    mgr = _get_session_manager(request)
    schema: DataflowSchema = await mgr.get_schema()
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

    mgr = _get_session_manager(request)
    session_id = body.session_id or f"s_{uuid4().hex[:8]}"
    session = mgr.get_or_create(session_id)

    subscribed = set(body.subscribe) if body.subscribe else set()

    schema = await mgr.get_schema()
    if not subscribed:
        subscribed = {o.name for o in schema.outputs}

    from starlette.responses import StreamingResponse

    async def event_stream():
        # Emit session_id as a comment so the client can persist it
        yield f": session_id={session_id}\n\n"

        events = await session.run(body.inputs, subscribed)

        for event in events:
            data = encode_event(event).decode("utf-8")
            event_type = _EVENT_TYPE_NAMES.get(type(event), "unknown")
            yield f"event: {event_type}\ndata: {data}\n\n"

        # Final heartbeat
        hb = HeartbeatEvent(timestamp=time.time())
        yield f"event: heartbeat\ndata: {encode_event(hb).decode('utf-8')}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Dataflow-Session-Id": session_id,
        },
    )
