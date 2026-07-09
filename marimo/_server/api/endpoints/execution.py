# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import uuid4

from starlette.authentication import requires
from starlette.responses import JSONResponse, StreamingResponse

from marimo import _loggers
from marimo._code_mode.screenshot_meta import (
    SCREENSHOT_AUTH_TOKEN_KEY,
    SCREENSHOT_SERVER_URL_KEY,
)
from marimo._runtime.commands import HTTPRequest, UpdateUIElementCommand
from marimo._server.api.deps import AppState
from marimo._server.api.endpoints.ws.ws_connection_validator import (
    FILE_QUERY_PARAM_KEY,
)
from marimo._server.api.endpoints.ws_endpoint import DOC_MANAGER
from marimo._server.api.utils import (
    dispatch_control_request,
    get_code_mode_credentials,
    parse_request,
)
from marimo._server.models.models import (
    BaseResponse,
    DebugCellRequest,
    ExecuteCellsRequest,
    ExecuteScratchpadRequest,
    InstantiateNotebookRequest,
    InvokeFunctionRequest,
    KernelStatusResponse,
    ModelRequest,
    SuccessResponse,
    UpdateUIElementValuesRequest,
)
from marimo._server.router import APIRouter
from marimo._server.uvicorn_utils import close_uvicorn
from marimo._server.workspace import MarimoFileKey
from marimo._session.consumer_policy import (
    TakeoverDecision,
    can_take_over_editing,
)
from marimo._session.types import KernelState
from marimo._types.ids import ConsumerId
from marimo._utils.asyncio_utils import cancel_and_wait

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


@router.get("/status")
@requires("edit")
async def kernel_status(
    *,
    request: Request,
) -> KernelStatusResponse:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
    responses:
        200:
            description: Report whether the kernel is currently executing.
                `running` means at least one cell is queued or running;
                `idle` means the kernel is alive but not executing; `stopped`
                means the kernel process is not running.
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/KernelStatusResponse"
    """
    app_state = AppState(request)
    session = app_state.require_current_session()

    if session.kernel_state() in (
        KernelState.STOPPED,
        KernelState.NOT_STARTED,
    ):
        return KernelStatusResponse(state="stopped")

    is_running = any(
        notification.status in ("queued", "running")
        for notification in session.session_view.cell_notifications.values()
    )
    return KernelStatusResponse(state="running" if is_running else "idle")


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
        snapshot_for_scratchpad,
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
        # Correlation ID: tags both the scratchpad command and the
        # listener so we wait for *our* completion and ignore
        # ``CompletedRun`` events from other commands on this session
        # (e.g. the ``session.instantiate`` call above, or concurrent
        # browser activity).
        run_id = str(uuid4())
        try:
            listener = ScratchCellListener(run_id=run_id)
            # Ensure we take a lock on the scratchpad before scoping the
            # listener. See #10035.
            async with session.scratchpad_lock:
                with session.scoped(listener):
                    http_req = HTTPRequest.from_request(request)
                    server_url, auth_token = get_code_mode_credentials(
                        app_state, request
                    )
                    http_req.meta[SCREENSHOT_SERVER_URL_KEY] = server_url
                    http_req.meta[SCREENSHOT_AUTH_TOKEN_KEY] = auth_token
                    notebook_cells, cell_outputs = snapshot_for_scratchpad(
                        session
                    )
                    session.put_control_request(
                        ExecuteScratchpadCommand(
                            code=body.code,
                            request=http_req,
                            notebook_cells=notebook_cells,
                            cell_outputs=cell_outputs,
                            run_id=run_id,
                        ),
                        from_consumer_id=None,
                    )
                    async for event in listener.stream():
                        yield event

                yield build_done_event(session, listener)
        finally:
            await cancel_and_wait(disconnect_task)

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

    session_id = app_state.get_current_session_id()
    if session_id is None:
        LOGGER.error("Missing Marimo-Session-Id header")
        return JSONResponse(
            status_code=400,
            content={"error": "Cannot take over session."},
        )
    caller_id = ConsumerId(session_id)

    session = app_state.get_current_session()
    if not session:
        LOGGER.error("No current session found")
        return JSONResponse(
            status_code=400,
            content={"error": "Cannot take over session."},
        )

    caller = session.room.get_consumer(caller_id)
    if not caller:
        LOGGER.error("No consumer found for caller ID %s", caller_id)
        return JSONResponse(
            status_code=400,
            content={"error": "Cannot take over session."},
        )

    takeover_decision = can_take_over_editing(session, caller_id)
    if takeover_decision != TakeoverDecision.ALLOW:
        LOGGER.debug("Takeover denied by policy for consumer %s", caller_id)
        return JSONResponse(
            status_code=403,
            content={"error": "Not allowed to take over session."},
        )

    session.room.promote_consumer_to_main(caller)

    return JSONResponse(status_code=200, content={"status": "ok"})
