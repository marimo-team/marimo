# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from tests._server.api.endpoints.ws_helpers import receive_until
from tests._server.mocks import token_header, with_session

HAS_FORMATTER = DependencyManager.ruff.has() or DependencyManager.black.has()

if TYPE_CHECKING:
    from starlette.testclient import TestClient

SESSION_ID = "session-123"
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    **token_header("fake-token"),
}


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
    # pytest.mark.parametrize doesn't work with @with_session
    for suffix, filename in (
        (".py", "notebook.py"),
        (".md", "notebook.md.py"),
        (".qmd", "notebook.qmd.py"),
    ):
        with (
            patch(
                "marimo._server.api.endpoints.editing.DefaultFormatter.format",
                new=AsyncMock(return_value={"cell-123": "x = 1"}),
            ) as mock_format,
            patch(
                "marimo._server.api.endpoints.editing.AppState.require_current_session"
            ) as mock_require_session,
        ):
            mock_session = MagicMock()
            mock_session.app_file_manager.path = f"notebook{suffix}"
            mock_require_session.return_value = mock_session
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
            mock_format.assert_awaited_once_with({"cell-123": "x=1"}, filename)


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
def test_install_missing_packages_server_source(client: TestClient) -> None:
    install_packages = AsyncMock()
    with patch(
        "marimo._server.api.endpoints.editing.install_packages_on_server",
        new=install_packages,
    ):
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

    install_packages.assert_awaited_once_with({"nbformat": ""})


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

        message = receive_until("focus-cell", websocket)
        assert message == {
            "op": "focus-cell",
            "data": {"op": "focus-cell", "cell_id": cell_id},
        }
