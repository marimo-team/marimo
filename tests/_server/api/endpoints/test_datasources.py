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
def test_preview_column(client: TestClient) -> None:
    response = client.post(
        "/api/datasources/preview_column",
        headers=HEADERS,
        json={
            "source_type": "connection",
            "source": "test_source",
            "table_name": "test_table",
            "column_name": "test_column",
        },
    )
    assert response.status_code == 200, response.text
    content = response.json()
    assert content["success"] is True


@with_session(SESSION_ID)
def test_preview_sql_table(client: TestClient) -> None:
    response = client.post(
        "/api/datasources/preview_sql_table",
        headers=HEADERS,
        json={
            "request_id": "test_request_id",
            "engine": "test_engine",
            "database": "test_db",
            "schema": "test_schema",
            "table_name": "test_table",
        },
    )
    assert response.status_code == 200, response.text
    content = response.json()
    assert content["success"] is True


@with_read_session(SESSION_ID)
def test_fails_in_read_mode(client: TestClient) -> None:
    response = client.post(
        "/api/datasources/preview_column",
        headers=HEADERS,
        json={
            "source_type": "connection",
            "source": "test_source",
            "table_name": "test_table",
            "column_name": "test_column",
        },
    )
    assert response.status_code == 401

    response = client.post(
        "/api/datasources/preview_sql_table",
        headers=HEADERS,
        json={
            "request_id": "test_request_id",
            "engine": "test_engine",
            "database": "test_db",
            "schema": "test_schema",
            "table_name": "test_table",
        },
    )
    assert response.status_code == 401
