# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING
from uuid import uuid4

from starlette.authentication import requires
from starlette.responses import JSONResponse, StreamingResponse

from marimo import _loggers
from marimo._messaging.notification import AlertNotification
from marimo._runtime.commands import HTTPRequest, UpdateUIElementCommand
from marimo._server.api.deps import AppState
from marimo._server.api.endpoints.ws.ws_connection_validator import (
    FILE_QUERY_PARAM_KEY,
)
from marimo._server.api.endpoints.ws_endpoint import DOC_MANAGER
from marimo._server.api.utils import dispatch_control_request, parse_request
from marimo._server.models.models import (
    BaseResponse,
    DebugCellRequest,
    ExecuteCellsRequest,
    ExecuteScratchpadRequest,
    InstantiateNotebookRequest,
    InvokeFunctionRequest,
    ModelRequest,
    SuccessResponse,
    UpdateUIElementValuesRequest,
)
from marimo._server.router import APIRouter
from marimo._server.uvicorn_utils import close_uvicorn
from marimo._server.workspace import MarimoFileKey
from marimo._types.ids import ConsumerId

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from starlette.requests import Request

LOGGER = _loggers.marimo_logger()

# Router for execution endpoints
router = APIRouter()


@router.post("/set_ui_element_value")
@requires("read")
async def set_ui_element_values(
    *,
    request: Request,
) -> BaseResponse:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/UpdateUIElementValuesRequest"
    responses:
        200:
            description: Set UI element values
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=UpdateUIElementValuesRequest)
    app_state.require_current_session().put_control_request(
        UpdateUIElementCommand(
            object_ids=body.object_ids,
            values=body.values,
            token=str(uuid4()),
            request=HTTPRequest.from_request(request),
        ),
        from_consumer_id=ConsumerId(app_state.require_current_session_id()),
    )

    return SuccessResponse()


@router.post("/set_model_value")
@requires("read")
async def set_model_values(
    *,
    request: Request,
) -> BaseResponse:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/ModelRequest"
    responses:
        200:
            description: Set model value
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    return await dispatch_control_request(request, ModelRequest)


@router.post("/instantiate")
@requires("edit")
async def instantiate(
    *,
    request: Request,
) -> BaseResponse:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/InstantiateNotebookRequest"
    responses:
        200:
            description: Instantiate a component. Only allowed in edit mode;
                in run mode, instantiation happens server-side automatically.
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=InstantiateNotebookRequest)
    app_state.require_current_session().instantiate(
        body,
        http_request=HTTPRequest.from_request(request),
    )

    return SuccessResponse()


@router.post("/function_call")
@requires("read")
async def function_call(
    *,
    request: Request,
) -> BaseResponse:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/InvokeFunctionRequest"
    responses:
        200:
            description: Invoke an RPC
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    return await dispatch_control_request(request, InvokeFunctionRequest)


@router.post("/interrupt")
@requires("edit")
async def interrupt(
    *,
    request: Request,
) -> BaseResponse:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
    responses:
        200:
            description: Interrupt the kernel's execution
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    app_state = AppState(request)
    app_state.require_current_session().try_interrupt()

    return SuccessResponse()


@router.post("/run")
@requires("edit")
async def run_cell(
    *,
    request: Request,
) -> BaseResponse:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/ExecuteCellsRequest"
    responses:
        200:
            description: Run a cell. Updates cell code in the kernel if needed; registers new cells for unseen cell IDs. Only allowed in edit mode.
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=ExecuteCellsRequest)
    body.request = HTTPRequest.from_request(request)
    app_state.require_current_session().put_control_request(
        body.as_command(),
        from_consumer_id=ConsumerId(app_state.require_current_session_id()),
    )

    return SuccessResponse()


