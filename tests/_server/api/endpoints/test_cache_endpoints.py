# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

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
def test_clear_cache(client: TestClient) -> None:
    """Test cache clear operation."""
    response = client.post("/api/cache/clear", headers=HEADERS, json={})
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True


@with_session(SESSION_ID)
def test_get_cache_info(client: TestClient) -> None:
    """Test cache info retrieval."""
    response = client.post("/api/cache/info", headers=HEADERS, json={})
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True


@with_read_session(SESSION_ID)
def test_cache_forbidden_in_read_mode(client: TestClient) -> None:
    """Test that cache operations are forbidden in read mode."""
    response = client.post("/api/cache/clear", headers=HEADERS, json={})
    assert response.status_code == 401, response.text

    response = client.post("/api/cache/info", headers=HEADERS, json={})
    assert response.status_code == 401, response.text
