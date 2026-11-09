from __future__ import annotations

import base64
import os
import subprocess
import sys
from typing import Any

import pytest
from starlette.applications import Starlette
from starlette.authentication import SimpleUser, requires
from starlette.datastructures import Headers, QueryParams
from starlette.requests import HTTPConnection, Request
from starlette.responses import Response
from starlette.routing import Route, WebSocketRoute
from starlette.testclient import TestClient
from starlette.websockets import WebSocket, WebSocketDisconnect

from marimo._config.config import merge_default_config
from marimo._config.config_schema import ServerConfig
from marimo._config.manager import MarimoConfigManager, UserConfigStore
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
from tests._server.mocks import (
    get_mock_session_manager,
    get_starlette_server_state_init,
)


async def mock_receive() -> Any:
    return {
        "type": "http.disconnect",
    }


async def mock_send(message: Any) -> None:
    del message


async def test_custom_session_middleware_call(app: Starlette):
    middleware = CustomSessionMiddleware(app, "secret_key")
    scope = create_connection(app).scope

    await middleware(scope, mock_receive, mock_send)
    assert middleware.session_cookie == "session_1234"
    assert middleware.path == "/"


async def test_custom_session_middleware_call_with_port():
    app = Starlette()
    middleware = CustomSessionMiddleware(app, "secret_key")
    scope = create_connection(app).scope

    await middleware(scope, mock_receive, mock_send)
    assert middleware.session_cookie == "session"


def test_custom_session_middleware_secure_flag_default(app: Starlette):
    # By default the session cookie is not marked Secure so it works over
    # plain HTTP during local development.
    middleware = CustomSessionMiddleware(app, "secret_key")
    assert "secure" not in middleware.security_flags


def test_custom_session_middleware_secure_flag_enabled(app: Starlette):
    # https_only=True (wired from MARIMO_SERVER_SESSION_COOKIE_SECURE) marks the
    # session cookie as Secure.
    middleware = CustomSessionMiddleware(app, "secret_key", https_only=True)
    assert "secure" in middleware.security_flags


def _app_with_base_url(
    base_url: str, *, partitioned: bool = False
) -> Starlette:
    app = create_starlette_app(
        base_url=base_url,
        enable_auth=True,
        host="kernel.example",
        server_config=ServerConfig(session_cookie_partitioned=partitioned),
    )
    get_starlette_server_state_init(base_url=base_url).apply(app.state)
    return app


async def test_custom_session_middleware_scopes_cookie_to_base_url():
    app = _app_with_base_url("/marimo1")
    middleware = CustomSessionMiddleware(app, "secret_key")
    scope = create_connection(app).scope

    await middleware(scope, mock_receive, mock_send)
    assert middleware.session_cookie == "session_1234_marimo1"
    assert middleware.path == "/marimo1"


async def test_custom_session_middleware_scopes_cookie_to_nested_base_url():
    app = _app_with_base_url("/apps/ml/notebook")
    middleware = CustomSessionMiddleware(app, "secret_key")
    scope = create_connection(app).scope

    await middleware(scope, mock_receive, mock_send)
    assert middleware.session_cookie == "session_1234_apps_ml_notebook"
    assert middleware.path == "/apps/ml/notebook"


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
        config_manager=MarimoConfigManager(UserConfigStore()),
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


@pytest.mark.parametrize(
    "variable", ["MARIMO_SERVER_SESSION_SECRET", "MARIMO_SESSION_SECRET"]
)
def test_session_secret_env_override(variable: str):
    # The fallback secret is random per process; check in fresh interpreters.
    code = (
        "from marimo._config.manager import get_default_config_manager;"
        "from marimo._server.main import create_starlette_app;"
        "from marimo._server.api.auth import hash_access_token;"
        "config = get_default_config_manager(current_path=None).get_config(hide_secrets=False);"
        "app = create_starlette_app(base_url='', server_config=config.server);"
        "print(str(app.state.session_secret));"
        "print(hash_access_token('tok', secret=app.state.session_secret))"
    )

    def run(env: dict[str, str]) -> list[str]:
        out = subprocess.check_output(
            [sys.executable, "-c", code],
            env={
                **{
                    key: value
                    for key, value in os.environ.items()
                    if key
                    not in (
                        "MARIMO_SERVER_SESSION_SECRET",
                        "MARIMO_SESSION_SECRET",
                    )
                },
                **env,
            },
            text=True,
        )
        return out.strip().splitlines()

    stable_a = run({variable: "stable-secret"})
    stable_b = run({variable: "stable-secret"})
    assert stable_a[0] == "stable-secret"
    # Same secret => same cookie hash across processes
    assert stable_a[1] == stable_b[1]

    random_a = run({variable: ""})
    random_b = run({variable: ""})
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


