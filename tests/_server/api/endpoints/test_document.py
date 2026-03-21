# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from tests._server.mocks import token_header, with_session

if TYPE_CHECKING:
    from starlette.testclient import TestClient

SESSION_ID = "session-123"
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    **token_header("fake-token"),
}


@with_session(SESSION_ID)
def test_document_events_move(client: TestClient) -> None:
    response = client.post(
        "/api/document/events",
        headers=HEADERS,
        json={
            "events": [
                {"type": "cell-created", "id": "a", "code": "x = 1"},
                {"type": "cell-created", "id": "b", "code": "y = 2"},
                {"type": "cell-moved", "id": "b", "after": None},
            ],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True


@with_session(SESSION_ID)
def test_document_events_code_changed(client: TestClient) -> None:
    response = client.post(
        "/api/document/events",
        headers=HEADERS,
        json={
            "events": [
                {"type": "cell-created", "id": "a", "code": "x = 1"},
                {"type": "code-changed", "id": "a", "code": "x = 42"},
            ],
        },
    )
    assert response.status_code == 200, response.text


@with_session(SESSION_ID)
def test_document_events_empty(client: TestClient) -> None:
    response = client.post(
        "/api/document/events",
        headers=HEADERS,
        json={"events": []},
    )
    assert response.status_code == 200, response.text
