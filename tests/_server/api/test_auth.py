from __future__ import annotations

import asyncio
import base64
import os
import subprocess
import sys
from http.cookiejar import CookieJar
from http.cookies import SimpleCookie
from typing import TYPE_CHECKING, Any

import pytest
from starlette.applications import Starlette
from starlette.authentication import SimpleUser, requires
from starlette.datastructures import Headers, QueryParams
from starlette.requests import HTTPConnection
from starlette.responses import JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.testclient import TestClient

from marimo._config.manager import MarimoConfigManager, UserConfigManager
from marimo._server.api.auth import (
    CookieSession,
    CustomAuthenticationMiddleware,
    CustomSessionMiddleware,
    hash_access_token,
    validate_auth,
)
from marimo._server.api.deps import AppState
from marimo._server.api.middleware import AuthBackend
from marimo._server.config import StarletteServerStateInit
from marimo._server.main import create_starlette_app
from marimo._server.tokens import AuthToken
from tests._server.mocks import (
    get_mock_session_manager,
    get_starlette_server_state_init,
)

if TYPE_CHECKING:
    from starlette.types import Message, Receive, Scope, Send
    from starlette.websockets import WebSocket


async def mock_receive() -> Any:
    return {
        "type": "http.disconnect",
    }


async def mock_send(message: Any) -> None:
    del message


@pytest.mark.parametrize(
    ("port", "host", "scheme", "base_url", "expected_name", "expected_path"),
    [
        (1234, None, "http", "", "session_1234", "/"),
        (None, None, "http", "", "session", "/"),
        (2718, "localhost:2718", "http", "", "session_2718", "/"),
        (2718, "localhost:2720", "http", "", "session_2720", "/"),
        (2718, "[::1]:2720", "http", "", "session_2720", "/"),
        (2718, "localhost", "http", "", "session_80", "/"),
        (2718, "localhost", "https", "", "session_443", "/"),
        (1234, None, "http", "/marimo1", "session_1234_marimo1", "/marimo1"),
        (
            1234,
            None,
            "http",
            "/apps/ml/notebook",
            "session_1234_apps_ml_notebook",
            "/apps/ml/notebook",
        ),
        (
            2718,
            "localhost:2720",
            "http",
            "/marimo1",
            "session_2720_marimo1",
            "/marimo1",
        ),
    ],
)
async def test_custom_session_middleware_cookie_scope(
    port: int | None,
    host: str | None,
    scheme: str,
    base_url: str,
    expected_name: str,
    expected_path: str,
):
    async def set_session(scope: Scope, receive: Receive, send: Send):
        scope["session"]["value"] = "test"
        await JSONResponse({})(scope, receive, send)

    app = _app_with_base_url(base_url)
    app.state.port = port
    middleware = CustomSessionMiddleware(set_session, "secret_key")
    scope = create_connection(app).scope
    scope["scheme"] = scheme
    if host is not None:
        scope["headers"] = [(b"host", host.encode())]
    messages: list[Message] = []

    async def capture(message: Message):
        messages.append(message)

    await middleware(scope, mock_receive, capture)
    cookie = SimpleCookie(Headers(scope=messages[0])["set-cookie"])
    assert list(cookie) == [expected_name]
    assert cookie[expected_name]["path"] == expected_path


def test_custom_session_middleware_secure_flag_default(app: Starlette):
    # By default the session cookie is not marked Secure so it works over
    # plain HTTP during local development.
    middleware = CustomSessionMiddleware(app, "secret_key")
    assert "secure" not in middleware.security_flags


def test_custom_session_middleware_secure_flag_enabled(app: Starlette):
    # https_only=True (wired from MARIMO_SESSION_COOKIE_SECURE) marks the
    # session cookie as Secure.
    middleware = CustomSessionMiddleware(app, "secret_key", https_only=True)
    assert "secure" in middleware.security_flags


def _app_with_base_url(base_url: str) -> Starlette:
    app = create_starlette_app(base_url=base_url, enable_auth=True)
    get_starlette_server_state_init(base_url=base_url).apply(app.state)
    return app


