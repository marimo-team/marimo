from __future__ import annotations

import base64
from typing import Any

import pytest
from starlette.applications import Starlette
from starlette.datastructures import Headers, QueryParams
from starlette.requests import HTTPConnection

from marimo._config.manager import UserConfigManager
from marimo._server.api.auth import (
    AppState,
    CustomSessionMiddleware,
    validate_auth,
)
from marimo._server.main import create_starlette_app
from tests._server.mocks import get_mock_session_manager


async def mock_receive() -> Any:
    return {}


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
    basic_auth_header = f"Basic {base64.b64encode('test:'.encode()).decode()}"
    conn._headers = Headers({"Authorization": basic_auth_header})

    assert validate_auth(conn) is False


async def test_validate_auth_with_no_auth(app: Starlette):
    conn = create_connection(app)
    # Run all middleware
    await app.build_middleware_stack()(conn.scope, mock_receive, mock_send)
    assert validate_auth(conn) is False
