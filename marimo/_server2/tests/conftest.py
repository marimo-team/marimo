# Copyright 2024 Marimo. All rights reserved.
from typing import Any, Generator

import pytest
import uvicorn
from starlette.testclient import TestClient

from marimo._config.config import get_configuration
from marimo._server.sessions import Session
from marimo._server2.main import app
from marimo._server2.tests.mocks import get_mock_session_manager


@pytest.fixture(scope="module")
def client_with_lifespans() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def client() -> TestClient:
    app.state.session_manager = get_mock_session_manager()
    app.state.user_config = get_configuration()
    client = TestClient(app)

    # Mock out the server
    uvicorn_server = uvicorn.Server(uvicorn.Config(app))
    uvicorn_server.servers = []

    app.state.server = uvicorn_server
    return client


@pytest.fixture(scope="module")
def LIFESPANS() -> Any:
    return []


@pytest.fixture(scope="module")
def session() -> Session:
    return None
