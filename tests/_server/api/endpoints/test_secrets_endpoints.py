# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from marimo._types.ids import SessionId
from tests._server.mocks import token_header, with_read_session, with_session

if TYPE_CHECKING:
    from starlette.testclient import TestClient

SESSION_ID = SessionId("session-123")
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    **token_header("fake-token"),
}


@with_session(SESSION_ID)
def test_list_secret_keys(client: TestClient) -> None:
    """Test secret keys listing."""
    response = client.post("/api/secrets/keys", headers=HEADERS, json={})
    assert response.status_code == 200, response.text
    assert "success" in response.json()


@with_session(SESSION_ID)
@patch("marimo._secrets.secrets.write_secret")
def test_create_secret(
    client: TestClient, mock_write_secret: MagicMock
) -> None:
    """Test secret creation and verify write_secret is called."""
    response = client.post(
        "/api/secrets/create",
        headers=HEADERS,
        json={"name": "test_secret", "value": "secret_value"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True
    assert mock_write_secret.called


@with_session(SESSION_ID)
def test_delete_secret_not_implemented(client: TestClient) -> None:
    """Test that delete secret endpoint raises NotImplementedError."""
    response = client.post(
        "/api/secrets/delete", headers=HEADERS, json={"name": "test_secret"}
    )
    assert response.status_code == 500, response.text


@with_read_session(SESSION_ID)
def test_secrets_forbidden_in_read_mode(client: TestClient) -> None:
    """Test that secret operations are forbidden in read mode."""
    response = client.post("/api/secrets/keys", headers=HEADERS, json={})
    assert response.status_code == 401, response.text

    response = client.post(
        "/api/secrets/create",
        headers=HEADERS,
        json={"name": "test", "value": "test"},
    )
    assert response.status_code == 401, response.text


@with_session(SESSION_ID)
@patch("marimo._secrets.secrets.write_secret")
def test_create_secret_write_failure(
    client: TestClient, mock_write_secret: MagicMock
) -> None:
    """Test handling when write_secret fails."""
    mock_write_secret.side_effect = Exception("Write failed")
    response = client.post(
        "/api/secrets/create",
        headers=HEADERS,
        json={"name": "test", "value": "test"},
    )
    assert response.status_code == 500, response.text
