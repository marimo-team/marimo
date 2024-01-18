from typing import Any, Generator

import pytest
from fastapi.testclient import TestClient

from marimo._server.model import SessionMode
from marimo._server.sessions import Session
from marimo._server2.api.deps import SessionManagerState
from marimo._server2.main import app


@pytest.fixture(scope="module")
def client_with_lifespans() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="module")
def state() -> SessionManagerState:
    return SessionManagerState(
        server_token="test-server-token",
        filename="test_app.py",
        mode=SessionMode.RUN,
        app_config=None,
        development_mode=False,
        quiet=False,
    )


@pytest.fixture(scope="module")
def LIFESPANS() -> Any:
    return []


@pytest.fixture(scope="module")
def session() -> Session:
    return None
