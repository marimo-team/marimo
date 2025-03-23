# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import io
import json
import sys
import time
from multiprocessing import Process
from typing import TYPE_CHECKING, Any

import pytest
import uvicorn
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Route
from starlette.testclient import TestClient
from starlette.websockets import WebSocket, WebSocketDisconnect
from uvicorn import Config, Server

from marimo._config.manager import MarimoConfigManager, UserConfigManager
from marimo._server.api.middleware import (
    ProxyMiddleware,
    _AsyncHTTPClient,
    _URLRequest,
)
from marimo._server.main import create_starlette_app
from marimo._server.model import SessionMode
from marimo._server.tokens import AuthToken
from marimo._server.utils import find_free_port
from tests._server.mocks import get_mock_session_manager, token_header

if TYPE_CHECKING:
    from pathlib import Path

    from starlette.requests import Request
    from starlette.types import ASGIApp, Receive, Scope, Send


def test_base_url() -> None:
    app = create_starlette_app(base_url="/foo")
    app.state.session_manager = get_mock_session_manager()
    app.state.config_manager = MarimoConfigManager(UserConfigManager())
    client = TestClient(app)

    # Mock out the server
    uvicorn_server = uvicorn.Server(uvicorn.Config(app))
    uvicorn_server.servers = []

    app.state.server = uvicorn_server
    app.state.host = "localhost"
    app.state.port = 1234
    app.state.base_url = "/foo"

    client = TestClient(app)

    # Infra routes
    response = client.get("/foo/health")
    assert response.status_code == 200, response.text
    response = client.get("/foo/healthz")
    assert response.status_code == 200, response.text
    response = client.get("/health")
    assert response.status_code == 404, response.text
    response = client.get("/healthz")
    assert response.status_code == 404, response.text

    # Index (requires auth)
    response = client.get("/foo/", headers=token_header("fake-token"))
    assert response.status_code == 200, response.text
    response = client.get("/")
    assert response.status_code == 404, response.text

    # Favicon, fails when missing base_url
    response = client.get("/foo/favicon.ico")
    assert response.status_code == 200, response.text
    response = client.get("/favicon.ico")
    assert response.status_code == 404, response.text

    # API, fails when missing base_url
    response = client.get("/foo/api/status")
    assert response.status_code == 200, response.text
    response = client.get("/api/status")
    assert response.status_code == 404, response.text


def test_skew_protection(edit_app: Starlette) -> None:
    client = TestClient(edit_app)
    # Unauthorized access
    response = client.get("/api/status")
    assert response.status_code == 401, response.text
    assert response.headers.get("Set-Cookie") is None

    # Authorized access
    response = client.get("/api/status", headers=token_header("fake-token"))
    assert response.status_code == 200, response.text
    assert response.headers.get("Set-Cookie") is not None

    # POST with a new passing skew protection token
    response = client.post(
        "/api/home/running_notebooks",
        headers=token_header("fake-token"),
    )
    assert response.status_code == 200, response.text

    # POST with a new skew protection token
    response = client.post(
        "/api/home/running_notebooks",
        headers=token_header("fake-token", "old-skew-id"),
    )
    assert response.status_code == 401, response.text


@pytest.fixture
def edit_app() -> Starlette:
    app = create_starlette_app(base_url="")
    app.state.session_manager = get_mock_session_manager()
    app.state.session_manager.mode = SessionMode.EDIT
    app.state.config_manager = MarimoConfigManager(UserConfigManager())
    # Mock out the server
    uvicorn_server = uvicorn.Server(uvicorn.Config(app))
    uvicorn_server.servers = []
    app.state.server = uvicorn_server
    app.state.host = "localhost"
    app.state.port = 1234
    app.state.base_url = ""
    return app


@pytest.fixture
def read_app() -> Starlette:
    app = create_starlette_app(base_url="")
    app.state.session_manager = get_mock_session_manager()
    app.state.session_manager.mode = SessionMode.RUN
    app.state.config_manager = MarimoConfigManager(UserConfigManager())
    # Mock out the server
    uvicorn_server = uvicorn.Server(uvicorn.Config(app))
    uvicorn_server.servers = []
    app.state.server = uvicorn_server
    app.state.host = "localhost"
    app.state.port = 1234
    app.state.base_url = ""
    return app


@pytest.fixture(params=["read_app", "edit_app"])
def app(request: Any) -> Starlette:
    return request.getfixturevalue(request.param)


