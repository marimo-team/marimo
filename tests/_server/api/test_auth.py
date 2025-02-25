from __future__ import annotations

import base64
from typing import Any

import pytest
from starlette.applications import Starlette
from starlette.authentication import SimpleUser
from starlette.datastructures import Headers, QueryParams
from starlette.requests import HTTPConnection

from marimo._config.manager import UserConfigManager
from marimo._server.api.auth import (
    AppState,
    CustomAuthenticationMiddleware,
    CustomSessionMiddleware,
    validate_auth,
)
from marimo._server.api.middleware import AuthBackend
from marimo._server.main import create_starlette_app
from tests._server.mocks import get_mock_session_manager


async def mock_receive() -> Any:
    return {
        "type": "http.disconnect",
    }


async def mock_send(message: Any) -> None:
    del message
    pass


async def test_custom_session_middleware_call(app: Starlette):
    middleware = CustomSessionMiddleware(app, "secret_key")
    scope = create_connection(app).scope

    await middleware(scope, mock_receive, mock_send)
    assert middleware.session_cookie == "session_1234"


async def test_custom_session_middleware_call_with_port():
    app = Starlette()
    middleware = CustomSessionMiddleware(app, "secret_key")
    scope = create_connection(app).scope

    await middleware(scope, mock_receive, mock_send)
    assert middleware.session_cookie == "session"


@pytest.fixture
def app() -> Starlette:
    app = create_starlette_app(base_url="", enable_auth=True)
    app.state.session_manager = get_mock_session_manager()
    app.state.config_manager = UserConfigManager()
    app.state.host = "localhost"
    app.state.port = 1234
    app.state.base_url = ""
    return app


def create_connection(app: Starlette) -> HTTPConnection:
    conn = HTTPConnection(
        {
            "type": "http",
            "app": app,
            "headers": {},
            "query_string": "",
            "method": "GET",
            "path": "/",
        }
    )
    return conn


async def test_validate_auth_with_valid_cookie(app: Starlette):
    conn = create_connection(app)
    # Run all middleware
    await app.build_middleware_stack()(conn.scope, mock_receive, mock_send)
    conn.session["access_token"] = str(
        AppState.from_app(app).session_manager.auth_token
    )

    assert validate_auth(conn) is True


async def test_validate_auth_with_bad_cookie(app: Starlette):
    conn = create_connection(app)
    # Run all middleware
    await app.build_middleware_stack()(conn.scope, mock_receive, mock_send)
    conn.session["access_token"] = "bad_token"

    assert validate_auth(conn) is False


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
    app.state.session_manager = get_mock_session_manager()

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
    app.state.session_manager = get_mock_session_manager()

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
