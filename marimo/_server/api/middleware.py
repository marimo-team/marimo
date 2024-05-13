# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import starlette.status as status
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    BaseUser,
    SimpleUser,
)
from starlette.requests import HTTPConnection, Request
from starlette.responses import JSONResponse

from marimo._server.api.auth import validate_auth
from marimo._server.api.deps import AppState, AppStateBase
from marimo._server.model import SessionMode

if TYPE_CHECKING:
    from starlette.requests import HTTPConnection
    from starlette.types import ASGIApp, Receive, Scope, Send


class AuthBackend(AuthenticationBackend):
    def __init__(self, should_authenticate: bool = True) -> None:
        self.should_authenticate = should_authenticate

    async def authenticate(
        self, conn: HTTPConnection
    ) -> Optional[tuple["AuthCredentials", "BaseUser"]]:
        mode = AppStateBase(conn.app.state).session_manager.mode

        # We may not need to authenticate. This can be disabled
        # because the user is running in a trusted environment
        # or authentication is handled by a layer above us
        if self.should_authenticate:
            # Valid auth header
            # This validates we have a valid Cookie (already authenticated)
            # or validates our auth (and sets the cookie)
            valid = validate_auth(conn)
            if not valid:
                return None

        # User's get Read access in Run mode
        if mode == SessionMode.RUN:
            return AuthCredentials(["read"]), SimpleUser("user")

        # User's get Read and Edit access in Edit mode
        if mode == SessionMode.EDIT:
            return AuthCredentials(["read", "edit"]), SimpleUser("user")

        raise ValueError(f"Invalid session mode: {mode}")


class SkewProtectionMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope)
        state = AppState.from_app(request.app)

        # If not POST request, then skip
        if request.method != "POST":
            return await self.app(scope, receive, send)
        # If is a form, then skip
        if request.headers.get("Content-Type", "").startswith(
            "application/x-www-form-urlencoded"
        ):
            return await self.app(scope, receive, send)
        # If ws, skip
        if request.url.path.startswith("/ws") or request.url.path.endswith(
            "/ws"
        ):
            return await self.app(scope, receive, send)

        expected = state.session_manager.skew_protection_token
        server_token = request.headers.get("Marimo-Server-Token")
        if server_token != str(expected):
            response = JSONResponse(
                {"error": "Invalid server token"},
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
            return await response(scope, receive, send)

        # Passed
        return await self.app(scope, receive, send)
