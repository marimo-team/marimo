# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from tests._server.conftest import get_session_manager
from tests._server.mocks import token_header, with_session

if TYPE_CHECKING:
    from starlette.testclient import TestClient

SESSION_ID = "session-123"
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    **token_header("fake-token"),
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
        json={"include_markdown": False},
    )
    body = response.json()
    files = body["files"]
    assert len(files) == 1
    assert files[0]["path"] == current_filename
    # Check that new fields are present
    assert "hasMore" in body
    assert "fileCount" in body
    assert body["hasMore"] is False
    assert body["fileCount"] == 1


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
        json={"sessionId": SESSION_ID},
    )
    assert response.status_code == 200
    assert response.json() == {"files": []}
    assert get_session_manager(client).get_session(SESSION_ID) is None


@with_session(SESSION_ID)
def test_open_tutorial(client: TestClient) -> None:
    response = client.post(
        "/api/home/tutorial/open",
        headers=HEADERS,
        json={"tutorialId": "intro"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "intro.py"
    assert data["path"].endswith("intro.py")


@with_session(SESSION_ID)
def test_cant_open_non_tutorial(client: TestClient) -> None:
    response = client.post(
        "/api/home/tutorial/open",
        headers=HEADERS,
        json={"tutorialId": "non-tutorial"},
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Tutorial not found"}


@with_session(SESSION_ID)
def test_tutorial_file_accessible_after_open(client: TestClient) -> None:
    """Test that a tutorial file can be accessed after being opened.

    This is an integration test for issue #7424.
    When a tutorial is opened via the endpoint, it creates a file in a temp
    directory. This test verifies that the file router can access that
    file despite it being outside the base directory.
    """
    from marimo._server.file_router import LazyListOfFilesAppFileRouter

    # Open a tutorial
    response = client.post(
        "/api/home/tutorial/open",
        headers=HEADERS,
        json={"tutorialId": "intro"},
    )
    assert response.status_code == 200
    data = response.json()
    tutorial_path = data["path"]

    # Verify the temp directory was registered with the file router
    session_manager = get_session_manager(client)
    file_router = session_manager.file_router

    # Only test for directory-based routers
    if isinstance(file_router, LazyListOfFilesAppFileRouter):
        assert file_router.is_file_in_allowed_temp_dir(tutorial_path)

    # Try to get a file manager for the tutorial file
    # This should not raise an HTTPException about being outside the directory
    file_manager = session_manager.app_manager(tutorial_path)
    assert file_manager is not None
    assert file_manager.path == tutorial_path