@pytest.mark.parametrize(
    ("headers", "query"),
    [
        ({"Authorization": "Bearer \xe9"}, []),
        (
            {
                "Authorization": f"Basic {base64.b64encode('u:é'.encode()).decode()}"
            },
            [],
        ),
        ({}, [("access_token", "é")]),
    ],
)
async def test_validate_auth_rejects_non_ascii_credentials(
    app: Starlette, headers: dict[str, str], query: list[tuple[str, str]]
):
    conn = create_connection(app)
    # Run all middleware
    await app.build_middleware_stack()(conn.scope, mock_receive, mock_send)
    conn._headers = Headers(headers)
    conn._query_params = QueryParams(query)

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


@pytest.mark.parametrize("partitioned", [False, True])
async def test_configured_session_secret_signs_and_validates_cookies(
    partitioned: bool,
) -> None:
    config = merge_default_config(
        {
            "server": {
                "session_secret": "configured-secret",
                "session_cookie_secure": True,
                "session_cookie_partitioned": partitioned,
            }
        }
    )
    app = create_starlette_app(base_url="", server_config=config.server)
    get_starlette_server_state_init().apply(app.state)
    middleware = next(
        item
        for item in app.user_middleware
        if item.cls is CustomSessionMiddleware
    )
    assert middleware.kwargs == {
        "secret_key": "configured-secret",
        "https_only": True,
        "partitioned": partitioned,
    }
    conn = create_connection(app)
    await app.build_middleware_stack()(conn.scope, mock_receive, mock_send)
    token = str(AppState.from_app(app).session_manager.auth_token)
    CookieSession(
        conn.session, secret=app.state.session_secret
    ).set_access_token(token)
    assert validate_auth(conn)
    conn.session["access_token"] = hash_access_token(
        token, secret="another-server-secret"
    )
    assert not validate_auth(conn)


def test_partial_server_config_defaults_to_insecure_local_cookie() -> None:
    app = create_starlette_app(
        base_url="",
        server_config=ServerConfig(browser="default", follow_symlink=False),
    )
    middleware = next(
        item
        for item in app.user_middleware
        if item.cls is CustomSessionMiddleware
    )
    assert middleware.kwargs["https_only"] is False


@pytest.mark.parametrize("base_url", ["", "/nested/marimo"])
@pytest.mark.parametrize(
    ("method", "path", "peer", "authority", "token", "allowed"),
    [
        (
            "POST",
            "/api/kernel/execute",
            "127.0.0.1",
            "localhost:1234",
            "local-secret",
            True,
        ),
        (
            "POST",
            "/api/kernel/execute",
            "::1",
            "[::1]:1234",
            "local-secret",
            True,
        ),
        (
            "POST",
            "/api/kernel/execute",
            "10.0.0.1",
            "localhost:1234",
            "local-secret",
            False,
        ),
        (
            "POST",
            "/api/kernel/execute",
            "127.0.0.1",
            "example.com:1234",
            "local-secret",
            False,
        ),
        (
            "POST",
            "/api/kernel/execute",
            "127.0.0.1",
            "localhost:1235",
            "local-secret",
            False,
        ),
        (
            "POST",
            "/api/kernel/execute",
            "127.0.0.1",
            "localhost:1234",
            "wrong",
            False,
        ),
        (
            "GET",
            "/api/sessions",
            "127.0.0.1",
            "localhost:1234",
            "local-secret",
            False,
        ),
        (
            "POST",
            "/api/kernel/run",
            "127.0.0.1",
            "localhost:1234",
            "local-secret",
            False,
        ),
        (
            "GET",
            "/api/kernel/execute",
            "127.0.0.1",
            "localhost:1234",
            "local-secret",
            False,
        ),
    ],
)
def test_local_credential_is_scoped_to_execution(
    base_url: str,
    method: str,
    path: str,
    peer: str,
    authority: str,
    token: str,
    allowed: bool,
) -> None:
    from marimo._server.host.bridge import SessionBridge
    from marimo._server.host.context import HostContext

    app = _app_with_base_url(base_url)
    app.state.host_context = HostContext(
        bridge=SessionBridge(app.state.session_manager),
        token="local-secret",
        port=1234,
    )
    conn = create_connection(app)
    conn.scope.update(
        method=method,
        path=base_url + path,
        client=(peer, 5000),
        session={},
        headers=[
            (b"host", authority.encode()),
            (b"authorization", f"Bearer {token}".encode()),
        ],
    )
    assert validate_auth(conn) is allowed
    assert conn.session == {}