@pytest.fixture
def no_auth_edit_app() -> Starlette:
    app = create_starlette_app(base_url="", enable_auth=False)
    app.state.session_manager = get_mock_session_manager()
    app.state.session_manager.mode = SessionMode.EDIT
    app.state.session_manager.auth_token = AuthToken("")  # no auth
    app.state.config_manager = MarimoConfigManager(UserConfigManager())
    # Mock out the server
    uvicorn_server = uvicorn.Server(uvicorn.Config(app))
    uvicorn_server.servers = []
    app.state.server = uvicorn_server
    app.state.host = "localhost"
    app.state.port = 1234
    app.state.base_url = ""
    return app


@pytest.fixture
def no_auth_read_app() -> Starlette:
    app = create_starlette_app(base_url="", enable_auth=False)
    app.state.session_manager = get_mock_session_manager()
    app.state.session_manager.mode = SessionMode.RUN
    app.state.session_manager.auth_token = AuthToken("")  # no auth
    app.state.config_manager = MarimoConfigManager(UserConfigManager())
    # Mock out the server
    uvicorn_server = uvicorn.Server(uvicorn.Config(app))
    uvicorn_server.servers = []
    app.state.server = uvicorn_server
    app.state.host = "localhost"
    app.state.port = 1234
    app.state.base_url = ""
    return app


@pytest.fixture(params=["no_auth_read_app", "no_auth_edit_app"])
def no_auth_app(request: Any) -> Starlette:
    return request.getfixturevalue(request.param)


class TestAuth:
    def test_no_auth_index_page(self, app: Starlette) -> None:
        # Test unauthorized access
        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200, response.text
        assert response.headers.get("Set-Cookie") is None
        assert "Login" in response.text

    def test_no_auth_api_route(self, app: Starlette) -> None:
        # Test unauthorized access
        client = TestClient(app)
        response = client.get("/api/status")
        assert response.status_code == 401, response.text
        assert response.headers.get("Set-Cookie") is None

    def test_auth_by_query(self, app: Starlette) -> None:
        # Test authorized access by auth_token in query
        client = TestClient(app)
        response = client.get("/?access_token=fake-token")
        assert response.status_code == 200, response.text
        assert response.headers.get("Set-Cookie") is not None

        # Can access again with cookie
        response = client.get("/")
        assert response.status_code == 200, response.text

    def tets_bath_auth_query(self, app: Starlette) -> None:
        # Test unauthorized access with bad auth token
        client = TestClient(app)
        response = client.get("/?access_token=bad-token")
        assert response.status_code == 401, response.text
        assert response.headers.get("Set-Cookie") is None

    def test_auth_by_header(self, app: Starlette) -> None:
        # Test authorized access by auth_token in header (basic auth login)
        client = TestClient(app)
        response = client.get("/", headers=token_header("fake-token"))
        assert response.status_code == 200, response.text
        assert response.headers.get("Set-Cookie") is not None

        # Can access again with cookie
        response = client.get("/")
        assert response.status_code == 200, response.text

    def test_bad_auth_header(self, app: Starlette) -> None:
        # Test unauthorized access with bad auth token
        client = TestClient(app)
        response = client.get("/api/status", headers=token_header("bad-token"))
        assert response.status_code == 401, response.text
        assert response.headers.get("Set-Cookie") is None


class TestNoAuth:
    def test_no_auth(self, no_auth_app: Starlette) -> None:
        client = TestClient(no_auth_app)
        response = client.get("/")
        assert response.status_code == 200, response.text
        assert response.headers.get("Set-Cookie") is None

    def tets_any_query(self, no_auth_app: Starlette) -> None:
        client = TestClient(no_auth_app)
        response = client.get("/?access_token=bad-token")
        assert response.status_code == 200, response.text
        assert response.headers.get("Set-Cookie") is None

    def test_any_header(self, no_auth_app: Starlette) -> None:
        client = TestClient(no_auth_app)
        response = client.get("/", headers=token_header("bad-token"))
        assert response.status_code == 200, response.text
        assert response.headers.get("Set-Cookie") is None


async def target_app(scope: Scope, receive: Receive, send: Send) -> None:
    if scope["type"] == "http":
        response = Response(
            json.dumps({"message": "response from proxied app"}),
            media_type="application/json",
        )
        await response(scope, receive, send)
    elif scope["type"] == "websocket":
        websocket = WebSocket(scope, receive=receive, send=send)
        await websocket.accept()
        try:
            while True:
                await websocket.receive_json()
                await websocket.send_json(
                    {"message": "ws response from proxied app"}
                )
        except WebSocketDisconnect:
            print("Client disconnected")
            return


def run_target_server():
    """Runs the target app with uvicorn."""
    config = Config(
        app=target_app, host="127.0.0.1", port=8765, log_level="info"
    )
    server = Server(config)
    server.run()


