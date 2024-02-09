# Copyright 2024 Marimo. All rights reserved.
from typing import Generator

import pytest
import uvicorn
from starlette.testclient import TestClient

from marimo._config.manager import UserConfigManager
from marimo._server.main import create_starlette_app
from marimo._server.sessions import SessionManager
from marimo._server.utils import initialize_asyncio
from tests._server.mocks import get_mock_session_manager

app = create_starlette_app(base_url="")


@pytest.fixture(scope="session", autouse=True)
def init() -> None:
    initialize_asyncio()


@pytest.fixture(scope="module")
def client_with_lifespans() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
def client() -> TestClient:
    app.state.session_manager = get_mock_session_manager()
    app.state.config_manager = UserConfigManager()
    client = TestClient(app)

    # Mock out the server
    uvicorn_server = uvicorn.Server(uvicorn.Config(app))
    uvicorn_server.servers = []

    app.state.server = uvicorn_server
    app.state.host = "localhost"
    app.state.port = 1234
    app.state.base_url = ""
    return client


def get_session_manager(client: TestClient) -> SessionManager:
    return client.app.state.session_manager  # type: ignore
