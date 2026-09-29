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
                    "id": "data-analysis",
                    "title": "Data analysis",
                    "description": "Load, filter, query, and clean data.",
                },
                {
                    "id": "visualization",
                    "title": "Visualization",
                    "description": "Create interactive charts and dashboards.",
                },
                {
                    "id": "apps-and-reports",
                    "title": "Apps and reports",
                    "description": "Build useful tools, forms, and reusable reports.",
                },
            ],
            "templates": [
                {
                    "id": "load-csv",
                    "title": "Explore a CSV",
                    "description": "Upload a CSV or start with sample rows, then inspect it in a table.",
                    "categoryIds": ["data-analysis"],
                    "previewUrl": "/api/templates/load-csv/preview",
                },
                {
                    "id": "filter-data",
                    "title": "Filter and summarize data",
                    "description": "Filter sample sales and summarize the rows you select.",
                    "categoryIds": ["data-analysis"],
                    "previewUrl": "/api/templates/filter-data/preview",
                },
                {
                    "id": "query-with-duckdb",
                    "title": "Query data with SQL",
                    "description": "Start with sample sales and an editable DuckDB query.",
                    "categoryIds": ["data-analysis"],
                    "previewUrl": "/api/templates/query-with-duckdb/preview",
                },
                {
                    "id": "data-explorer",
                    "title": "Create an interactive chart",
                    "description": "Explore fuel economy with filters, tooltips, and zoom.",
                    "categoryIds": ["visualization"],
                    "previewUrl": "/api/templates/data-explorer/preview",
                },
                {
                    "id": "dashboard",
                    "title": "Build a dashboard",
                    "description": "Combine a filter, key metrics, a chart, and a detail table.",
                    "categoryIds": ["visualization"],
                    "previewUrl": "/api/templates/dashboard/preview",
                },
                {
                    "id": "interactive-controls",
                    "title": "Build a calculator",
                    "description": "Estimate a monthly budget from a few assumptions.",
                    "categoryIds": ["apps-and-reports"],
                    "previewUrl": "/api/templates/interactive-controls/preview",
                },
                {
                    "id": "clean-data",
                    "title": "Clean and transform data",
                    "description": "Fill missing values and calculate derived columns with Polars.",
                    "categoryIds": ["data-analysis"],
                    "previewUrl": "/api/templates/clean-data/preview",
                },
                {
                    "id": "data-entry-form",
                    "title": "Create a data-entry form",
                    "description": "Collect related inputs and turn them into a structured record.",
                    "categoryIds": ["apps-and-reports"],
                    "previewUrl": "/api/templates/data-entry-form/preview",
                },
                {
                    "id": "parameterized-report",
                    "title": "Create a parameterized report",
                    "description": "Generate a reusable status report from a few parameters.",
                    "categoryIds": ["apps-and-reports"],
                    "previewUrl": "/api/templates/parameterized-report/preview",
                },
            ],
            "featuredIds": [
                "load-csv",
                "filter-data",
                "query-with-duckdb",
                "data-explorer",
                "dashboard",
                "interactive-controls",
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
        "/proxy/api/templates/load-csv/preview",
        "/proxy/api/templates/filter-data/preview",
        "/proxy/api/templates/query-with-duckdb/preview",
        "/proxy/api/templates/data-explorer/preview",
        "/proxy/api/templates/dashboard/preview",
        "/proxy/api/templates/interactive-controls/preview",
        "/proxy/api/templates/clean-data/preview",
        "/proxy/api/templates/data-entry-form/preview",
        "/proxy/api/templates/parameterized-report/preview",
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
    assert 'label="Team size"' in source

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
