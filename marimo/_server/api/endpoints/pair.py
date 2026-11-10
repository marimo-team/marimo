# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec
from starlette.authentication import requires
from starlette.responses import Response

from marimo._messaging.agents import (
    AgentContextUnavailableError,
    AgentError,
    AgentInfo,
    ConnectionSubscriptionRequest,
    MessageError,
    MessageRequest,
    NoAgentsConnectedError,
    SendResult,
)
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_request
from marimo._server.router import APIRouter
from marimo._utils.http import HTTPException, HTTPStatus

if TYPE_CHECKING:
    from starlette.requests import Request

    from marimo._core.notebook import Notebook
    from marimo._server.host.agents import AgentMessaging
    from marimo._session.session import Session

pair_router = APIRouter()


def _message_error(status: int, error: MessageError) -> Response:
    return Response(
        msgspec.json.encode(error),
        status_code=status,
        media_type="application/json",
    )


def _messaging_session(
    request: Request,
) -> tuple[AppState, Session] | Response:
    state = AppState(request)
    try:
        session = state.session_by_stable_id(request.path_params["id"])
    except HTTPException as error:
        return _message_error(
            error.status_code,
            MessageError(
                "unavailable", error.detail or "Notebook unavailable"
            ),
        )
    return state, session


def _messaging_target(
    state: AppState, session: Session
) -> tuple[Notebook, AgentMessaging] | Response:
    notebook = state.notebook_for_session(session)
    context = state.host_context
    if notebook is None or context is None:
        return _message_error(
            409, MessageError("unavailable", "Agent messaging is unavailable")
        )
    return notebook, context.agents


@pair_router.post("/notebooks/{id}/messages", include_in_schema=False)
@requires("edit")
async def messages(request: Request) -> SendResult | Response:
    """Send producer content to an explicit agent or a broadcast snapshot."""
    resolved_session = _messaging_session(request)
    if isinstance(resolved_session, Response):
        return resolved_session
    try:
        body = await parse_request(request, MessageRequest)
        if body.broadcast == (body.to is not None):
            raise ValueError("Select one recipient or explicit broadcast")
    except (msgspec.DecodeError, ValueError):
        return _message_error(
            400,
            MessageError("invalid-argument", "Invalid agent message request."),
        )

    target = _messaging_target(*resolved_session)
    if isinstance(target, Response):
        return target
    notebook, messaging = target
    try:
        if body.broadcast:
            result = await messaging.broadcast(
                notebook, body.message, timeout=body.timeout
            )
        else:
            assert body.to is not None
            result = await messaging.send(
                notebook, body.message, to=body.to, timeout=body.timeout
            )
    except (TypeError, ValueError) as error:
        return _message_error(
            400, MessageError("invalid-argument", str(error))
        )
    except NoAgentsConnectedError as error:
        return _message_error(409, MessageError("no-agents", str(error)))
    except AgentContextUnavailableError as error:
        return _message_error(409, MessageError("unavailable", str(error)))
    except AgentError as error:
        return _message_error(503, MessageError("failed", str(error)))
    return result


@pair_router.get("/notebooks/{id}/agents", include_in_schema=False)
@requires("edit")
async def agents(request: Request) -> tuple[AgentInfo, ...] | Response:
    """List logical recipients from the Notebook's current attachments."""
    resolved_session = _messaging_session(request)
    if isinstance(resolved_session, Response):
        return resolved_session
    target = _messaging_target(*resolved_session)
    if isinstance(target, Response):
        return target
    notebook, messaging = target
    return messaging.list(notebook)


@pair_router.post(
    "/notebooks/{id}/agents/subscriptions", include_in_schema=False
)
@requires("edit")
async def agent_subscription(request: Request) -> Response:
    """Register a private function callback for the current kernel only."""
    resolved = _messaging_session(request)
    if isinstance(resolved, Response):
        return resolved
    state, session = resolved
    target = _messaging_target(state, session)
    if isinstance(target, Response):
        return target
    try:
        body = await parse_request(request, ConnectionSubscriptionRequest)
        if len(body.subscription_id) != 32 or any(
            c not in "0123456789abcdef" for c in body.subscription_id
        ):
            raise ValueError("Invalid subscription ID")
    except (msgspec.DecodeError, ValueError):
        return _message_error(
            400, MessageError("invalid-argument", "Invalid subscription")
        )
    notebook, _ = target
    if notebook.runtime is None or notebook.runtime.status not in {
        "starting",
        "running",
    }:
        return _message_error(
            409, MessageError("unavailable", "The kernel is no longer active")
        )
    assert state.host_context is not None
    connections = state.host_context.bridge.agent_connections
    if body.active:
        try:
            connections.subscribe(notebook, session, body.subscription_id)
        except ValueError as error:
            return _message_error(409, MessageError("failed", str(error)))
    else:
        connections.unsubscribe(session, body.subscription_id)
    return Response(b"{}", media_type="application/json")


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
        body = await parse_request(request, DetachRequest)
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
