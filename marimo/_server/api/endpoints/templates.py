# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.authentication import requires
from starlette.responses import FileResponse

from marimo._server.api.deps import AppState
from marimo._server.models.templates import (
    TemplateCatalogResponse,
    TemplateCategory,
    TemplateLaunchResponse,
    TemplateSummary,
)
from marimo._server.router import APIRouter
from marimo._template_catalog import TemplateNotFoundError
from marimo._utils.http import HTTPException, HTTPStatus

if TYPE_CHECKING:
    from starlette.requests import Request

router = APIRouter()


@router.get("/")
@requires("edit")
async def list_templates(*, request: Request) -> TemplateCatalogResponse:
    """
    responses:
        200:
            description: List bundled templates
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/TemplateCatalogResponse"
    """
    app_state = AppState(request)
    catalog = app_state.session_manager.templates.catalog
    base_url = app_state.base_url.rstrip("/")
    return TemplateCatalogResponse(
        categories=[
            TemplateCategory(
                id=category.id,
                title=category.title,
                description=category.description,
            )
            for category in catalog.categories
        ],
        templates=[
            TemplateSummary(
                id=entry.id,
                title=entry.title,
                description=entry.description,
                category_ids=list(entry.category_ids),
                preview_url=(f"{base_url}/api/templates/{entry.id}/preview"),
            )
            for entry in catalog.entries
        ],
        featured_ids=list(catalog.featured_ids),
    )


@router.get("/{template_id}/preview")
@requires("edit")
async def template_preview(*, request: Request) -> FileResponse:
    """
    parameters:
        - in: path
          name: template_id
          schema:
              type: string
          required: true
    responses:
        200:
            description: Read a bundled template preview
            content:
                image/png:
                    schema:
                        type: string
                        format: binary
        404:
            description: Template not found
    """
    template_id = str(request.path_params["template_id"])
    try:
        entry = AppState(request).session_manager.templates.catalog.get(
            template_id
        )
    except TemplateNotFoundError as error:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Template {template_id!r} not found",
        ) from error
    return FileResponse(
        entry.preview_path,
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.post("/{template_id}/launch")
@requires("edit")
async def launch_template(*, request: Request) -> TemplateLaunchResponse:
    """
    parameters:
        - in: path
          name: template_id
          schema:
              type: string
          required: true
    responses:
        200:
            description: Create an unnamed template launch
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/TemplateLaunchResponse"
        404:
            description: Template not found
    """
    template_id = str(request.path_params["template_id"])
    try:
        file_key = AppState(request).session_manager.templates.create_launch(
            template_id
        )
    except TemplateNotFoundError as error:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Template {template_id!r} not found",
        ) from error
    return TemplateLaunchResponse(file_key=file_key)