@pytest.mark.parametrize("partitioned", [False, True])
@pytest.mark.parametrize("base_url", ["", "/nested/path"])
def test_partitioned_cookie_lifecycle(partitioned: bool, base_url: str):
    app = _app_with_base_url(base_url, partitioned=partitioned)
    token = str(AppState.from_app(app).session_manager.auth_token)

    @requires("read")
    async def session(request: Request) -> Response:
        if request.method == "DELETE":
            request.session.clear()
        else:
            CookieSession(request.session).set_access_token(token)
        return Response()

    path = f"{base_url}/chips-session"
    app.router.routes.insert(
        0, Route(path, session, methods=["GET", "DELETE"])
    )
    skew_token = AppState.from_app(app).session_manager.skew_protection_token
    with TestClient(app, base_url="https://kernel.example") as client:
        assert client.get(path).status_code == 401
        for index, method in enumerate(("GET", "GET", "DELETE")):
            response = client.request(
                method,
                path,
                params={"access_token": token} if index == 0 else None,
                headers={"Marimo-Server-Token": str(skew_token)},
            )
            assert response.status_code == 200
            cookie = response.headers["set-cookie"].lower()
            assert "; httponly" in cookie
            assert ("; partitioned" in cookie) is partitioned
            assert ("; samesite=none" in cookie) is partitioned
            assert ("; secure" in cookie) is partitioned
            assert ("; samesite=lax" in cookie) is not partitioned
            assert cookie.startswith(
                "session_1234" + base_url.replace("/", "_") + "="
            )
            assert f"path={base_url or '/'};" in cookie
            if method == "DELETE":
                assert "expires=thu, 01 jan 1970" in cookie
        assert client.get(path).status_code == 401


@pytest.mark.parametrize(
    ("origin", "metadata", "allowed"),
    [
        ("https://kernel.example", None, True),
        ("https://kernel.example:443", None, True),
        ("https://kernel.example:444", None, False),
        ("https://kernel.example:0", None, False),
        ("http://kernel.example", None, False),
        ("https://attacker.example", None, False),
        ("https://sibling.kernel.example", None, False),
        ("null", None, False),
        ("https://kernel.example/path", None, False),
        ("https://user@kernel.example", None, False),
        ("https://kernel.example:invalid", None, False),
        ("https://kernel.example:65536", None, False),
        ("https://kernel.example\\", None, False),
        ("https://kernel.example:", None, False),
        ("https://kernel.example?", None, False),
        ("https://kernel.example#", None, False),
        (" https://kernel.example", None, False),
        ("https://kernel.exa\nmple", None, False),
        (None, None, True),
        (None, "cross-site", False),
        (None, "same-site", False),
        (None, "same-origin", True),
    ],
)
@pytest.mark.parametrize("connection_type", ["http", "websocket"])
def test_partitioned_cookie_origin(
    app: Starlette,
    origin: str | None,
    metadata: str | None,
    allowed: bool,
    connection_type: str,
):
    conn = create_connection(app)
    conn.scope.update(
        type=connection_type,
        method="POST",
        scheme="http",
        marimo_partitioned_session=True,
        session={
            "access_token": hash_access_token(
                str(AppState.from_app(app).session_manager.auth_token)
            )
        },
    )
    headers = {"host": "kernel.example"}
    if origin is not None:
        headers["origin"] = origin
    if metadata is not None:
        headers["sec-fetch-site"] = metadata
    conn.scope["headers"] = Headers(headers).raw
    assert validate_auth(conn) is allowed


@pytest.mark.parametrize("credential", ["query", "bearer"])
def test_partitioned_cross_origin_explicit_token(
    app: Starlette, credential: str
):
    conn = create_connection(app)
    token = str(AppState.from_app(app).session_manager.auth_token)
    conn.scope.update(
        type="websocket",
        marimo_partitioned_session=True,
        session={"access_token": hash_access_token(token)},
    )
    headers = {"host": "kernel.example", "origin": "https://attacker.example"}
    if credential == "bearer":
        headers["authorization"] = f"Bearer {token}"
    else:
        conn.scope["query_string"] = f"access_token={token}".encode()
    conn.scope["headers"] = Headers(headers).raw
    assert validate_auth(conn) is True


