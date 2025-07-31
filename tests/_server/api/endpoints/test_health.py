# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo import __version__
from tests._server.mocks import token_header, with_session

if TYPE_CHECKING:
    from starlette.testclient import TestClient

SESSION_ID = "session-123"
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    **token_header("fake-token"),
}


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "healthy"}
    response = client.get("/healthz")
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "healthy"}


def test_status(client: TestClient) -> None:
    # Unauthorized
    response = client.get("/api/status")
    assert response.status_code == 401, response.text

    response = client.get("/api/status", headers=token_header())
    assert response.status_code == 200, response.text
    content = response.json()
    assert content["status"] == "healthy"
    assert len(content["filenames"]) == 0
    assert content["mode"] == "edit"
    assert content["sessions"] == 0
    assert content["version"] == __version__
    assert content["lsp_running"] is False
    assert content["python_version"] is not None


def test_version(client: TestClient) -> None:
    response = client.get("/api/version")
    assert response.status_code == 200, response.text
    assert response.text == __version__


def test_memory(client: TestClient) -> None:
    # Unauthorized
    response = client.get("/api/status")
    assert response.status_code == 401, response.text

    response = client.get("/api/usage", headers=token_header())
    assert response.status_code == 200, response.text
    memory = response.json()["memory"]
    assert memory["total"] > 0
    assert memory["available"] > 0
    assert memory["used"] > 0
    assert memory["free"] > 0
    cpu = response.json()["cpu"]
    assert cpu["percent"] >= 0
    computer = response.json()["server"]
    assert computer["memory"] > 0
    # None, no active session
    computer = response.json()["kernel"]
    assert computer["memory"] is None

    gpu = response.json()["gpu"]
    assert len(gpu) == 0


def test_connections(client: TestClient) -> None:
    response = client.get("/api/status/connections")
    assert response.status_code == 200
    assert response.json()["active"] == 0


@with_session(SESSION_ID)
def test_read_code(client: TestClient) -> None:
    response = client.get("/api/status/connections", headers=HEADERS)
    assert response.status_code == 200, response.text
    assert response.json()["active"] == 1
