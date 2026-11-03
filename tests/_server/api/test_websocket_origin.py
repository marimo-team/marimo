# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock
from urllib.parse import urlsplit

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

if TYPE_CHECKING:
    from starlette.types import Message, Scope


async def echo(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_text("connected")
    await websocket.close()


def make_app(
    allow_origins: tuple[str, ...] = (), *, host: str | None = None
) -> Starlette:
    return Starlette(
        routes=[
            WebSocketRoute("/ws", echo),
            Route("/", lambda _: PlainTextResponse("ok")),
        ],
        middleware=[
            Middleware(
                WebSocketOriginMiddleware,
                allow_origins=allow_origins,
                host=host,
            )
        ],
    )


def make_client(
    allow_origins: tuple[str, ...] = (), *, host: str | None = None
) -> TestClient:
    return TestClient(make_app(allow_origins, host=host))


async def websocket_messages(
    app: Starlette, url: str, origin: str | None
) -> list[Message]:
    # Older supported Starlette TestClients cannot parse IPv6 URL authorities.
    parsed = urlsplit(url)
    headers = [(b"host", parsed.netloc.encode())]
    if origin is not None:
        headers.append((b"origin", origin.encode()))
    scope: Scope = {
        "type": "websocket",
        "scheme": parsed.scheme,
        "path": parsed.path,
        "root_path": "",
        "query_string": parsed.query.encode(),
        "headers": headers,
        "server": (
            parsed.hostname,
            parsed.port or (443 if parsed.scheme == "wss" else 80),
        ),
        "subprotocols": [],
    }
    messages: list[Message] = []

    async def send(message: Message) -> None:
        messages.append(message)

    await app(
        scope, AsyncMock(return_value={"type": "websocket.connect"}), send
    )
    return messages


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
async def test_same_origin(url: str, origin: str | None) -> None:
    messages = await websocket_messages(
        make_app(host="example.com"), url, origin
    )
    assert messages[0]["type"] == "websocket.accept"
    assert messages[1] == {"type": "websocket.send", "text": "connected"}


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
    client.headers = [("Origin", "http://localhost")] * 2
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("ws://localhost/ws"):
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
async def test_invalid_origin_with_configured_policy(
    allow_origins: tuple[str, ...], origin: str
) -> None:
    messages = await websocket_messages(
        make_app(allow_origins), "ws://[::1]/ws", origin
    )
    assert messages == [
        {
            "type": "websocket.close",
            "code": 1008,
            "reason": "Origin not allowed",
        }
    ]


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
        "ws://localhost/ws", headers={"Origin": "http://localhost"}
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


def test_invalid_configured_origins_warn_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        client = make_client(
            (
                "localhost",
                "https://editor.example/",
                "https://editor.example",
                "*",
            )
        )
        for _ in range(2):
            with client.websocket_connect(
                "/ws", headers={"Origin": "https://editor.example"}
            ) as websocket:
                assert websocket.receive_text() == "connected"
    assert [record.getMessage() for record in caplog.records] == [
        f"Ignoring invalid WebSocket origin {origin!r} in allow_origins. "
        "Use an http:// or https:// origin with an optional port, "
        "without a path or trailing slash."
        for origin in ("localhost", "https://editor.example/")
    ]


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


@pytest.mark.parametrize("host", [None, "localhost", "0.0.0.0", "::"])
@pytest.mark.parametrize("enable_auth", [True, False])
@pytest.mark.parametrize("request_host", ["other.example", "192.0.2.50"])
def test_matching_headers_require_a_configured_host(
    host: str | None, enable_auth: bool, request_host: str
) -> None:
    app = create_starlette_app(base_url="", host=host, enable_auth=enable_auth)
    app.state.session_manager = get_mock_session_manager()
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with TestClient(app).websocket_connect(
            "ws://127.0.0.1:2718/ws?access_token=fake-token",
            headers={
                "Host": f"{request_host}:2718",
                "Origin": f"http://{request_host}:2718",
            },
        ):
            pytest.fail("Unexpected connection")
    assert exc_info.value.reason == "Origin not allowed"


def test_configured_host_is_allowed() -> None:
    app = create_starlette_app(
        base_url="", host="EDITOR.EXAMPLE", enable_auth=False
    )
    app.state.session_manager = get_mock_session_manager()
    app.router.routes.insert(0, WebSocketRoute("/echo", echo))
    with TestClient(app).websocket_connect(
        "ws://127.0.0.1:2718/echo",
        headers={
            "Host": "editor.example:8080",
            "Origin": "http://editor.example:8080",
        },
    ) as websocket:
        assert websocket.receive_text() == "connected"


@pytest.mark.parametrize("host", ["192.0.2.10", "[2001:db8::1]"])
async def test_local_socket_address_is_allowed(host: str) -> None:
    messages = await websocket_messages(
        make_app(), f"ws://{host}:2718/ws", f"http://{host}:2718"
    )
    assert messages[0]["type"] == "websocket.accept"
    assert messages[1] == {"type": "websocket.send", "text": "connected"}


def test_socket_hostname_does_not_allow_other_origins() -> None:
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with make_client().websocket_connect(
            "ws://other.example/ws",
            headers={"Origin": "http://other.example"},
        ):
            pytest.fail("Unexpected connection")
    assert exc_info.value.reason == "Origin not allowed"


def test_rewritten_host_with_configured_origin() -> None:
    with make_client(("https://editor.example",)).websocket_connect(
        "ws://127.0.0.1:2718/ws",
        headers={
            "Host": "internal-upstream:2718",
            "Origin": "https://editor.example",
        },
    ) as websocket:
        assert websocket.receive_text() == "connected"


def test_http_and_lifespan_passthrough() -> None:
    with make_client() as client:
        response = client.get("/", headers={"Origin": "https://other.example"})
        assert response.text == "ok"


def test_trusted_proxy_scheme() -> None:
    client = TestClient(
        ProxyHeadersMiddleware(
            make_client(host="example.com").app, trusted_hosts=["testclient"]
        )
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
    origins = ["http://localhost"]
    if allow_origins:
        origins.append("https://editor.example")
    for origin in origins:
        with TestClient(app).websocket_connect(
            "ws://localhost/echo?access_token=fake-token",
            headers={"Origin": origin},
        ) as websocket:
            assert websocket.receive_text() == "connected"
