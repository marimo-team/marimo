# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import sys
from tempfile import TemporaryDirectory
from typing import Generator, Iterator

import pytest
import uvicorn
from starlette.testclient import TestClient

from marimo._config.manager import UserConfigManager
from marimo._config.utils import CONFIG_FILENAME
from marimo._server.main import create_starlette_app
from marimo._server.sessions import SessionManager
from marimo._server.utils import initialize_asyncio
from tests._server.mocks import get_mock_session_manager

app = create_starlette_app(base_url="", enable_auth=True)


@pytest.fixture(scope="session", autouse=True)
def init() -> bool:
    initialize_asyncio()
    return True


@pytest.fixture(scope="module")
def client_with_lifespans() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def user_config_manager() -> UserConfigManager:
    class TestUserConfigManager(UserConfigManager):
        def _get_config_path(self) -> str:
            tmp = TemporaryDirectory()
            return os.path.join(tmp.name, CONFIG_FILENAME)

    return TestUserConfigManager()


@pytest.fixture
def client(user_config_manager: UserConfigManager) -> Iterator[TestClient]:
    main = sys.modules["__main__"]
    app.state.session_manager = get_mock_session_manager()
    app.state.config_manager = user_config_manager
    client = TestClient(app)

    # Mock out the server
    uvicorn_server = uvicorn.Server(uvicorn.Config(app))
    uvicorn_server.servers = []

    app.state.server = uvicorn_server
    app.state.host = "localhost"
    app.state.port = 1234
    app.state.base_url = ""
    yield client
    sys.modules["__main__"] = main


def get_session_manager(client: TestClient) -> SessionManager:
    return client.app.state.session_manager  # type: ignore


def get_user_config_manager(client: TestClient) -> UserConfigManager:
    return client.app.state.config_manager  # type: ignore
