# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo import __version__
from tests._server.conftest import get_session_manager
from tests._server.mocks import with_session
from tests.mocks import snapshotter

if TYPE_CHECKING:
    from starlette.testclient import TestClient

snapshot = snapshotter(__file__)

SESSION_ID = "session-123"
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    "Marimo-Server-Token": "fake-token",
}


@with_session(SESSION_ID)
def test_export_html(client: TestClient) -> None:
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session
    session.app_file_manager.filename = "test.py"
    response = client.post(
        "/api/export/html",
        headers=HEADERS,
        json={
            "download": False,
            "files": [],
            "include_code": True,
        },
    )
    body = response.text
    assert '<marimo-code hidden=""></marimo-code>' not in body


@with_session(SESSION_ID)
def test_export_html_no_code(client: TestClient) -> None:
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session
    session.app_file_manager.filename = "test.py"
    response = client.post(
        "/api/export/html",
        headers=HEADERS,
        json={
            "download": False,
            "files": [],
            "include_code": False,
        },
    )
    body = response.text
    assert '<marimo-code hidden=""></marimo-code>' in body


@with_session(SESSION_ID)
def test_export_script(client: TestClient) -> None:
    response = client.post(
        "/api/export/script",
        headers=HEADERS,
        json={
            "download": False,
        },
    )
    assert response.status_code == 200
    assert "__generated_with = " in response.text


@with_session(SESSION_ID)
def test_export_markdown(client: TestClient) -> None:
    response = client.post(
        "/api/export/markdown",
        headers=HEADERS,
        json={
            "download": False,
        },
    )
    assert response.status_code == 200
    assert f"marimo-version: {__version__}" in response.text
    assert "```{.python.marimo}" in response.text
