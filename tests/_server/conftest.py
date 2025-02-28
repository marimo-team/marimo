# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import sys
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

import pytest
import uvicorn
from starlette.testclient import TestClient

from marimo._config.manager import MarimoConfigManager, UserConfigManager
from marimo._config.utils import CONFIG_FILENAME
from marimo._server.api.deps import AppState
from marimo._server.main import create_starlette_app
from marimo._server.sessions import SessionManager
from marimo._server.utils import initialize_asyncio
from tests._server.mocks import get_mock_session_manager

if TYPE_CHECKING:
    from collections.abc import Generator, Iterator

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
def user_config_manager() -> Iterator[UserConfigManager]:
    tmp = TemporaryDirectory()
    config_path = os.path.join(tmp.name, CONFIG_FILENAME)
    with open(config_path, "w") as f:
        f.write("")

    class TestUserConfigManager(UserConfigManager):
        def __init__(self) -> None:
            super().__init__()

        def get_config_path(self) -> str:
            return config_path

    yield TestUserConfigManager()

    tmp.cleanup()


@pytest.fixture
def client(user_config_manager: UserConfigManager) -> Iterator[TestClient]:
    main = sys.modules["__main__"]
    app.state.session_manager = get_mock_session_manager()
    app.state.config_manager = MarimoConfigManager(user_config_manager)
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


def get_session_config_manager(client: TestClient) -> UserConfigManager:
    """Assumes only one active session."""
    sessions = list(
        AppState.from_app(client.app).session_manager.sessions.values()
    )
    assert len(sessions) == 1
    return sessions[0].config_manager  # type: ignore


def get_user_config_manager(client: TestClient) -> UserConfigManager:
    return client.app.state.app_config_manager  # type: ignore
