# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

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
def test_format_cell_passes_notebook_path_to_formatter(
    client: TestClient,
) -> None:
    with patch(
        "marimo._server.api.endpoints.editing.DefaultFormatter.format",
        new=AsyncMock(return_value={"cell-123": "x = 1"}),
    ) as mock_format:
        response = client.post(
            "/api/kernel/format",
            headers=HEADERS,
            json={
                "codes": {"cell-123": "x=1"},
                "lineLength": 80,
            },
        )

    assert response.status_code == 200, response.text
    assert response.json() == {"codes": {"cell-123": "x = 1"}}
    assert mock_format.await_count == 1

    args, kwargs = mock_format.await_args
    assert {"cell-123": "x=1"} in args
    assert isinstance(kwargs["stdin_filename"], str)
    assert kwargs["stdin_filename"].endswith(".py")


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


def _mock_server_install(
    client: TestClient, *, manager_installed: bool = True
) -> tuple[MagicMock, MagicMock]:
    """POST install_missing_packages with source="server" using a mocked
    package manager.  Returns (mock_create, mock_pkg_manager)."""
    mock_pkg_manager = MagicMock()
    mock_pkg_manager.is_manager_installed.return_value = manager_installed
    mock_pkg_manager.install = AsyncMock()

    with patch(
        "marimo._runtime.packages.package_managers.create_package_manager",
        return_value=mock_pkg_manager,
    ) as mock_create:
        response = client.post(
            "/api/kernel/install_missing_packages",
            headers=HEADERS,
            json={
                "manager": "pip",
                "versions": {"nbformat": ""},
                "source": "server",
            },
        )
        assert response.status_code == 200, response.text
        assert "success" in response.json()

    return mock_create, mock_pkg_manager


@with_session(SESSION_ID)
def test_install_missing_packages_server_source(client: TestClient) -> None:
    # source="server" routes the install to the server's Python env directly
    # rather than dispatching to the kernel.
    mock_create, mock_pkg_manager = _mock_server_install(client)
    mock_create.assert_called_once_with("pip", python_exe=sys.executable)
    mock_pkg_manager.install.assert_awaited_once_with("nbformat", version=None)


@with_session(SESSION_ID)
def test_install_missing_packages_server_source_manager_not_installed(
    client: TestClient,
) -> None:
    # When the package manager is not installed, alert_not_installed is called
    # and no packages are installed.
    _, mock_pkg_manager = _mock_server_install(client, manager_installed=False)
    mock_pkg_manager.alert_not_installed.assert_called_once()
    mock_pkg_manager.install.assert_not_awaited()


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
