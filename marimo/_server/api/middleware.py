# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable
from dataclasses import dataclass
from http.client import HTTPResponse, HTTPSConnection
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Final,
    Optional,
    Union,
)
from urllib.parse import urljoin, urlparse

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
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.websockets import WebSocket, WebSocketState
from websockets import ConnectionClosed, connect

from marimo import _loggers
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._dependencies.dependencies import DependencyManager
from marimo._server.api.auth import validate_auth
from marimo._server.api.deps import AppState, AppStateBase
from marimo._server.model import SessionMode
from marimo._tracer import server_tracer

if TYPE_CHECKING:
    from starlette.requests import HTTPConnection
    from starlette.types import ASGIApp, Receive, Scope, Send

LOGGER = _loggers.marimo_logger()


class AuthBackend(AuthenticationBackend):
    def __init__(self, should_authenticate: bool = True) -> None:
        self.should_authenticate = should_authenticate

    async def authenticate(
        self, conn: HTTPConnection
    ) -> Optional[tuple[AuthCredentials, BaseUser]]:
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

        mode = AppStateBase(conn.app.state).session_manager.mode

        # User's get Read access in Run mode
        if mode == SessionMode.RUN:
            return AuthCredentials(["read"]), SimpleUser("user")

        # User's get Read and Edit access in Edit mode
        if mode == SessionMode.EDIT:
            return AuthCredentials(["read", "edit"]), SimpleUser("user")

        raise ValueError(f"Invalid session mode: {mode}")


