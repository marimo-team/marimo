# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import sys
import threading
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

from marimo._session.session import SessionImpl
import pytest
import uvicorn
from starlette.testclient import TestClient

from marimo._config.manager import MarimoConfigManager, UserConfigManager
from marimo._config.utils import CONFIG_FILENAME
from marimo._server.api.deps import AppState
from marimo._server.config import StarletteServerStateInit
from marimo._server.main import create_starlette_app
from marimo._server.session_manager import SessionManager
from marimo._server.utils import initialize_asyncio
from marimo._session.state.session_view import SessionView
from tests._server.mocks import get_mock_session_manager
from tests.utils import assert_serialize_roundtrip

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
    config_path = Path(tmp.name) / CONFIG_FILENAME
    config_path.write_text("")

    class TestUserConfigManager(UserConfigManager):
        def __init__(self) -> None:
            super().__init__()

        def get_config_path(self) -> str:
            return str(config_path)

    yield TestUserConfigManager()

    tmp.cleanup()


@pytest.fixture
def client(user_config_manager: UserConfigManager) -> Iterator[TestClient]:
    main = sys.modules["__main__"]
    client = TestClient(app)
    StarletteServerStateInit(
        port=1234,
        host="localhost",
        base_url="",
        asset_url=None,
        headless=False,
        quiet=False,
        session_manager=get_mock_session_manager(),
        config_manager=MarimoConfigManager(user_config_manager),
        remote_url=None,
        mcp_server_enabled=False,
        skew_protection=False,
        enable_auth=True,
    ).apply(app.state)

    # Mock out the server
    uvicorn_server = uvicorn.Server(uvicorn.Config(app))
    uvicorn_server.servers = []
    app.state.server = uvicorn_server

    yield client

    try:
        session_manager: SessionManager = client.app.state.session_manager
        kernel_tasks = []
        # Kernels started in run mode run in their own threads; if these kernels
        # execute code, they may patch and restore their own main modules.
        # To ensure that this fixture correctly restores the original saved
        # main module, we wait for threads to finish before restoring the module.
        for session in session_manager.sessions.values():
            assert isinstance(session, SessionImpl)
            kernel_task = session._kernel_manager.kernel_task
            if kernel_task is not None and isinstance(
                kernel_task, threading.Thread
            ):
                kernel_tasks.append(kernel_task)

        session_manager.shutdown()
        for task in kernel_tasks:
            if task.is_alive():
                task.join()
    finally:
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
    return client.app.state.config_manager  # type: ignore


@pytest.fixture
def session_view() -> Generator[SessionView, None, None]:
    sv = SessionView()

    yield sv

    # Test all operations can be serialized/deserialized
    for operation in sv.notifications:
        assert_serialize_roundtrip(operation)
