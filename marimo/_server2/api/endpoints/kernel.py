from __future__ import annotations

from fastapi import APIRouter

from marimo._ast.app import App
from marimo._runtime.requests import (
    CreationRequest,
    ExecutionRequest,
    SetUIElementValueRequest,
)
from marimo._server import sessions
from marimo._server2.api.deps import SessionDep
from marimo._server2.models.models import (
    BaseResponse,
    InstantiateRequest,
    SuccessResponse,
    UpdateComponentValuesRequest,
)

# Router for kernel endpoints
router = APIRouter()


@router.post(
    "/set_ui_element_value",
    response_model=BaseResponse,
)
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


@router.post(
    "/instantiate",
    response_model=BaseResponse,
)
def instantiate(
    *,
    request: InstantiateRequest,
    session: SessionDep,
) -> BaseResponse:
    """
    Instantiate the kernel.
    """
    mgr = sessions.get_manager()
    app = mgr.load_app()

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
