# Copyright 2024 Marimo. All rights reserved.
import sys

import pytest
from starlette.testclient import TestClient

from tests._server.conftest import get_session_manager
from tests._server.mocks import with_session

SESSION_ID = "session-123"
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    "Marimo-Server-Token": "fake-token",
}


@with_session(SESSION_ID)
def test_workspace_files(client: TestClient) -> None:
    current_filename = get_session_manager(
        client
    ).file_router.get_unique_file_key()
    assert current_filename

    response = client.post(
        "/api/home/workspace_files",
        headers=HEADERS,
    )
    body = response.json()
    files = body["files"]
    assert len(files) == 1
    assert files[0]["path"] == current_filename


@with_session(SESSION_ID)
def test_workspace_files_no_files(client: TestClient) -> None:
    response = client.post(
        "/api/home/recent_files",
        headers=HEADERS,
    )
    body = response.json()
    files = body["files"]
    assert files is not None


@with_session(SESSION_ID)
def test_running_notebooks(client: TestClient) -> None:
    current_filename = get_session_manager(
        client
    ).file_router.get_unique_file_key()
    assert current_filename

    response = client.post(
        "/api/home/running_notebooks",
        headers=HEADERS,
    )
    body = response.json()
    files = body["files"]
    assert len(files) == 1
    assert files[0]["path"] == current_filename


# TODO: Debug on Windows
@pytest.mark.skipif(sys.platform == "win32", reason="Failing on Windows CI")
@with_session(SESSION_ID, auto_shutdown=False)
def test_shutdown_session(client: TestClient) -> None:
    response = client.post(
        "/api/home/shutdown_session",
        headers=HEADERS,
        json={"session_id": SESSION_ID},
    )
    assert response.status_code == 200
    assert response.json() == {"files": []}
    assert get_session_manager(client).get_session(SESSION_ID) is None