def run_mpl_server(host: str, port: int):
    """Runs the matplotlib plugin server.
    Defined at module level so it can be pickled."""
    from marimo._plugins.stateless.mpl._mpl import (
        create_application,  # Import here to avoid circular imports
    )

    app = create_application()
    app.state.host = host
    app.state.port = port
    app.state.secure = False
    config = Config(app=app, host=host, port=port, log_level="info")
    server = Server(config)
    server.run()


async def serve_static(request: Request) -> Response:
    del request
    content = "body { color: red; }"
    return Response(content=content, media_type="text/css")


async def serve_large_file(request: Request) -> Response:
    del request
    content = "x" * 1024 * 1024  # 1MB of 'x' characters
    return Response(content=content, media_type="text/plain")


target_static_app = Starlette(
    routes=[
        Route("/_static/css/page.css", serve_static),
        Route("/_static/large-file.txt", serve_large_file),
    ]
)


def run_static_server():
    """Runs the static file server with uvicorn."""
    config = Config(
        app=target_static_app, host="127.0.0.1", port=8766, log_level="info"
    )
    server = Server(config)
    server.run()


class TestProxyMiddleware:
    @pytest.fixture(scope="module")
    def target_server(self):
        """Start a separate `uvicorn` server for the target app."""
        process = Process(target=run_target_server, daemon=True)
        process.start()
        time.sleep(1)  # Ensure the server has started before tests run
        yield None
        process.terminate()
        process.join()

    @pytest.fixture
    def app_with_proxy(
        self, edit_app: Starlette, target_server: None
    ) -> ASGIApp:
        del target_server
        """Create the app with ProxyMiddleware targeting the running server."""
        edit_app.add_middleware(
            ProxyMiddleware,
            proxy_path="/proxy",
            target_url="http://127.0.0.1:8765",
        )
        return edit_app

    @pytest.fixture(scope="module")
    def mpl_server(self):
        """Start the matplotlib plugin server in a separate process."""
        host = "127.0.0.1"
        port = find_free_port(10_000)

        process = Process(
            target=run_mpl_server, args=(host, port), daemon=True
        )
        process.start()
        time.sleep(1)
        yield host, port
        process.terminate()
        process.join()

    @pytest.fixture
    def app_with_mpl_proxy(
        self, edit_app: Starlette, mpl_server: tuple[str, int]
    ) -> ASGIApp:
        """Create the app with ProxyMiddleware targeting the matplotlib plugin server."""
        host, port = mpl_server
        target_url = f"http://{host}:{port}"
        edit_app.add_middleware(
            ProxyMiddleware,
            proxy_path="/mpl",
            target_url=target_url,
        )
        return edit_app

    @pytest.fixture(scope="module")
    def static_server(self):
        """Start a separate server for static files."""
        process = Process(target=run_static_server, daemon=True)
        process.start()
        time.sleep(1)  # Ensure the server has started
        yield None
        process.terminate()
        process.join()

    @pytest.fixture
    def app_with_static_proxy(
        self, edit_app: Starlette, static_server: None, tmp_path: Path
    ) -> ASGIApp:
        del static_server
        """Create the app with ProxyMiddleware targeting the static server."""
        # Create test static files
        css_dir = tmp_path / "static" / "css"
        css_dir.mkdir(parents=True)
        css_file = css_dir / "page.css"
        css_file.write_text("body { color: red; }")

        large_file = tmp_path / "static" / "large-file.txt"
        large_file.write_text("x" * 1024 * 1024)  # 1MB file

        edit_app.add_middleware(
            ProxyMiddleware,
            proxy_path="/_static",
            target_url="http://127.0.0.1:8766",
        )
        return edit_app

    def test_proxy_static_file(self, app_with_static_proxy: Starlette) -> None:
        client = TestClient(app_with_static_proxy)
        response = client.get("/_static/css/page.css")
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("text/css")
        assert "body { color: red; }" in response.text

    def test_proxy_large_static_file(
        self, app_with_static_proxy: Starlette
    ) -> None:
        client = TestClient(app_with_static_proxy)
        response = client.get("/_static/large-file.txt")
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("text/plain")
        assert (
            len(response.content) == 1024 * 1024
        )  # Check full content length

    def test_proxy_static_file_streaming(
        self, app_with_static_proxy: Starlette
    ) -> None:
        client = TestClient(app_with_static_proxy)
        with client.stream("GET", "/_static/large-file.txt") as response:
            assert response.status_code == 200, response.text
            content_length = 0
            for chunk in response.iter_bytes():
                content_length += len(chunk)
            assert content_length == 1024 * 1024

    async def test_http_client_streaming(
        self, app_with_proxy: Starlette
    ) -> None:
        del app_with_proxy
        client = _AsyncHTTPClient(base_url="http://127.0.0.1:8765")

        request = _URLRequest(
            "http://127.0.0.1:8765/test",
            method="POST",
            headers={"Content-Type": "application/json"},
            data=b"test string",
        )
        response = await client.send(request, stream=True)
        assert response.status_code == 200
        chunks = [chunk async for chunk in response.aiter_raw()]
        assert len(chunks) > 0
        await response.aclose()

    async def test_http_client_body_types(
        self, app_with_proxy: Starlette
    ) -> None:
        del app_with_proxy
        client = _AsyncHTTPClient(base_url="http://127.0.0.1:8765")

        # Test with bytes data
        request = _URLRequest(
            "http://127.0.0.1:8765/test",
            method="POST",
            headers={"Content-Type": "application/json"},
            data=b'{"test": "data"}',
        )
        response = await client.send(request)
        assert response.status_code == 200
        await response.aclose()

        # Test with iterable of bytes using a file-like object
        class BytesBuffer(io.BytesIO):
            def read(self, size: int | None = -1) -> bytes:
                return super().read(size)

        buffer = BytesBuffer(b'{"test": "data"}')
        request = _URLRequest(
            "http://127.0.0.1:8765/test",
            method="POST",
            headers={"Content-Type": "application/json"},
            data=buffer,
        )
        response = await client.send(request)
        assert response.status_code == 200
        await response.aclose()

    async def test_http_client_headers(
        self, app_with_proxy: Starlette
    ) -> None:
        del app_with_proxy
        client = _AsyncHTTPClient(base_url="http://127.0.0.1:8765")

        custom_headers = {
            "X-Test-Header": "test-value",
            "Content-Type": "application/json",
        }
        request = _URLRequest(
            "http://127.0.0.1:8765/test",
            method="GET",
            headers=custom_headers,
            data=None,  # Explicitly set to None for GET request
        )
        response = await client.send(request)
        assert response.headers.get("content-type") == "application/json"
        await response.aclose()

    def test_http_client_url_building(self) -> None:
        client = _AsyncHTTPClient(base_url="http://127.0.0.1:8765")

        url = type(
            "URL", (), {"path": "/test/path", "query": b"param=value"}
        )()

        request = client.build_request("GET", url, headers={}, content=None)
        assert (
            request.full_url == "http://127.0.0.1:8765/test/path?param=value"
        )
        assert "host" in request.headers

    @pytest.mark.parametrize(
        ("method", "payload"),
        [
            ("GET", None),
            ("POST", {"data": "test"}),
        ],
    )
    def test_proxy_basic_http_functionality(
        self,
        app_with_proxy: Starlette,
        method: str,
        payload: dict[str, Any] | None,
    ) -> None:
        client = TestClient(app_with_proxy)
        response = client.request(
            method,
            "/proxy/api/test",
            headers=token_header("fake-token"),
            json=payload,
        )
        assert response.status_code == 200, response.text
        assert response.json()["message"] == "response from proxied app"

    def test_original_app_auth_still_works(
        self, app_with_proxy: Starlette
    ) -> None:
        client = TestClient(app_with_proxy)
        response = client.get("/api/status", headers=token_header("bad-token"))
        assert response.status_code == 401, response.text
        assert response.headers.get("Set-Cookie") is None

    async def test_proxy_websocket(self, app_with_proxy: Starlette) -> None:
        client = TestClient(app_with_proxy)
        with client.websocket_connect("/proxy/ws") as websocket:
            websocket.send_json({"message": "hello there"})
            response = websocket.receive_json()
            assert response["message"] == "ws response from proxied app"
            websocket.send_json({"message": "hello there again"})
            response_2 = websocket.receive_json()
            assert response_2["message"] == "ws response from proxied app"
            websocket.send_json({"message": "hello there again"})
            response_3 = websocket.receive_json()
            assert response_3["message"] == "ws response from proxied app"

    @pytest.mark.xfail(
        reason="Returning 403 instead of invalid ID message",
    )
    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Skipping test on Windows due to websocket issues",
    )
    def test_proxy_websocket_with_invalid_id(
        self, app_with_mpl_proxy: Starlette
    ) -> None:
        client = TestClient(app_with_mpl_proxy)
        with client.websocket_connect(
            "/mpl/ws?figure=invalid_id",
        ) as websocket:
            websocket.send_json({"type": "supports_binary", "value": True})
            message = websocket.receive_json()
            assert message["type"] == "error"
            assert "invalid" in message["message"].lower()

    # Could be good to go on to test the happy path for mpl but we're already doing that with the test client above so leaving just this invalid ID test for
