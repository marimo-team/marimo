# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from tests._server.conftest import (
    get_session_manager,
    get_user_config_manager,
)
from tests._server.mocks import token_header, with_session

if TYPE_CHECKING:
    import pytest
    from starlette.testclient import TestClient


SESSION_ID = "session-123"
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    **token_header("fake-token"),
}


def test_save_user_config_no_session(client: TestClient) -> None:
    user_config_manager = get_user_config_manager(client)
    response = client.post(
        "/api/kernel/save_user_config",
        headers=HEADERS,
        json={
            "config": user_config_manager.get_config(),
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert "success" in response.json()


@with_session(SESSION_ID)
def test_save_user_config_with_session(client: TestClient) -> None:
    user_config_manager = get_user_config_manager(client)
    response = client.post(
        "/api/kernel/save_user_config",
        headers=HEADERS,
        json={
            "config": user_config_manager.get_config(),
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert "success" in response.json()


@with_session(SESSION_ID)
def test_save_user_config_with_partial_config(client: TestClient) -> None:
    """
    Test that save_user_config endpoint works correctly with partial config

    This is a regression test for the KeyError: 'output_max_bytes' bug.
    Before the fix, sending partial config would cause runtime errors when
    the kernel tried to access missing config fields.
    """
    # Create a partial config that's missing required runtime fields
    partial_config = {
        "display": {
            "theme": "light",
        },
    }

    response = client.post(
        "/api/kernel/save_user_config",
        headers=HEADERS,
        json={
            "config": partial_config,
        },
    )

    # Verify the endpoint succeeds
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert "success" in response.json()


def test_save_user_config_starts_lsp_when_ty_enabled(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = False

    async def mock_start_lsp_server() -> None:
        nonlocal called
        called = True

    session_manager = get_session_manager(client)
    monkeypatch.setattr(
        session_manager, "start_lsp_server", mock_start_lsp_server
    )

    response = client.post(
        "/api/kernel/save_user_config",
        headers=HEADERS,
        json={
            "config": {
                "completion": {"copilot": False},
                "language_servers": {"ty": {"enabled": True}},
            },
        },
    )

    assert response.status_code == 200, response.text
    assert called is True
