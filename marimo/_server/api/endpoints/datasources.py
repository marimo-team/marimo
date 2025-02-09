# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.authentication import requires

from marimo import _loggers
from marimo._runtime.requests import (
    PreviewDatasetColumnRequest,
    PreviewSQLTableInfoRequest,
    PreviewSQLTablesRequest,
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


@router.get("/preview_sql_tables/{engine:path}/{database:path}/{schema:path}")
@requires("edit")
async def preview_sql_tables(request: Request) -> BaseResponse:
    """
    parameters:
        - name: engine
          in: path
          required: true
          schema:
            type: string
          description: The SQL engine to use
          # TODO: Can this be empty?
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
    responses:
        200:
            description: Get tables from the SQL database
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    app_state = AppState(request)
    # TODO: Add some validation
    engine, database, schema = (
        request.path_params["engine"],
        request.path_params["database"],
        request.path_params["schema"],
    )
    app_state.require_current_session().put_control_request(
        PreviewSQLTablesRequest(
            engine=engine, database=database, schema=schema
        ),
        from_consumer_id=ConsumerId(app_state.require_current_session_id()),
    )
    return SuccessResponse()


@router.get(
    "/preview_sql_table_info/{engine:path}/{database:path}/{schema:path}/{table_name:path}"
)
@requires("edit")
async def preview_sql_table_info(request: Request) -> BaseResponse:
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
    responses:
        200:
            description: Get tables from the SQL database
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
    app_state.require_current_session().put_control_request(
        PreviewSQLTableInfoRequest(
            engine=engine,
            database=database,
            schema=schema,
            table_name=table_name,
        ),
        from_consumer_id=ConsumerId(app_state.require_current_session_id()),
    )
    return SuccessResponse()
