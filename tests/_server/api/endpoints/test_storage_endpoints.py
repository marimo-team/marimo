# Copyright 2026 Marimo. All rights reserved.
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
def test_list_entries(client: TestClient) -> None:
    response = client.post(
        "/api/storage/list_entries",
        headers=HEADERS,
        json={
            "requestId": "test_request_id",
            "namespace": "my_store",
            "limit": 100,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True


@with_session(SESSION_ID)
def test_list_entries_with_prefix(client: TestClient) -> None:
    response = client.post(
        "/api/storage/list_entries",
        headers=HEADERS,
        json={
            "requestId": "test_request_id",
            "namespace": "my_store",
            "limit": 50,
            "prefix": "data/images/",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True


@with_session(SESSION_ID)
def test_download(client: TestClient) -> None:
    response = client.post(
        "/api/storage/download",
        headers=HEADERS,
        json={
            "requestId": "test_request_id",
            "namespace": "my_store",
            "path": "data/file.csv",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True


@with_read_session(SESSION_ID)
def test_list_entries_fails_in_read_mode(client: TestClient) -> None:
    response = client.post(
        "/api/storage/list_entries",
        headers=HEADERS,
        json={
            "requestId": "test_request_id",
            "namespace": "my_store",
            "limit": 100,
        },
    )
    assert response.status_code == 401


@with_read_session(SESSION_ID)
def test_download_fails_in_read_mode(client: TestClient) -> None:
    response = client.post(
        "/api/storage/download",
        headers=HEADERS,
        json={
            "requestId": "test_request_id",
            "namespace": "my_store",
            "path": "data/file.csv",
        },
    )
    assert response.status_code == 401
