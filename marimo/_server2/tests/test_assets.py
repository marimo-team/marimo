# Copyright 2024 Marimo. All rights reserved.
from typing import cast

from starlette.testclient import TestClient

from marimo._server.sessions import SessionManager


def test_index(client: TestClient) -> None:
    session_manager = cast(SessionManager, client.app.state.session_manager)
    response = client.get("/")
    assert response.status_code == 200, response.text
    content = response.text
    assert "<marimo-filename" in content
    assert session_manager.filename is not None
    assert session_manager.filename in content
    assert "edit" in content
    assert session_manager.server_token in content


def test_favicon(client: TestClient) -> None:
    response = client.get("/favicon.ico")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "image/x-icon"


def test_unknown_file(client: TestClient) -> None:
    response = client.get("/unknown_file")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"detail": "Not Found"}
