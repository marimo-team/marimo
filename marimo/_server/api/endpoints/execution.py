# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from starlette.requests import Request

from marimo import _loggers
from marimo._ast.app import App
from marimo._runtime import requests
from marimo._runtime.requests import (
    CreationRequest,
    ExecutionRequest,
    SetUIElementValueRequest,
)
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_request
from marimo._server.models.models import (
    BaseResponse,
    FunctionCallRequest,
    InstantiateRequest,
    RunRequest,
    SuccessResponse,
    UpdateComponentValuesRequest,
)
from marimo._server.router import APIRouter
from marimo._server.uvicorn_utils import close_uvicorn

LOGGER = _loggers.marimo_logger()

# Router for execution endpoints
router = APIRouter()


@router.post("/set_ui_element_value")
async def set_ui_element_values(
    *,
    request: Request,
) -> BaseResponse:
    """
    Set UI element values.
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=UpdateComponentValuesRequest)
    app_state.require_current_session().put_request(
        SetUIElementValueRequest(
            zip(
                body.object_ids,
                body.values,
            )
        )
    )
    return SuccessResponse()


@router.post("/instantiate")
async def instantiate(
    *,
    request: Request,
) -> BaseResponse:
    """
    Instantiate the kernel.
    """
    app_state = AppState(request)
    notebook = app_state.session_manager.load_app()
    body = await parse_request(request, cls=InstantiateRequest)

    execution_requests: tuple[ExecutionRequest, ...]
    if notebook is None:
        # Instantiating an empty app
        # TODO(akshayka): In this case, don't need to run anything ...
        execution_requests = (
            ExecutionRequest(cell_id=App()._create_cell_id(None), code=""),
        )
    else:
        execution_requests = tuple(
            ExecutionRequest(cell_id=cell_data.cell_id, code=cell_data.code)
            for cell_data in notebook._cell_data.values()
        )

    app_state.require_current_session().put_request(
        CreationRequest(
            execution_requests=execution_requests,
            set_ui_element_value_request=SetUIElementValueRequest(
                zip(body.object_ids, body.values)
            ),
        )
    )

    return SuccessResponse()


@router.post("/function_call")
async def function_call(
    *,
    request: Request,
) -> BaseResponse:
    """Invoke an RPC"""
    app_state = AppState(request)
    body = await parse_request(request, cls=FunctionCallRequest)
    app_state.require_current_session().put_request(
        requests.FunctionCallRequest(
            function_call_id=body.function_call_id,
            namespace=body.namespace,
            function_name=body.function_name,
            args=body.args,
        )
    )

    return SuccessResponse()


@router.post("/interrupt")
async def interrupt(
    *,
    request: Request,
) -> BaseResponse:
    """Interrupt the kernel's execution."""
    app_state = AppState(request)
    app_state.require_current_session().try_interrupt()

    return SuccessResponse()


@router.post("/run")
async def run_cell(
    *,
    request: Request,
) -> BaseResponse:
    """Run multiple cells (and their descendants).

    Updates cell code in the kernel if needed; registers new cells
    for unseen cell IDs.

    Only allowed in edit mode.
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=RunRequest)
    app_state.require_current_session().put_request(
        requests.ExecuteMultipleRequest(
            tuple(
                requests.ExecutionRequest(cell_id=cid, code=code)
                for cid, code in zip(body.cell_ids, body.codes)
            )
        )
    )

    return SuccessResponse()


@router.post("/shutdown")
async def shutdown(
    *,
    request: Request,
) -> BaseResponse:
    """Shutdown the kernel."""
    LOGGER.debug("Received shutdown request")
    app_state = AppState(request)
    app_state.session_manager.shutdown()

    await close_uvicorn(app_state.server)
    return SuccessResponse()