async def test_concurrent_sessions_keep_their_cookie_scope(app: Starlette):
    first_started = asyncio.Event()
    second_started = asyncio.Event()
    first_finished = asyncio.Event()

    async def set_session(scope: Scope, receive: Receive, send: Send):
        if HTTPConnection(scope).url.port == 2718:
            first_started.set()
            await second_started.wait()
        else:
            second_started.set()
            await first_finished.wait()
        scope["session"]["value"] = "test"
        await JSONResponse({})(scope, receive, send)
        first_finished.set()

    middleware = CustomSessionMiddleware(set_session, "secret_key")

    async def request(port: int) -> str:
        scope = create_connection(app).scope
        scope["headers"] = [(b"host", f"localhost:{port}".encode())]
        messages: list[Message] = []

        async def capture(message: Message):
            messages.append(message)

        if port == 2720:
            await first_started.wait()
        await middleware(scope, mock_receive, capture)
        return Headers(scope=messages[0])["set-cookie"]

    first, second = await asyncio.wait_for(
        asyncio.gather(request(2718), request(2720)), timeout=5
    )
    assert list(SimpleCookie(first)) == ["session_2718"]
    assert list(SimpleCookie(second)) == ["session_2720"]


def test_sessions_survive_login_to_forwarded_server():
    @requires("edit")
    async def protected(request: HTTPConnection) -> JSONResponse:
        del request
        return JSONResponse({"authenticated": True})

    @requires("edit")
    async def protected_websocket(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_json({"authenticated": True})
        await websocket.close()

    def make_app(token: str) -> Starlette:
        app = _app_with_base_url("")
        app.state.port = 2718
        app.state.session_manager._token_manager.auth_token = AuthToken(token)
        app.router.routes.insert(0, Route("/protected", protected))
        app.router.routes.insert(
            0, WebSocketRoute("/protected-ws", protected_websocket)
        )
        return app

    # Browsers share cookies across ports on the same host.
    cookies = CookieJar()
    local = TestClient(
        make_app("local-token"),
        base_url="http://localhost:2718",
        cookies=cookies,
    )
    remote = TestClient(
        make_app("remote-token"),
        base_url="http://localhost:2720",
        cookies=cookies,
    )

    assert local.get("/protected").status_code == 401
    assert remote.get("/protected").status_code == 401
    assert (
        local.get(
            "/protected", params={"access_token": "local-token"}
        ).status_code
        == 200
    )
    assert local.get("/protected").status_code == 200
    assert (
        remote.get(
            "/protected", params={"access_token": "remote-token"}
        ).status_code
        == 200
    )

    assert local.get("/protected").status_code == 200
    assert remote.get("/protected").status_code == 200

    for client, port in [(local, 2718), (remote, 2720)]:
        with client.websocket_connect(
            f"ws://localhost:{port}/protected-ws"
        ) as websocket:
            assert websocket.receive_json() == {"authenticated": True}


@pytest.fixture
def app() -> Starlette:
    app = create_starlette_app(base_url="", enable_auth=True)
    StarletteServerStateInit(
        port=1234,
        host="localhost",
        base_url="",
        asset_url=None,
        headless=False,
        quiet=False,
        session_manager=get_mock_session_manager(),
        config_manager=MarimoConfigManager(UserConfigManager()),
        remote_url=None,
        mcp_server_enabled=False,
        skew_protection=False,
        enable_auth=True,
    ).apply(app.state)
    return app


def create_connection(app: Starlette) -> HTTPConnection:
    conn = HTTPConnection(
        {
            "type": "http",
            "app": app,
            "headers": [],
            "query_string": b"",
            "method": "GET",
            "path": "/",
        }
    )
    return conn


async def test_validate_auth_with_valid_cookie(app: Starlette):
    conn = create_connection(app)
    # Run all middleware
    await app.build_middleware_stack()(conn.scope, mock_receive, mock_send)
    conn.session["access_token"] = hash_access_token(
        str(AppState.from_app(app).session_manager.auth_token)
    )

    assert validate_auth(conn) is True


async def test_validate_auth_with_bad_cookie(app: Starlette):
    conn = create_connection(app)
    # Run all middleware
    await app.build_middleware_stack()(conn.scope, mock_receive, mock_send)
    conn.session["access_token"] = "bad_token"

    assert validate_auth(conn) is False


async def test_validate_auth_rejects_raw_token_in_cookie(app: Starlette):
    # A cookie carrying the raw token (e.g. from an older marimo version, or
    # forged by someone who knows the token) must not be accepted; only the
    # keyed hash is.
    conn = create_connection(app)
    await app.build_middleware_stack()(conn.scope, mock_receive, mock_send)
    conn.session["access_token"] = str(
        AppState.from_app(app).session_manager.auth_token
    )

    assert validate_auth(conn) is False


def test_cookie_session_never_stores_raw_token():
    session: dict[str, str] = {}
    cookie_session = CookieSession(session)
    cookie_session.set_access_token("super-secret")

    assert session["access_token"] != "super-secret"
    assert "super-secret" not in session["access_token"]
    assert session["access_token"] == hash_access_token("super-secret")
    assert cookie_session.get_access_token() == hash_access_token(
        "super-secret"
    )


def test_hash_access_token_is_keyed_and_deterministic():
    assert hash_access_token("a") == hash_access_token("a")
    assert hash_access_token("a") != hash_access_token("b")
    # 64 hex chars (sha256)
    assert len(hash_access_token("a")) == 64


def test_session_secret_env_override():
    # GlobalSettings reads env vars at import time, so check in a fresh
    # interpreter.
    code = (
        "from marimo._server.api.auth import SESSION_SECRET, hash_access_token;"
        "print(str(SESSION_SECRET));"
        "print(hash_access_token('tok'))"
    )

    def run(env: dict[str, str]) -> list[str]:
        out = subprocess.check_output(
            [sys.executable, "-c", code],
            env={**os.environ, **env},
            text=True,
        )
        return out.strip().splitlines()

    stable_a = run({"MARIMO_SESSION_SECRET": "stable-secret"})
    stable_b = run({"MARIMO_SESSION_SECRET": "stable-secret"})
    assert stable_a[0] == "stable-secret"
    # Same secret => same cookie hash across processes
    assert stable_a[1] == stable_b[1]

    random_a = run({"MARIMO_SESSION_SECRET": ""})
    random_b = run({"MARIMO_SESSION_SECRET": ""})
    # Empty/unset => random per process, so hashes differ
    assert random_a[0] != "stable-secret"
    assert random_a[0] != random_b[0]
    assert random_a[1] != random_b[1]


async def test_validate_auth_with_valid_access_token(app: Starlette):
    conn = create_connection(app)
    # Run all middleware
    await app.build_middleware_stack()(conn.scope, mock_receive, mock_send)
    token = str(AppState.from_app(app).session_manager.auth_token)
    conn._query_params = QueryParams([("access_token", token)])

    assert validate_auth(conn) is True


async def test_validate_auth_with_invalid_access_token(app: Starlette):
    conn = create_connection(app)
    # Run all middleware
    await app.build_middleware_stack()(conn.scope, mock_receive, mock_send)
    conn._query_params = QueryParams([("access_token", "bad_token")])

    assert validate_auth(conn) is False


async def test_validate_auth_with_valid_basic_auth(app: Starlette):
    conn = create_connection(app)
    auth_token = AppState.from_app(app).session_manager.auth_token
    # Run all middleware
    await app.build_middleware_stack()(conn.scope, mock_receive, mock_send)
    basic_auth_header = (
        f"Basic {base64.b64encode(f'user:{auth_token}'.encode()).decode()}"
    )
    conn._headers = Headers({"Authorization": basic_auth_header})

    assert validate_auth(conn) is True


async def test_validate_auth_with_missing_password_in_basic_auth(
    app: Starlette,
):
    conn = create_connection(app)
    # Run all middleware
    await app.build_middleware_stack()(conn.scope, mock_receive, mock_send)
    basic_auth_header = f"Basic {base64.b64encode(b'test:').decode()}"
    conn._headers = Headers({"Authorization": basic_auth_header})

    assert validate_auth(conn) is False


async def test_validate_auth_with_no_auth(app: Starlette):
    conn = create_connection(app)
    # Run all middleware
    await app.build_middleware_stack()(conn.scope, mock_receive, mock_send)
    assert validate_auth(conn) is False


async def test_custom_auth_middleware_preserves_user():
    app = Starlette()
    get_starlette_server_state_init().apply(app.state)

    async def test_app(scope: Any, receive: Any, send: Any) -> None:
        del receive, send
        # Verify the user was swapped during middleware execution
        assert scope["user"].username == "test_user"
        assert (
            scope[CustomAuthenticationMiddleware.KEY].username == "test_user"
        )

    middleware = CustomAuthenticationMiddleware(
        test_app, backend=AuthBackend(should_authenticate=False)
    )
    scope = {
        "type": "http",
        "user": SimpleUser("test_user"),
        "app": app,
        "path": "/",
    }

    await middleware(scope, mock_receive, mock_send)
    # Verify original user was restored and temp key was cleaned up
    assert scope["user"].username == "test_user"
    assert CustomAuthenticationMiddleware.KEY not in scope


async def test_custom_auth_middleware_without_user():
    app = Starlette()
    get_starlette_server_state_init().apply(app.state)

    async def test_app(scope: Any, receive: Any, send: Any) -> None:
        del receive, send
        # Fallbacks to SimpleUser("user")
        assert scope["user"].username == "user"

    middleware = CustomAuthenticationMiddleware(
        test_app, backend=AuthBackend(should_authenticate=False)
    )
    scope = {
        "type": "http",
        "app": app,
        "path": "/",
    }

    await middleware(scope, mock_receive, mock_send)
    assert CustomAuthenticationMiddleware.KEY not in scope
