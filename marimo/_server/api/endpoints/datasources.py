# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.authentication import requires

from marimo import _loggers
from marimo._runtime.requests import (
    PreviewDatasetColumnRequest,
    PreviewSQLTableRequest,
)
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_request
from marimo._server.models.models import BaseResponse, SuccessResponse
from marimo._server.router import APIRouter
from marimo._types.ids import ConsumerId

if TYPE_CHECKING:
    from starlette.requests import Request

LOGGER = _loggers.marimo_logger()

# Router for data source endpoints
router = APIRouter()


@router.post("/preview_column")
@requires("edit")
async def preview_column(
    request: Request,
) -> BaseResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/PreviewDatasetColumnRequest"
    responses:
        200:
            description: Preview a column in a dataset
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    app_state = AppState(request)
    body = await parse_request(request, PreviewDatasetColumnRequest)
    app_state.require_current_session().put_control_request(
        body,
        from_consumer_id=ConsumerId(app_state.require_current_session_id()),
    )
    return SuccessResponse()


@router.get(
    "/preview_sql_table/{engine:path}/{database:path}/{schema:path}/{table_name:path}"
)
@requires("edit")
async def preview_sql_table(request: Request) -> BaseResponse:
    """
    parameters:
      - name: engine
        in: path
        required: true
        schema:
        type: string
        description: The SQL engine to use
      - name: database
        in: path
        required: true
        schema:
        type: string
        description: The SQL database to use
      - name: schema
        in: path
        required: true
        schema:
        type: string
        description: The SQL schema to use
      - name: table_name
        in: path
        required: true
        schema:
        type: string
        description: The SQL table to preview
      - name: request_id
        in: query
        required: true
        schema:
        type: string
        description: Request ID for the preview so that the response can be matched
    responses:
      200:
        description: Get table details from the SQL database
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/SuccessResponse"
    """
    app_state = AppState(request)
    engine, database, schema, table_name = (
        request.path_params["engine"],
        request.path_params["database"],
        request.path_params["schema"],
        request.path_params["table_name"],
    )
    request_id = request.query_params.get("request_id")
    app_state.require_current_session().put_control_request(
        PreviewSQLTableRequest(
            engine=engine,
            database=database,
            schema=schema,
            table_name=table_name,
            request_id=request_id,
        ),
        from_consumer_id=ConsumerId(app_state.require_current_session_id()),
    )
    return SuccessResponse()
