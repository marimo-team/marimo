# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import PlainTextResponse
from starlette.routing import Route, WebSocketRoute
from starlette.testclient import TestClient
from starlette.websockets import WebSocket, WebSocketDisconnect
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from marimo._server.api.middleware import WebSocketOriginMiddleware
from marimo._server.main import create_starlette_app
from tests._server.mocks import get_mock_session_manager


async def echo(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_text("connected")
    await websocket.close()


def make_client(allow_origins: tuple[str, ...] = ()) -> TestClient:
    return TestClient(
        Starlette(
            routes=[
                WebSocketRoute("/ws", echo),
                Route("/", lambda _: PlainTextResponse("ok")),
            ],
            middleware=[
                Middleware(
                    WebSocketOriginMiddleware, allow_origins=allow_origins
                )
            ],
        )
    )


@pytest.mark.parametrize(
    ("url", "origin"),
    [
        ("ws://localhost:2718/ws", "http://localhost:2718"),
        ("ws://127.0.0.1:2718/ws", "http://127.0.0.1:2718"),
        ("ws://[::1]:2718/ws", "http://[::1]:2718"),
        ("ws://example.com/ws", "http://example.com:80"),
        ("ws://example.com:80/ws", "http://example.com"),
        ("wss://example.com/ws", "https://example.com:443"),
        ("wss://example.com:443/ws", "https://example.com"),
        ("wss://example.com:8443/ws", "https://EXAMPLE.COM:8443"),
        ("ws://localhost:2718/ws", None),
    ],
)
def test_same_origin(url: str, origin: str | None) -> None:
    headers = {"Origin": origin} if origin is not None else {}
    with make_client().websocket_connect(url, headers=headers) as websocket:
        assert websocket.receive_text() == "connected"


@pytest.mark.parametrize(
    "origin",
    [
        "http://other.example",
        "http://localhost:8080",
        "http://127.0.0.1:2718",
        "https://localhost:2718",
        "http://localhost:2718.other.example",
        "http://localhost:2718@other.example",
        "http://other.example@localhost:2718",
        "http://localhost:2718/path",
        "http://localhost:2718?",
        "http://localhost:2718#",
        "http://localhost:invalid",
        "http://localhost:99999",
        "http://[::1",
        "http://local\\host:2718",
        "http://local\thost:2718",
        "http://localhost:2718 http://other.example",
        "http://localhost:2718,http://other.example",
        "ws://localhost:2718",
        "localhost",
        "null",
        "",
    ],
)
def test_other_or_invalid_origin(origin: str) -> None:
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with make_client().websocket_connect(
            "ws://localhost:2718/ws", headers={"Origin": origin}
        ):
            pytest.fail("Unexpected connection")
    assert (exc_info.value.code, exc_info.value.reason) == (
        1008,
        "Origin not allowed",
    )


@pytest.mark.parametrize("allow_origins", [(), ("*",)])
def test_duplicate_origin(allow_origins: tuple[str, ...]) -> None:
    client = make_client(allow_origins)
    client.headers = [("Origin", "http://testserver")] * 2
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws"):
            pytest.fail("Unexpected connection")
    assert exc_info.value.reason == "Origin not allowed"


@pytest.mark.parametrize("allow_origins", [(), ("*",)])
@pytest.mark.parametrize(
    "origin",
    [
        "null",
        "",
        "\x00http://[::1]",
        "http://[::1]\x7f",
        "http://[::1]:",
        "http://[::1]extra",
        "http://[::1]extra:80",
        "http://[::1]/",
        "http://[::1]?query",
        "http://[::1]#fragment",
        "http://user:password@[::1]",
    ],
)
def test_invalid_origin_with_configured_policy(
    allow_origins: tuple[str, ...], origin: str
) -> None:
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with make_client(allow_origins).websocket_connect(
            "ws://[::1]/ws", headers={"Origin": origin}
        ):
            pytest.fail("Unexpected connection")
    assert exc_info.value.reason == "Origin not allowed"


@pytest.mark.parametrize(
    "allow_origins", [("https://editor.example",), ("*",)]
)
def test_configured_origins(allow_origins: tuple[str, ...]) -> None:
    client = make_client(allow_origins)
    with client.websocket_connect(
        "/ws", headers={"Origin": "https://editor.example"}
    ) as websocket:
        assert websocket.receive_text() == "connected"
    with client.websocket_connect(
        "/ws", headers={"Origin": "http://testserver"}
    ) as websocket:
        assert websocket.receive_text() == "connected"


@pytest.mark.parametrize(
    "allow_origins", [("https://editor.example",), ("localhost",)]
)
def test_configured_origins_require_full_match(
    allow_origins: tuple[str, ...],
) -> None:
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with make_client(allow_origins).websocket_connect(
            "/ws", headers={"Origin": "https://editor.example:8443"}
        ):
            pytest.fail("Unexpected connection")
    assert exc_info.value.reason == "Origin not allowed"


def test_configured_origins_normalize_host_and_port() -> None:
    client = make_client(("https://EDITOR.example:443",))
    with client.websocket_connect(
        "/ws", headers={"Origin": "https://editor.example"}
    ) as websocket:
        assert websocket.receive_text() == "connected"


@pytest.mark.parametrize("host", ["localhost", "0.0.0.0", "::"])
def test_bound_host_does_not_allow_other_origins(host: str) -> None:
    app = create_starlette_app(base_url="", host=host, enable_auth=False)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with TestClient(app).websocket_connect(
            "ws://localhost:2718/ws",
            headers={"Origin": "http://localhost:8080"},
        ):
            pytest.fail("Unexpected connection")
    assert exc_info.value.reason == "Origin not allowed"


def test_http_and_lifespan_passthrough() -> None:
    with make_client() as client:
        response = client.get("/", headers={"Origin": "https://other.example"})
        assert response.text == "ok"


def test_trusted_proxy_scheme() -> None:
    client = TestClient(
        ProxyHeadersMiddleware(make_client().app, trusted_hosts=["testclient"])
    )
    with client.websocket_connect(
        "ws://127.0.0.1:2718/ws",
        headers={
            "Host": "example.com",
            "Origin": "https://example.com",
            "X-Forwarded-Proto": "https",
        },
    ) as websocket:
        assert websocket.receive_text() == "connected"


def test_forwarded_headers_are_not_used_directly() -> None:
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with make_client().websocket_connect(
            "ws://localhost:2718/ws",
            headers={
                "Origin": "https://other.example",
                "X-Forwarded-Proto": "https",
                "X-Forwarded-Host": "other.example",
            },
        ):
            pytest.fail("Unexpected connection")
    assert exc_info.value.reason == "Origin not allowed"


@pytest.mark.parametrize("enable_auth", [True, False])
@pytest.mark.parametrize("base_url", ["", "/notebook"])
@pytest.mark.parametrize(
    "path",
    [
        "/ws",
        "/ws_sync",
        "/terminal/ws",
        "/lsp/pylsp",
        "/api/marimo/v1/notebooks/test/events/ws",
    ],
)
def test_app_websocket_origins(
    enable_auth: bool, base_url: str, path: str
) -> None:
    app = create_starlette_app(
        base_url=base_url, enable_auth=enable_auth, skew_protection=False
    )
    app.state.session_manager = get_mock_session_manager()
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with TestClient(app).websocket_connect(
            f"{base_url}{path}?access_token=fake-token",
            headers={"Origin": "https://other.example"},
        ):
            pytest.fail("Unexpected connection")
    assert (exc_info.value.code, exc_info.value.reason) == (
        1008,
        "Origin not allowed",
    )


@pytest.mark.parametrize("enable_auth", [True, False])
@pytest.mark.parametrize(
    "allow_origins", [None, ("https://editor.example",), ("*",)]
)
def test_app_allowed_origins(
    enable_auth: bool, allow_origins: tuple[str, ...] | None
) -> None:
    app = create_starlette_app(
        base_url="", enable_auth=enable_auth, allow_origins=allow_origins
    )
    app.state.session_manager = get_mock_session_manager()
    app.router.routes.insert(0, WebSocketRoute("/echo", echo))
    origins = ["http://testserver"]
    if allow_origins:
        origins.append("https://editor.example")
    for origin in origins:
        with TestClient(app).websocket_connect(
            "/echo?access_token=fake-token", headers={"Origin": origin}
        ) as websocket:
            assert websocket.receive_text() == "connected"
