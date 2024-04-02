# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Optional

from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    BaseUser,
    SimpleUser,
)
from starlette.requests import HTTPConnection, Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from marimo._server.model import SessionMode


class AuthBackend(AuthenticationBackend):
    async def authenticate(
        self, conn: HTTPConnection
    ) -> Optional[tuple["AuthCredentials", "BaseUser"]]:
        mode = conn.app.state.session_manager.mode
        if mode is None:
            return None
        if mode == SessionMode.RUN:
            return AuthCredentials(["read"]), SimpleUser("user")
        elif mode == SessionMode.EDIT:
            return AuthCredentials(["read", "edit"]), SimpleUser("user")
        return None


class ValidateServerTokensMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope)

        # If not POST request, then skip
        if request.method != "POST":
            return await self.app(scope, receive, send)
        # If ws, skip
        if request.url.path.startswith("/ws") or request.url.path.endswith(
            "/ws"
        ):
            return await self.app(scope, receive, send)

        expected_server_token = request.app.state.session_manager.server_token
        if expected_server_token is None:
            return await self.app(scope, receive, send)

        server_token = request.headers.get("Marimo-Server-Token")
        if server_token != expected_server_token:
            response = JSONResponse(
                {"error": "Invalid server token"}, status_code=401
            )
            return await response(scope, receive, send)

        # Passed
        return await self.app(scope, receive, send)
