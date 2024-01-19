# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from fastapi import APIRouter, Request

from marimo._ast.app import App
from marimo._runtime import requests
from marimo._runtime.requests import (
    CreationRequest,
    ExecutionRequest,
    SetUIElementValueRequest,
)
from marimo._server.print import print_shutdown
from marimo._server2.api.deps import SessionDep, SessionManagerDep
from marimo._server2.models.models import (
    BaseResponse,
    FunctionCallRequest,
    InstantiateRequest,
    RunRequest,
    SuccessResponse,
    UpdateComponentValuesRequest,
)
from marimo._server2.uvicorn_utils import close_uvicorn

# Router for execution endpoints
router = APIRouter()


@router.post("/set_ui_element_value", response_model=BaseResponse)
def set_ui_element_values(
    *,
    request: UpdateComponentValuesRequest,
    session: SessionDep,
) -> BaseResponse:
    """
    Set UI element values.
    """
    session.control_queue.put(
        SetUIElementValueRequest(
            zip(
                request.object_ids,
                request.values,
            )
        )
    )
    return SuccessResponse()


@router.post("/instantiate", response_model=BaseResponse)
def instantiate(
    *,
    request: InstantiateRequest,
    session: SessionDep,
    manager: SessionManagerDep,
) -> BaseResponse:
    """
    Instantiate the kernel.
    """
    app = manager.load_app()

    execution_requests: tuple[ExecutionRequest, ...]
    if app is None:
        # Instantiating an empty app
        # TODO(akshayka): In this case, don't need to run anything ...
        execution_requests = (
            ExecutionRequest(cell_id=App()._create_cell_id(None), code=""),
        )
    else:
        execution_requests = tuple(
            ExecutionRequest(cell_id=cell_data.cell_id, code=cell_data.code)
            for cell_data in app._cell_data.values()
        )

    session.control_queue.put(
        CreationRequest(
            execution_requests=execution_requests,
            set_ui_element_value_request=SetUIElementValueRequest(
                zip(request.object_ids, request.values)
            ),
        )
    )

    return SuccessResponse()


@router.post("/function_call", response_model=BaseResponse)
def function_call(
    *,
    request: FunctionCallRequest,
    session: SessionDep,
) -> BaseResponse:
    """Invoke an RPC"""
    session.control_queue.put(
        requests.FunctionCallRequest(
            function_call_id=request.function_call_id,
            namespace=request.namespace,
            function_name=request.function_name,
            args=request.args,
        )
    )

    return SuccessResponse()


@router.post("/interrupt", response_model=BaseResponse)
def interrupt(
    *,
    session: SessionDep,
) -> BaseResponse:
    """Interrupt the kernel's execution."""
    session.try_interrupt()

    return SuccessResponse()


@router.post("/run", response_model=BaseResponse)
def run_cell(
    *,
    request: RunRequest,
    session: SessionDep,
) -> BaseResponse:
    """Run multiple cells (and their descendants).

    Updates cell code in the kernel if needed; registers new cells
    for unseen cell IDs.

    Only allowed in edit mode.
    """
    session.control_queue.put(
        requests.ExecuteMultipleRequest(
            tuple(
                requests.ExecutionRequest(cell_id=cid, code=code)
                for cid, code in zip(request.cell_ids, request.codes)
            )
        )
    )

    return SuccessResponse()


@router.post("/shutdown", response_model=BaseResponse)
async def shutdown(
    *,
    mgr: SessionManagerDep,
    request: Request,
) -> BaseResponse:
    """Shutdown the kernel."""
    if not mgr.quiet:
        print_shutdown()
    mgr.shutdown()

    await close_uvicorn(request.app.state.server)
    return SuccessResponse()
