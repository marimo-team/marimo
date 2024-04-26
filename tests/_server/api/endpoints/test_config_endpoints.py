# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from tests._server.conftest import get_user_config_manager
from tests._server.mocks import with_session

if TYPE_CHECKING:
    from starlette.testclient import TestClient

SESSION_ID = "session-123"
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    "Marimo-Server-Token": "fake-token",
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
