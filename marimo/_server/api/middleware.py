# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Optional
from urllib.parse import urljoin

import httpx
import starlette.status as status
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    BaseUser,
    SimpleUser,
)
from starlette.background import BackgroundTask
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    DispatchFunction,
    RequestResponseEndpoint,
)
from starlette.requests import HTTPConnection, Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.websockets import WebSocket
from websockets import ConnectionClosed
from websockets.client import connect

from marimo._config.settings import GLOBAL_SETTINGS
from marimo._dependencies.dependencies import DependencyManager
from marimo._server.api.auth import validate_auth
from marimo._server.api.deps import AppState, AppStateBase
from marimo._server.model import SessionMode
from marimo._tracer import server_tracer

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


class OpenTelemetryMiddleware(BaseHTTPMiddleware):
    def __init__(
        self, app: ASGIApp, dispatch: DispatchFunction | None = None
    ) -> None:
        super().__init__(app, dispatch)

        if not GLOBAL_SETTINGS.TRACING:
            return

        DependencyManager.opentelemetry.require("for tracing.")

        # Import once and store for later
        from opentelemetry import trace
        from opentelemetry.trace.status import Status, StatusCode

        self.trace = trace
        self.Status = Status
        self.StatusCode = StatusCode

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if not GLOBAL_SETTINGS.TRACING:
            return await call_next(request)

        with server_tracer.start_as_current_span(
            f"{request.method} {request.url.path}",
            kind=self.trace.SpanKind.SERVER,
            attributes={
                "http.method": request.method,
                "http.target": request.url.path or "",
            },
        ) as span:
            try:
                response = await call_next(request)
                span.set_attribute("http.status_code", response.status_code)
                span.set_status(self.Status(self.StatusCode.OK))
            except Exception as e:
                span.set_status(self.Status(self.StatusCode.ERROR, str(e)))
                raise
            return response


class ProxyMiddleware:
    def __init__(self, app: ASGIApp, proxy_path: str, target_url: str) -> None:
        self.app = app
        self.path = proxy_path.rstrip("/")
        self.target = target_url.rstrip("/")
        self.client = httpx.AsyncClient(base_url=self.target)

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] == "websocket":
            if not scope["path"].startswith(self.path):
                return await self.app(scope, receive, send)

            # Connect to target websocket
            ws_url = urljoin(self.target, scope["path"])
            if scope["scheme"] in ("http", "ws"):
                ws_url = ws_url.replace("http", "ws", 1)
            elif scope["scheme"] in ("https", "wss"):
                ws_url = ws_url.replace("https", "wss", 1)

            await self._proxy_websocket(scope, receive, send, ws_url)
            return

        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope, receive)
        if not scope["path"].startswith(self.path):
            await self.app(scope, receive, send)
            return

        url = httpx.URL(
            path=request.url.path, query=request.url.query.encode("utf-8")
        )
        rp_req = self.client.build_request(
            request.method,
            url,
            headers=request.headers.raw,
            content=request.stream(),
        )
        rp_resp = await self.client.send(rp_req, stream=True)
        response = StreamingResponse(
            rp_resp.aiter_raw(),
            status_code=rp_resp.status_code,
            headers=rp_resp.headers,
            background=BackgroundTask(rp_resp.aclose),
        )

        await response(scope, receive, send)

    # TODO: this does not work, but the correct answer probably lies
    # in here: https://github.com/valohai/asgiproxy/blob/master/asgiproxy/proxies/websocket.py
    async def _proxy_websocket(
        self, scope: Scope, receive: Receive, send: Send, ws_url: str
    ) -> None:
        websocket = WebSocket(scope, receive=receive, send=send)
        await websocket.accept()

        print("[debug] CONNECTING TO", ws_url)
        async with connect(ws_url) as ws_client:

            async def client_to_upstream() -> None:
                try:
                    while True:
                        msg = await websocket.receive()
                        if msg["type"] == "websocket.disconnect":
                            return

                        if "text" in msg:
                            await ws_client.send(msg["text"])
                        elif "bytes" in msg:
                            await ws_client.send(msg["bytes"])
                except ConnectionClosed as e:
                    await websocket.close()
                    print("[debug] CLIENT CLOSED", e)
                    return

            async def upstream_to_client() -> None:
                try:
                    while True:
                        msg = await ws_client.recv()
                        if isinstance(msg, bytes):
                            await websocket.send_bytes(msg)
                        else:
                            await websocket.send_text(msg)
                except ConnectionClosed as e:
                    await websocket.close()
                    print("[debug] UPSTREAM CLOSED", e)
                    return

            # Run both relay loops concurrently
            relay_tasks = [
                asyncio.create_task(client_to_upstream()),
                asyncio.create_task(upstream_to_client()),
            ]

            try:
                # Wait for either task to complete
                done, pending = await asyncio.wait(
                    relay_tasks, return_when=asyncio.FIRST_COMPLETED
                )

                # Cancel pending tasks
                for task in pending:
                    task.cancel()

                # Check for exceptions
                for task in done:
                    try:
                        task.result()
                    except Exception:
                        pass

            finally:
                # Ensure websocket is closed
                try:
                    await websocket.close()
                except Exception:
                    pass
