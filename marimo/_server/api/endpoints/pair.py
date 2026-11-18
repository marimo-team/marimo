# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec
from starlette.authentication import requires
from starlette.responses import Response

from marimo._messaging.agents import (
    ConnectionSubscriptionRequest,
    MessageRequest,
)
from marimo._server.api.deps import AppState
from marimo._server.router import APIRouter
from marimo._utils.http import HTTPException, HTTPStatus

if TYPE_CHECKING:
    from starlette.requests import Request

    from marimo._core.notebook import Notebook
    from marimo._server.host.agents import AgentMessaging

pair_router = APIRouter()


def _messaging_target(request: Request) -> tuple[Notebook, AgentMessaging]:
    state = AppState(request)
    session = state.session_by_stable_id(request.path_params["id"])
    notebook = state.notebook_for_session(session)
    if notebook is None or state.host_context is None:
        raise HTTPException(status_code=409, detail="Notebook unavailable")
    return notebook, state.host_context.agents


@pair_router.post("/notebooks/{id}/messages", include_in_schema=False)
@requires("edit")
async def messages(request: Request) -> Response:
    """Send any JSON content to all agents attached to the notebook."""
    notebook, messaging = _messaging_target(request)
    try:
        # Do not cache raw content while the call waits for submission reports.
        result = await messaging.send(
            notebook,
            msgspec.json.decode(
                b"".join([chunk async for chunk in request.stream()]),
                type=MessageRequest,
            ),
        )
    except (msgspec.DecodeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return Response(msgspec.json.encode(result), media_type="application/json")


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


@pair_router.get("/notebooks/{id}/agents", include_in_schema=False)
@requires("edit")
async def agents(request: Request) -> Response:
    """List the logical agents that can receive messages."""
    notebook, messaging = _messaging_target(request)
    listing = messaging.list(notebook)
    return Response(
        msgspec.json.encode(listing), media_type="application/json"
    )


@pair_router.post(
    "/notebooks/{id}/agents/subscriptions", include_in_schema=False
)
@requires("edit")
async def subscriptions(request: Request) -> Response:
    """Register a connection callback for the current Session."""
    notebook, messaging = _messaging_target(request)
    session = AppState(request).session_by_stable_id(request.path_params["id"])
    try:
        body = msgspec.json.decode(
            await request.body(), type=ConnectionSubscriptionRequest
        )
        if len(body.subscription_id) != 32 or any(
            c not in "0123456789abcdef" for c in body.subscription_id
        ):
            raise ValueError("Invalid subscription ID")
        if notebook.runtime is None or notebook.runtime.status not in {
            "starting",
            "running",
        }:
            raise HTTPException(
                status_code=409, detail="The kernel is no longer active"
            )
        if body.active:
            messaging.connections.subscribe(
                notebook, session, body.subscription_id
            )
        else:
            messaging.connections.unsubscribe(session, body.subscription_id)
    except (msgspec.DecodeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return Response(b"{}", media_type="application/json")