class SkewProtectionMiddleware:
    HEADER_NAME: Final[str] = "Marimo-Server-Token"

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
        server_token = request.headers.get(self.HEADER_NAME)
        if server_token is None:
            LOGGER.warning(
                "Received request with no server token (skew protection token). "
                "This could mean the header is being stripped by a proxy. "
                "If you are running behind a proxy, please ensure the header "
                f"'{self.HEADER_NAME}' is being forwarded."
            )
            response = JSONResponse(
                {"error": "Missing server token"},
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
            return await response(scope, receive, send)

        if server_token != str(expected):
            LOGGER.warning(
                "Received request with invalid server token (skew protection token). "
                "This could mean the server has new code deployed but the client "
                "is still using an old version."
                f"Expected: {expected}, got: {server_token}"
            )
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


@dataclass
class _URLRequest:
    full_url: str
    method: str
    headers: dict[str, str]
    data: Any


class _AsyncHTTPResponse:
    def __init__(self, response: HTTPResponse):
        self.raw_response = response
        self.status_code = response.status
        self.headers = {k.lower(): v for k, v in response.getheaders()}

    async def aiter_raw(self) -> AsyncIterable[bytes]:
        try:
            while True:
                chunk = self.raw_response.read(8192)
                if not chunk:
                    break
                yield chunk
        except Exception:
            raise
        finally:
            await self.aclose()

    async def aclose(self) -> None:
        self.raw_response.close()


class _AsyncHTTPClient:
    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        parsed = urlparse(base_url)
        self.host = parsed.netloc
        self.is_https = parsed.scheme == "https"
        self.timeout = timeout

    def build_request(
        self, method: str, url: Any, headers: dict[str, str], content: Any
    ) -> _URLRequest:
        # Combine base_url with path and query to form a full URL
        full_url = f"{self.base_url}{url.path}"
        if hasattr(url, "query") and url.query:
            full_url += f"?{url.query.decode('utf-8')}"

        headers = dict(headers)
        headers["host"] = self.host

        request = _URLRequest(
            full_url,  # Use the full URL here
            method=method,
            headers=headers,
            data=content,
        )

        request.method = method
        return request

    async def _collect_body(self, request: _URLRequest) -> bytes:
        if not hasattr(request, "data") or request.data is None:
            return b""

        if isinstance(request.data, AsyncIterable):
            chunks: list[bytes] = []
            try:
                async for chunk in request.data:
                    if isinstance(chunk, str):
                        chunks.append(chunk.encode())
                    elif isinstance(chunk, bytes):
                        chunks.append(chunk)
                    else:
                        # Handle unexpected types
                        chunks.append(str(chunk).encode())
                return b"".join(chunks)
            except Exception as e:
                LOGGER.error(f"Error collecting async request body: {e}")
                raise
        if isinstance(request.data, str):
            return request.data.encode()
        if isinstance(request.data, bytes):
            return request.data
        if hasattr(request.data, "read"):
            return request.data.read()  # type: ignore

        raise ValueError(
            f"Unsupported request data type: {type(request.data)}"
        )

    def _send_request(self, request: _URLRequest, body: bytes) -> HTTPResponse:
        from http.client import HTTPConnection

        parsed_url = urlparse(request.full_url)
        path_and_query = parsed_url.path
        if parsed_url.query:
            path_and_query += f"?{parsed_url.query}"

        conn_class = HTTPSConnection if self.is_https else HTTPConnection
        conn = conn_class(self.host, timeout=self.timeout)

        method = request.method or "GET"

        try:
            conn.request(
                method=method,
                url=path_and_query,  # Only path and query
                body=body,
                headers=request.headers,
            )
            resp = conn.getresponse()
            return resp  # type: ignore[no-any-return]
        except Exception:
            raise

    async def send(
        self, request: _URLRequest, stream: bool = False, max_retries: int = 2
    ) -> _AsyncHTTPResponse:
        del stream
        loop = asyncio.get_event_loop()

        body = await self._collect_body(request)

        for attempt in range(max_retries + 1):
            try:
                response = await loop.run_in_executor(
                    None, lambda: self._send_request(request, body)
                )
                return _AsyncHTTPResponse(response)
            except (ConnectionError, TimeoutError) as e:
                if attempt < max_retries:
                    # Exponential backoff
                    wait_time = 0.1 * (2**attempt)
                    LOGGER.warning(
                        f"Connection attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    LOGGER.error(f"All connection attempts failed: {e}")
                    raise

        raise ValueError("Failed to send request")


class ProxyMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        proxy_path: str,
        target_url: Union[str, Callable[[str], str]],
        path_rewrite: Callable[[str], str] | None = None,
    ) -> None:
        self.app = app
        self.path = proxy_path.rstrip("/")
        self.target_url = target_url
        self.path_rewrite = path_rewrite

    def _get_target_url(self, path: str) -> str:
        """Get target URL either from rewrite function or default MPL logic."""
        if callable(self.target_url):
            return self.target_url(path)

        return self.target_url

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] == "websocket":
            if not scope["path"].startswith(self.path):
                return await self.app(scope, receive, send)

            ws_target_url = self._get_target_url(scope["path"])
            ws_path = scope["path"]
            if self.path_rewrite:
                ws_path = self.path_rewrite(ws_path)
            ws_url = urljoin(ws_target_url, ws_path)
            if ws_url.startswith("http"):
                # http -> ws
                # https -> wss
                ws_url = ws_url.replace("http", "ws", 1)

            LOGGER.debug(f"Creating websocket proxy for {ws_url}")
            try:
                await self._proxy_websocket(scope, receive, send, ws_url)
            except Exception as e:
                LOGGER.error(f"Error proxying websocket: {e}")
            LOGGER.debug(f"Done with websocket proxy for {ws_url}")
            return

        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope, receive)
        if not scope["path"].startswith(self.path):
            await self.app(scope, receive, send)
            return

        target_base = self._get_target_url(request.url.path)
        # Remove proxy path prefix for proxied request
        target_path = request.url.path
        if self.path_rewrite:
            target_path = self.path_rewrite(target_path)
        target_query = request.url.query.encode("utf-8")

        # Create client if needed (for dynamic target URLs)
        client = _AsyncHTTPClient(base_url=target_base)

        # Construct the URL object with path and query
        url = type("URL", (), {"path": target_path, "query": target_query})()

        headers = {k.decode(): v.decode() for k, v in request.headers.raw}

        rp_req = client.build_request(
            request.method,
            url,
            headers=headers,
            content=request.stream(),
        )

        rp_resp = await client.send(rp_req, stream=True)
        response = StreamingResponse(
            rp_resp.aiter_raw(),
            status_code=rp_resp.status_code,
            headers=rp_resp.headers,
            background=BackgroundTask(rp_resp.aclose),
        )
        await response(scope, receive, send)

    async def _proxy_websocket(
        self, scope: Scope, receive: Receive, send: Send, ws_url: str
    ) -> None:
        websocket = WebSocket(scope, receive=receive, send=send)
        try:
            original_params = websocket.query_params
            if original_params:
                ws_url = f"{ws_url}?{'&'.join(f'{k}={v}' for k, v in original_params.items())}"
            await websocket.accept()

            async with connect(ws_url) as ws_client:

                async def client_to_upstream() -> None:
                    try:
                        while True:
                            msg = await websocket.receive()
                            if msg["type"] == "websocket.disconnect":
                                # Cancel the other task when client disconnects
                                for task in relay_tasks:
                                    if not task.done():
                                        task.cancel()
                                return

                            if "text" in msg:
                                await ws_client.send(msg["text"])
                            elif "bytes" in msg:
                                await ws_client.send(msg["bytes"])
                    except Exception as e:
                        LOGGER.error(f"Client to upstream relay error: {e}")
                        # Cancel other tasks only if this is a fatal error
                        for task in relay_tasks:
                            if not task.done():
                                task.cancel()

                async def upstream_to_client() -> None:
                    try:
                        while True:
                            msg = await ws_client.recv()
                            if isinstance(msg, bytes):
                                await websocket.send_bytes(msg)
                            else:
                                await websocket.send_text(msg)
                    except ConnectionClosed:
                        # Cancel the other task when connection closes
                        for task in relay_tasks:
                            if not task.done():
                                task.cancel()
                        return
                    except Exception:
                        return

                # Run both relay loops concurrently
                relay_tasks = [
                    asyncio.create_task(client_to_upstream()),
                    asyncio.create_task(upstream_to_client()),
                ]

                try:
                    await asyncio.gather(*relay_tasks)
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    raise e
                finally:
                    for task in relay_tasks:
                        if not task.done():
                            task.cancel()
                    if websocket.client_state != WebSocketState.DISCONNECTED:
                        await websocket.close()
                    await ws_client.close()
        except Exception as e:
            LOGGER.error(f"WebSocket proxy error: {e}")
            if websocket.client_state != WebSocketState.DISCONNECTED:
                await websocket.close(code=1011)  # Internal error
            raise
