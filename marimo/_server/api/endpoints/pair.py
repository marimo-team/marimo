# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec
from starlette.authentication import requires
from starlette.responses import Response

from marimo._messaging.messages import AGENT_MESSAGE_TYPE
from marimo._server.api.deps import AppState
from marimo._server.router import APIRouter
from marimo._utils.http import HTTPException, HTTPStatus

if TYPE_CHECKING:
    from starlette.requests import Request

pair_router = APIRouter()


@pair_router.post("/notebooks/{id}/messages", include_in_schema=False)
@requires("edit")
async def messages(request: Request) -> Response:
    """Send any JSON content to all agents attached to the notebook."""
    state = AppState(request)
    session = state.session_by_stable_id(request.path_params["id"])
    try:
        payload = msgspec.json.decode(await request.body())
    except msgspec.DecodeError as error:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Invalid JSON agent message payload.",
        ) from error

    notebook = state.notebook_for_session(session)
    if notebook is None or not any(
        a.kind == "agent" for a in notebook.attachments
    ):
        raise HTTPException(status_code=409, detail="No agent attached")
    notebook.emit(AGENT_MESSAGE_TYPE, payload)
    return Response(status_code=202)


class DetachRequest(msgspec.Struct):
    """Select a host attachment to remove without stopping its notebook runtime."""

    attachment_id: str


@pair_router.post(
    "/notebooks/{id}/attachments/detach", include_in_schema=False
)
@requires("edit")
async def detach(request: Request) -> Response:
    """Disconnect one attachment without stopping its notebook runtime."""
    state = AppState(request)
    session = state.session_by_stable_id(request.path_params["id"])
    try:
        body = msgspec.json.decode(await request.body(), type=DetachRequest)
        if not body.attachment_id:
            raise ValueError("Empty attachment ID")
    except (msgspec.DecodeError, ValueError) as error:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Invalid attachment ID.",
        ) from error
    notebook = state.notebook_for_session(session)
    if notebook is not None:
        notebook.detach(body.attachment_id)
    return Response(status_code=204)
