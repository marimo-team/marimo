# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

from inline_snapshot import snapshot

from tests._server.mocks import (
    get_session_manager,
    token_header,
    with_session,
)

if TYPE_CHECKING:
    from starlette.testclient import TestClient

SESSION_ID = "session-123"
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    **token_header("fake-token"),
}


@with_session(SESSION_ID)
def test_list_templates(client: TestClient) -> None:
    response = client.get("/api/templates/", headers=HEADERS)

    assert response.status_code == 200
    assert response.json() == snapshot(
        {
            "categories": [
                {
                    "id": "getting-started",
                    "title": "Getting started",
                    "description": "Learn core marimo workflows with small interactive notebooks.",
                },
                {
                    "id": "working-with-data",
                    "title": "Working with data",
                    "description": "Explore data with reactive controls and clear outputs.",
                },
            ],
            "templates": [
                {
                    "id": "interactive-controls",
                    "title": "Build an interactive control",
                    "description": "Connect a slider to reactive Markdown output.",
                    "categoryIds": ["getting-started"],
                    "previewUrl": "/api/templates/interactive-controls/preview",
                },
                {
                    "id": "filter-data",
                    "title": "Filter tabular data",
                    "description": "Filter embedded records and inspect them in a table.",
                    "categoryIds": ["working-with-data"],
                    "previewUrl": "/api/templates/filter-data/preview",
                },
                {
                    "id": "query-with-duckdb",
                    "title": "Query data with DuckDB",
                    "description": "Parameterize a SQL query with a reactive control.",
                    "categoryIds": ["working-with-data"],
                    "previewUrl": "/api/templates/query-with-duckdb/preview",
                },
                {
                    "id": "data-explorer",
                    "title": "Explore a small dataset",
                    "description": "Select a city and inspect its embedded sample data.",
                    "categoryIds": ["working-with-data"],
                    "previewUrl": "/api/templates/data-explorer/preview",
                },
            ],
            "featuredIds": [
                "interactive-controls",
                "filter-data",
                "query-with-duckdb",
            ],
        }
    )


@with_session(SESSION_ID)
def test_template_preview(client: TestClient) -> None:
    response = client.get(
        "/api/templates/interactive-controls/preview", headers=HEADERS
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "public, max-age=3600"
    assert response.content.startswith(b"\x89PNG")


@with_session(SESSION_ID)
def test_list_templates_uses_base_url(client: TestClient) -> None:
    original_base_url = client.app.state.base_url
    client.app.state.base_url = "/proxy"
    try:
        response = client.get("/api/templates/", headers=HEADERS)
    finally:
        client.app.state.base_url = original_base_url

    assert response.status_code == 200
    assert [item["previewUrl"] for item in response.json()["templates"]] == [
        "/proxy/api/templates/interactive-controls/preview",
        "/proxy/api/templates/filter-data/preview",
        "/proxy/api/templates/query-with-duckdb/preview",
        "/proxy/api/templates/data-explorer/preview",
    ]


@with_session(SESSION_ID)
def test_unknown_template_preview(client: TestClient) -> None:
    response = client.get("/api/templates/missing/preview", headers=HEADERS)

    assert response.status_code == 404
    assert response.json() == {"detail": "Template 'missing' not found"}


@with_session(SESSION_ID)
def test_launch_template(client: TestClient) -> None:
    response = client.post(
        "/api/templates/interactive-controls/launch", headers=HEADERS
    )

    assert response.status_code == 200
    file_key = response.json()["fileKey"]
    source = get_session_manager(client).templates.resolve_launch(file_key)
    assert source is not None
    assert 'label="Number of stars"' in source

    page = client.get(f"/?file={quote(file_key)}", headers=HEADERS)
    assert page.status_code == 200
    assert "<marimo-filename hidden></marimo-filename>" in page.text
    assert '"width": "medium"' in page.text


@with_session(SESSION_ID)
def test_unknown_template_launch(client: TestClient) -> None:
    response = client.post("/api/templates/missing/launch", headers=HEADERS)

    assert response.status_code == 404
    assert response.json() == {"detail": "Template 'missing' not found"}


def test_template_launch_requires_edit_authorization(
    client: TestClient,
) -> None:
    response = client.post("/api/templates/interactive-controls/launch")

    assert response.status_code == 401
