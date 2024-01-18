from __future__ import annotations

import mimetypes
import sys
from multiprocessing import shared_memory

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from marimo._ast.app import App
from marimo._config.utils import LOGGER
from marimo._runtime import requests
from marimo._runtime.requests import (
    CreationRequest,
    ExecutionRequest,
    SetUIElementValueRequest,
)
from marimo._runtime.virtual_file import EMPTY_VIRTUAL_FILE
from marimo._server.api.status import HTTPStatus
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
            ExecutionRequest(App()._create_cell_id(None), ""),
        )
    else:
        execution_requests = tuple(
            ExecutionRequest(cell_data.cell_id, cell_data.code)
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
                requests.ExecutionRequest(cid, code)
                for cid, code in zip(request.cell_ids, request.codes)
            )
        )
    )

    return SuccessResponse()


@router.post("/@file/{filename_and_length:path}")
def virtual_file(
    *,
    filename_and_length: str,
) -> Response:
    """Handler for virtual files."""

    LOGGER.debug("Getting virtual file: %s", filename_and_length)
    if filename_and_length == EMPTY_VIRTUAL_FILE.filename:
        return Response(content=b"", media_type="application/octet-stream")

    byte_length, filename = filename_and_length.split("-", 1)
    key = filename
    shm = None
    try:
        # NB: this can't be collapsed into a one-liner!
        # doing it in one line yields a 'released memoryview ...'
        # because shared_memory has built in ref-tracking + GC
        shm = shared_memory.SharedMemory(name=key)
        buffer_contents = bytes(shm.buf)[: int(byte_length)]
    except FileNotFoundError as err:
        LOGGER.debug(
            "Error retrieving shared memory for virtual file: %s", err
        )
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            detail="File not found",
        ) from err
    finally:
        if shm is not None:
            shm.close()
    mimetype, _ = mimetypes.guess_type(filename)
    return Response(
        content=buffer_contents,
        media_type=mimetype,
        headers={"Cache-Control": "max-age=86400"},
    )


@router.post("/shutdown", response_model=BaseResponse)
def shutdown(
    *,
    mgr: SessionManagerDep,
) -> BaseResponse:
    """Shutdown the kernel."""
    if not mgr.quiet:
        print_shutdown()
    mgr.shutdown()
    sys.exit(0)
