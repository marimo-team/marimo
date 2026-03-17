# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
from typing import TYPE_CHECKING

import anyio
import pytest

from marimo._dependencies.dependencies import DependencyManager
from tests._server.mocks import token_header, with_session

HAS_FORMATTER = DependencyManager.ruff.has() or DependencyManager.black.has()

if TYPE_CHECKING:
    from starlette.testclient import TestClient, WebSocketTestSession

SESSION_ID = "session-123"
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    **token_header("fake-token"),
}


def _receive_json_with_timeout(
    websocket: WebSocketTestSession, timeout_seconds: float = 0.5
) -> dict[str, object]:
    async def receive() -> dict[str, object]:
        with anyio.fail_after(timeout_seconds):
            message = await websocket._send_rx.receive()
        websocket._raise_on_close(message)
        return json.loads(message["text"])

    return websocket.portal.call(receive)


@with_session(SESSION_ID)
def test_code_autocomplete(client: TestClient) -> None:
    response = client.post(
        "/api/kernel/code_autocomplete",
        headers=HEADERS,
        json={
            "id": "completion-123",
            "document": "print('Hello, World!')",
            "cellId": "cell-123",
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert "success" in response.json()


@with_session(SESSION_ID)
def test_delete_cell(client: TestClient) -> None:
    response = client.post(
        "/api/kernel/delete",
        headers=HEADERS,
        json={
            "cellId": "cell-123",
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert "success" in response.json()


@pytest.mark.skipif(not HAS_FORMATTER, reason="ruff or black not installed")
@with_session(SESSION_ID)
def test_format_cell(client: TestClient) -> None:
    response = client.post(
        "/api/kernel/format",
        headers=HEADERS,
        json={
            "codes": {
                "cell-123": "def foo():\n  return 1",
            },
            "lineLength": 80,
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    formatted_codes = response.json().get("codes", {})
    assert "cell-123" in formatted_codes
    assert formatted_codes["cell-123"] == "def foo():\n    return 1"


@with_session(SESSION_ID)
def test_install_missing_packages(client: TestClient) -> None:
    response = client.post(
        "/api/kernel/install_missing_packages",
        headers=HEADERS,
        json={
            "manager": "pip",
            "versions": {},
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert "success" in response.json()


@with_session(SESSION_ID)
def test_set_cell_config(client: TestClient) -> None:
    response = client.post(
        "/api/kernel/set_cell_config",
        headers=HEADERS,
        json={
            "configs": {
                "cell-123": {"runnable": True},
            },
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert "success" in response.json()


@with_session(SESSION_ID)
def test_stdin(client: TestClient) -> None:
    response = client.post(
        "/api/kernel/stdin",
        headers=HEADERS,
        json={
            "text": "user input",
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert "success" in response.json()


@with_session(SESSION_ID)
def test_focus_cell(client: TestClient) -> None:
    response = client.post(
        "/api/kernel/focus_cell",
        headers=HEADERS,
        json={"cellId": "some-cell-id"},
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert "success" in response.json()


@with_session(SESSION_ID)
def test_focus_cell_notifies_same_session_kiosk_consumer(
    client: TestClient,
) -> None:
    cell_id = "some-cell-id"
    auth_token = token_header("fake-token")
    with client.websocket_connect(
        f"/ws?session_id={SESSION_ID}&kiosk=true&access_token=fake-token",
        headers=auth_token,
    ) as websocket:
        data = websocket.receive_json()
        assert data["op"] == "kernel-ready"
        assert data["data"]["kiosk"] is True

        response = client.post(
            "/api/kernel/focus_cell",
            headers=HEADERS,
            json={"cellId": cell_id},
        )
        assert response.status_code == 200, response.text

        message = _receive_json_with_timeout(websocket)
        assert message == {
            "op": "focus-cell",
            "data": {"op": "focus-cell", "cell_id": cell_id},
        }
