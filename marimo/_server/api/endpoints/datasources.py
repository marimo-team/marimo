# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.authentication import requires

from marimo import _loggers
from marimo._server.api.utils import dispatch_control_request
from marimo._server.models.models import (
    BaseResponse,
    ListDataSourceConnectionRequest,
    ListSQLTablesRequest,
    PreviewDatasetColumnRequest,
    PreviewSQLTableRequest,
)
from marimo._server.router import APIRouter

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
                    $ref: "#/components/schemas/PreviewDatasetColumnRequest"
    responses:
        200:
            description: Preview a column in a dataset
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    return await dispatch_control_request(request, PreviewDatasetColumnRequest)


@router.post("/preview_sql_table")
@requires("edit")
async def preview_sql_table(request: Request) -> BaseResponse:
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
                    $ref: "#/components/schemas/PreviewSQLTableRequest"
    responses:
        200:
            description: Preview a SQL table
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    return await dispatch_control_request(request, PreviewSQLTableRequest)


@router.post("/preview_sql_table_list")
@requires("edit")
async def preview_sql_table_list(request: Request) -> BaseResponse:
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
                    $ref: "#/components/schemas/ListSQLTablesRequest"
    responses:
        200:
            description: Preview a list of tables in an SQL schema
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    return await dispatch_control_request(request, ListSQLTablesRequest)


@router.post("/preview_datasource_connection")
@requires("edit")
async def preview_datasource_connection(request: Request) -> BaseResponse:
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
                    $ref: "#/components/schemas/ListDataSourceConnectionRequest"
    responses:
        200:
            description: Broadcasts a datasource connection
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    return await dispatch_control_request(
        request, ListDataSourceConnectionRequest
    )
