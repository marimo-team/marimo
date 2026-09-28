# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

from typing import TYPE_CHECKING

from inline_snapshot import snapshot

from tests._server.mocks import token_header, with_session

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
                    "id": "data-explorer",
                    "title": "Explore a small dataset",
                    "description": "Select a city and inspect its embedded sample data.",
                    "categoryIds": ["working-with-data"],
                    "previewUrl": "/api/templates/data-explorer/preview",
                },
            ],
            "featuredIds": ["interactive-controls"],
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
        "/proxy/api/templates/data-explorer/preview",
    ]


@with_session(SESSION_ID)
def test_unknown_template_preview(client: TestClient) -> None:
    response = client.get("/api/templates/missing/preview", headers=HEADERS)

    assert response.status_code == 404
    assert response.json() == {"detail": "Template 'missing' not found"}
