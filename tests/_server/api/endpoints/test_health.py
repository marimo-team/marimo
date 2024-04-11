# Copyright 2024 Marimo. All rights reserved.
from starlette.testclient import TestClient

from marimo import __version__


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
