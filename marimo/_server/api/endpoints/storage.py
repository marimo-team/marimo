# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.authentication import requires

from marimo import _loggers
from marimo._server.api.utils import dispatch_control_request
from marimo._server.models.models import (
    BaseResponse,
    StorageDownloadRequest,
    StorageListEntriesRequest,
)
from marimo._server.router import APIRouter

if TYPE_CHECKING:
    from starlette.requests import Request

LOGGER = _loggers.marimo_logger()

router = APIRouter()


@router.post("/list_entries")
@requires("edit")
async def list_entries(request: Request) -> BaseResponse:
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
                    $ref: "#/components/schemas/StorageListEntriesRequest"
    responses:
        200:
            description: List storage entries at a prefix
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    return await dispatch_control_request(request, StorageListEntriesRequest)


@router.post("/download")
@requires("edit")
async def download(request: Request) -> BaseResponse:
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
                    $ref: "#/components/schemas/StorageDownloadRequest"
    responses:
        200:
            description: Download a storage entry
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    return await dispatch_control_request(request, StorageDownloadRequest)
