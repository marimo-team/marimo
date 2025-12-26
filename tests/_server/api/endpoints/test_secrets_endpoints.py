# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

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
    response = client.post(
        "/api/secrets/keys",
        headers=HEADERS,
        json={"requestId": "test-request-id"},
    )
    assert response.status_code == 200, response.text
    assert "success" in response.json()


@with_session(SESSION_ID)
def test_create_secret(client: TestClient) -> None:
    """Test secret creation and verify write_secret is called."""
    with patch(
        "marimo._server.api.endpoints.secrets.write_secret"
    ) as mock_write_secret:
        response = client.post(
            "/api/secrets/create",
            headers=HEADERS,
            json={
                "key": "TEST_SECRET",
                "value": "secret_value",
                "provider": "env",
                "name": "test_secret",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["success"] is True
        assert mock_write_secret.called


@with_session(SESSION_ID)
def test_delete_secret_not_implemented(client: TestClient) -> None:
    """Test that delete secret endpoint raises NotImplementedError."""
    response = client.post(
        "/api/secrets/delete", headers=HEADERS, json={"key": "test_secret"}
    )
    assert response.status_code == 501, response.text


@with_read_session(SESSION_ID)
def test_secrets_forbidden_in_read_mode(client: TestClient) -> None:
    """Test that secret operations are forbidden in read mode."""
    response = client.post(
        "/api/secrets/keys",
        headers=HEADERS,
        json={"requestId": "test-request-id"},
    )
    assert response.status_code == 401, response.text

    response = client.post(
        "/api/secrets/create",
        headers=HEADERS,
        json={
            "key": "TEST_SECRET",
            "value": "test_value",
            "provider": "env",
            "name": "test",
        },
    )
    assert response.status_code == 401, response.text


@with_session(SESSION_ID)
def test_create_secret_write_failure(client: TestClient) -> None:
    """Test handling when write_secret fails."""
    with patch(
        "marimo._server.api.endpoints.secrets.write_secret",
        side_effect=Exception("Write failed"),
    ):
        with pytest.raises(Exception, match="Write failed"):
            client.post(
                "/api/secrets/create",
                headers=HEADERS,
                json={
                    "key": "TEST_SECRET",
                    "value": "test_value",
                    "provider": "env",
                    "name": "test",
                },
            )