@router.post("/execute", include_in_schema=False)
@requires("edit")
async def execute_code(
    *,
    request: Request,
) -> StreamingResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/ExecuteScratchpadRequest"
    responses:
        200:
            description: Execute code in the kernel, streaming results as SSE.
            content:
                text/event-stream:
                    schema:
                        type: string
    """
    from marimo._runtime.commands import ExecuteScratchpadCommand
    from marimo._server.scratchpad import (
        ScratchCellListener,
        build_done_event,
    )

    app_state = AppState(request)
    body = await parse_request(request, cls=ExecuteScratchpadRequest)
    session = app_state.require_current_session()

    # Register cells into the graph without executing them so that
    # code_mode's run_cell can resolve dependencies. The kernel
    # no-ops if already instantiated.
    session.instantiate(
        InstantiateNotebookRequest(object_ids=[], values=[], auto_run=False),
        http_request=HTTPRequest.from_request(request),
    )

    async def _watch_disconnect() -> None:
        """Wait for client disconnect and interrupt the kernel."""
        while True:
            # request._receive is the ASGI `receive` callable. Although
            # it's a private Starlette attribute, it's the standard way to
            # detect disconnects and doesn't race with StreamingResponse
            # (which only writes to the send channel, never reads receive).
            message = await request._receive()
            if message.get("type") == "http.disconnect":
                session.try_interrupt()
                return

    async def sse_generator() -> AsyncGenerator[str, None]:
        disconnect_task = asyncio.create_task(_watch_disconnect())
        try:
            listener = ScratchCellListener()
            with session.scoped(listener):
                async with session.scratchpad_lock:
                    http_req = HTTPRequest.from_request(request)
                    # Inject trusted server URL and auth token for
                    # code-mode screenshot support.  We use the
                    # server's own host/port (from config) rather
                    # than the request's Host header to prevent
                    # header-spoofing attacks.
                    http_req.meta["screenshot_auth_token"] = str(
                        app_state.session_manager.auth_token
                    )
                    base_url = app_state.base_url.rstrip("/")
                    scheme = request.url.scheme or "http"
                    http_req.meta["screenshot_server_url"] = (
                        f"{scheme}://{app_state.host}:{app_state.port}{base_url}"
                    )
                    session.put_control_request(
                        ExecuteScratchpadCommand(
                            code=body.code,
                            request=http_req,
                            notebook_cells=tuple(session.document.cells),
                        ),
                        from_consumer_id=None,
                    )
                    async for event in listener.stream():
                        yield event

                yield build_done_event(session, listener)
        finally:
            disconnect_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await disconnect_task

    return StreamingResponse(sse_generator(), media_type="text/event-stream")


@router.post("/scratchpad/run")
@requires("edit")
async def run_scratchpad(
    *,
    request: Request,
) -> BaseResponse:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/ExecuteScratchpadRequest"
    responses:
        200:
            description: Run the scratchpad
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    return await dispatch_control_request(request, ExecuteScratchpadRequest)


@router.post("/pdb/pm")
@requires("edit")
async def run_post_mortem(
    *,
    request: Request,
) -> BaseResponse:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/DebugCellRequest"
    responses:
        200:
            description: Run a post mortem on the most recent failed cell.
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    return await dispatch_control_request(request, DebugCellRequest)


@router.post("/restart_session")
@requires("edit")
async def restart_session(
    *,
    request: Request,
) -> BaseResponse:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
    responses:
        200:
            description: Restart the current session without affecting other sessions.
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    app_state = AppState(request)
    session_manager = app_state.session_manager

    # This just closes the session, and the frontend will
    # do a full reload, which will restart the session.
    session_id = app_state.require_current_session_id()
    session = app_state.require_current_session()
    session_manager.close_session(session_id)

    # Close RTC doc if it exists
    file_key: MarimoFileKey | None = (
        app_state.query_params(FILE_QUERY_PARAM_KEY)
        or session_manager.workspace.get_unique_file_key()
        or session.app_file_manager.path
    )
    if file_key is not None:
        await DOC_MANAGER.remove_doc(file_key)
    else:
        LOGGER.warning("Unable to close RTC doc as no file key was provided")

    return SuccessResponse()


@router.post("/shutdown")
@requires("edit")
async def shutdown(
    *,
    request: Request,
) -> BaseResponse:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: false
    responses:
        200:
            description: Shutdown the kernel
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    LOGGER.debug("Received shutdown request")
    app_state = AppState(request)
    session_manager = app_state.session_manager
    workspace = session_manager.workspace

    def shutdown_server() -> None:
        app_state.session_manager.shutdown()
        close_uvicorn(app_state.server)

    # If we are only operating on a single file (new or explicit file),
    # and there are no other sessions (user may have opened another notebook
    # from the file explorer) then we should shutdown the whole server
    key = workspace.get_unique_file_key()
    if key and len(session_manager.sessions) <= 1:
        shutdown_server()
        return SuccessResponse()

    # Otherwise, get the session
    session_id = app_state.get_current_session_id()
    if not session_id:
        shutdown_server()
        return SuccessResponse()

    was_shutdown = session_manager.close_session(session_id)
    if not was_shutdown:
        shutdown_server()

    return SuccessResponse()


@router.post("/takeover")
@requires("edit")
async def takeover_endpoint(
    *,
    request: Request,
) -> JSONResponse:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
    responses:
        200:
            description: Successfully closed existing sessions
            content:
                application/json:
                    schema:
                        type: object
                        properties:
                            status:
                                type: string
    """
    app_state = AppState(request)

    file_key: MarimoFileKey | None = (
        app_state.query_params(FILE_QUERY_PARAM_KEY)
        or app_state.session_manager.workspace.get_unique_file_key()
    )
    if file_key is None:
        LOGGER.error("No file key provided")
        return JSONResponse(
            status_code=400,
            content={"error": "Cannot take over session."},
        )

    # Find and close any existing sessions for this file
    existing_session = app_state.session_manager.get_session_by_file_key(
        file_key
    )
    if existing_session is not None:
        # Send a disconnect message to the client
        existing_session.notify(
            AlertNotification(
                title="Session taken over",
                description="Another user has taken over this session.",
                variant="danger",
            ),
            from_consumer_id=None,
        )
        # Wait 100ms to ensure the client has received the message
        await asyncio.sleep(0.1)
        existing_session.disconnect_main_consumer()
    else:
        LOGGER.warning("No existing session found for file key %s", file_key)

    return JSONResponse(status_code=200, content={"status": "ok"})