def test_partitioned_websocket_rejects_unrelated_origin():
    app = _app_with_base_url("", partitioned=True)
    token = str(AppState.from_app(app).session_manager.auth_token)

    @requires("read")
    async def session(request: Request) -> Response:
        CookieSession(request.session).set_access_token(token)
        return Response()

    async def websocket(socket: WebSocket) -> None:
        if not validate_auth(socket):
            await socket.close(code=1008)
            return
        await socket.accept()
        await socket.send_text("authenticated")
        await socket.close()

    app.router.routes.insert(0, Route("/chips-session", session))
    app.router.routes.insert(0, WebSocketRoute("/chips-ws", websocket))
    with TestClient(app, base_url="https://kernel.example") as client:
        assert client.get("/chips-session").status_code == 401
        response = client.get("/chips-session", params={"access_token": token})
        assert response.status_code == 200
        cookie = response.headers["set-cookie"]
        assert "partitioned" in cookie.lower()
        # Replay the cookie as a browser that ignores Partitioned would.
        headers = {"cookie": cookie.split(";", 1)[0]}
        with client.websocket_connect(
            "wss://kernel.example/chips-ws",
            headers={**headers, "origin": "https://kernel.example"},
        ) as socket:
            assert socket.receive_text() == "authenticated"
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                "wss://kernel.example/chips-ws",
                headers={**headers, "origin": "https://attacker.example"},
            ):
                pytest.fail("accepted an unrelated origin")


@pytest.mark.parametrize("value", ["true", "1", "false", "0"])
def test_partitioned_cookie_env(value: str):
    output = subprocess.check_output(
        [
            sys.executable,
            "-c",
            'from marimo._config.manager import EnvVarReader; print(EnvVarReader().read()["server"]["session_cookie_partitioned"])',
        ],
        env={**os.environ, "MARIMO_SERVER_SESSION_COOKIE_PARTITIONED": value},
        text=True,
    )
    assert output.strip() == str(value in ("true", "1"))


def test_partitioned_navigation_does_not_require_kernel_origin(app: Starlette):
    conn = create_connection(app)
    conn.scope.update(
        marimo_partitioned_session=True,
        session={
            "access_token": hash_access_token(
                str(AppState.from_app(app).session_manager.auth_token)
            )
        },
        headers=Headers(
            {"host": "kernel.example", "origin": "https://hub.example"}
        ).raw,
    )
    assert validate_auth(conn) is True


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
@pytest.mark.parametrize(
    ("headers", "allowed"),
    [
        (
            [
                ("host", "kernel.example:8443"),
                ("origin", "https://kernel.example:8443"),
            ],
            True,
        ),
        (
            [
                ("host", "kernel.example:8443"),
                ("origin", "https://kernel.example"),
            ],
            False,
        ),
        ([("host", "[::1]:8443"), ("origin", "https://[::1]:8443")], True),
        (
            [("host", "[::1]:8443"), ("origin", "https://[::1]invalid:8443")],
            False,
        ),
        (
            [("host", "[::1]invalid:8443"), ("origin", "https://[::1]:8443")],
            False,
        ),
        (
            [
                ("host", "kernel.example"),
                ("origin", "https://kernel.example"),
                ("origin", "https://attacker.example"),
            ],
            False,
        ),
        (
            [
                ("host", "kernel.example"),
                ("host", "attacker.example"),
                ("origin", "https://kernel.example"),
            ],
            False,
        ),
        (
            [
                ("host", "kernel.example/path"),
                ("origin", "https://kernel.example"),
            ],
            False,
        ),
        (
            [
                ("host", "kernel.example"),
                ("origin", "https://attacker.example"),
                ("x-forwarded-host", "attacker.example"),
            ],
            False,
        ),
        (
            [
                ("host", "internal:2718"),
                ("origin", "https://kernel.example"),
                ("x-forwarded-host", "kernel.example"),
            ],
            False,
        ),
    ],
)
def test_partitioned_cookie_public_authority(
    app: Starlette, method: str, headers: list[tuple[str, str]], allowed: bool
):
    conn = create_connection(app)
    token = str(AppState.from_app(app).session_manager.auth_token)
    conn.scope.update(
        method=method,
        scheme="http",
        marimo_partitioned_session=True,
        session={"access_token": hash_access_token(token)},
        headers=[(key.encode(), value.encode()) for key, value in headers],
    )
    assert validate_auth(conn) is allowed


@pytest.mark.parametrize("connection_type", ["http", "websocket"])
@pytest.mark.parametrize(
    ("hosts", "allowed"),
    [
        ([], False),
        (["kernel.example"], True),
        (["kernel.example", "kernel.example"], False),
        (["kernel.example", "attacker.example"], False),
    ],
)
def test_partitioned_cookie_without_origin_requires_one_host(
    app: Starlette, connection_type: str, hosts: list[str], allowed: bool
):
    conn = create_connection(app)
    token = str(AppState.from_app(app).session_manager.auth_token)
    conn.scope.update(
        type=connection_type,
        method="POST",
        marimo_partitioned_session=True,
        session={"access_token": hash_access_token(token)},
        headers=[(b"host", host.encode()) for host in hosts],
    )
    assert validate_auth(conn) is allowed
