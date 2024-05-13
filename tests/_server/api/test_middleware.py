# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
import uvicorn
from starlette.testclient import TestClient

from marimo._config.manager import UserConfigManager
from marimo._server.main import create_starlette_app
from marimo._server.model import SessionMode
from marimo._server.tokens import AuthToken
from tests._server.mocks import get_mock_session_manager, token_header

if TYPE_CHECKING:
    from starlette.applications import Starlette


def test_base_url() -> None:
    app = create_starlette_app(base_url="/foo")
    app.state.session_manager = get_mock_session_manager()
    app.state.config_manager = UserConfigManager()
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
    response = client.get("/")
    assert response.status_code == 401, response.text
    assert response.headers.get("Set-Cookie") is None

    # Authorized access
    response = client.get("/", headers=token_header("fake-token"))
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
    app.state.config_manager = UserConfigManager()
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
    app.state.config_manager = UserConfigManager()
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
    app.state.config_manager = UserConfigManager()
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
    app.state.config_manager = UserConfigManager()
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
    def test_no_auth(self, app: Starlette) -> None:
        # Test unauthorized access
        client = TestClient(app)
        response = client.get("/")
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
        response = client.get("/", headers=token_header("bad-token"))
        assert response.status_code == 401, response.text
        assert response.headers.get("Set-Cookie") is None


class TestNoAuth:
    def test_no_auth(self, no_auth_app: Starlette) -> None:
        client = TestClient(no_auth_app)
        response = client.get("/")
        assert response.status_code == 200, response.text
        assert response.headers.get("Set-Cookie") is None

    def tets_any_query(self, no_auth_app: Starlette) -> None:
        # Test unauthorized access with bad auth token
        client = TestClient(no_auth_app)
        response = client.get("/?access_token=bad-token")
        assert response.status_code == 200, response.text
        assert response.headers.get("Set-Cookie") is None

    def test_any_header(self, no_auth_app: Starlette) -> None:
        # Test unauthorized access with bad auth token
        client = TestClient(no_auth_app)
        response = client.get("/", headers=token_header("bad-token"))
        assert response.status_code == 200, response.text
        assert response.headers.get("Set-Cookie") is None
