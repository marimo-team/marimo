# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from tests._server.mocks import token_header, with_read_session, with_session

if TYPE_CHECKING:
    from starlette.testclient import TestClient

SESSION_ID = "session-123"
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    **token_header("fake-token"),
}


@with_session(SESSION_ID)
def test_validate_sql(client: TestClient) -> None:
    response = client.post(
        "/api/sql/validate",
        headers=HEADERS,
        json={
            "requestId": "test_request_id",
            "engine": "test_engine",
            "query": "SELECT * FROM test",
        },
    )
    assert response.status_code == 200, response.text


@with_read_session(SESSION_ID)
def test_fails_in_read_mode(client: TestClient) -> None:
    response = client.post(
        "/api/sql/validate",
        headers=HEADERS,
        json={
            "requestId": "test_request_id",
            "engine": "test_engine",
            "query": "SELECT * FROM test",
        },
    )
    assert response.status_code == 401
