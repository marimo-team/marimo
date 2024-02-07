# Copyright 2024 Marimo. All rights reserved.
import uvicorn
from starlette.testclient import TestClient

from marimo._config.config import get_configuration
from marimo._server.main import create_starlette_app
from tests._server.mocks import get_mock_session_manager


def test_base_url() -> None:
    app = create_starlette_app(base_url="/foo")
    app.state.session_manager = get_mock_session_manager()
    app.state.user_config = get_configuration()
    app.state.session_manager = get_mock_session_manager()
    app.state.user_config = get_configuration()
    client = TestClient(app)

    # Mock out the server
    uvicorn_server = uvicorn.Server(uvicorn.Config(app))
    uvicorn_server.servers = []

    app.state.server = uvicorn_server
    app.state.host = "localhost"
    app.state.port = 1234
    app.state.base_url = "/foo"

    client = TestClient(app)

    # Infra routes, allows fallback
    response = client.get("/foo/health")
    assert response.status_code == 200, response.text
    response = client.get("/foo/healthz")
    assert response.status_code == 200, response.text
    response = client.get("/health")
    assert response.status_code == 200, response.text
    response = client.get("/healthz")
    assert response.status_code == 200, response.text

    # Index, allows fallback
    response = client.get("/foo/")
    assert response.status_code == 200, response.text
    response = client.get("/")
    assert response.status_code == 200, response.text

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
