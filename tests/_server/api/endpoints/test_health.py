# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo import __version__

if TYPE_CHECKING:
    from starlette.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "healthy"}
    response = client.get("/healthz")
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "healthy"}


def test_status(client: TestClient) -> None:
    response = client.get("/api/status")
    assert response.status_code == 200, response.text
    content = response.json()
    assert content["status"] == "healthy"
    assert len(content["filenames"]) == 0
    assert content["mode"] == "edit"
    assert content["sessions"] == 0
    assert content["version"] == __version__
    assert content["lsp_running"] is False


def test_version(client: TestClient) -> None:
    response = client.get("/api/version")
    assert response.status_code == 200, response.text
    assert response.text == __version__


def test_memory(client: TestClient) -> None:
    response = client.get("/api/usage")
    assert response.status_code == 200, response.text
    memory = response.json()["memory"]
    assert memory["total"] > 0
    assert memory["available"] > 0
    assert memory["used"] > 0
    assert memory["free"] > 0
    cpu = response.json()["cpu"]
    assert cpu["percent"] >= 0
