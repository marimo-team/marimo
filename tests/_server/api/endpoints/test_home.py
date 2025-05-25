# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from marimo._server.file_router import AppFileRouter
from marimo._server.model import SessionMode
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


@with_session(SESSION_ID)
def test_open_tutorial(client: TestClient) -> None:
    response = client.post(
        "/api/home/tutorial/open",
        headers=HEADERS,
        json={"tutorial_id": "intro"},
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
        json={"tutorial_id": "non-tutorial"},
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Tutorial not found"}


@with_session(SESSION_ID)
def test_workspace_files_in_run_mode(client: TestClient) -> None:
    """Test workspace files endpoint in run mode."""
    session_manager = get_session_manager(client)
    session_manager.mode = SessionMode.RUN

    # Create a temporary directory with some files
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a marimo file
        marimo_file = Path(temp_dir) / "notebook.py"
        marimo_file.write_text("import marimo\napp = marimo.App()")

        # Create a non-marimo file
        non_marimo_file = Path(temp_dir) / "text.txt"
        non_marimo_file.write_text("This is not a marimo file")

        # Set the file router to use the temp directory
        session_manager.file_router = AppFileRouter.from_directory(temp_dir)

        response = client.post(
            "/api/home/workspace_files",
            headers=HEADERS,
            json={"include_markdown": False},
        )
        body = response.json()
        files = body["files"]

        # In run mode, only marimo files should be returned
        assert len(files) == 1
        assert files[0]["path"] == str(marimo_file)


@with_session(SESSION_ID)
def test_workspace_files_in_edit_mode(client: TestClient) -> None:
    """Test workspace files endpoint in edit mode."""
    session_manager = get_session_manager(client)
    session_manager.mode = SessionMode.EDIT

    # Create a temporary directory with some files
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a marimo file
        marimo_file = Path(temp_dir) / "notebook.py"
        marimo_file.write_text("import marimo\napp = marimo.App()")

        # Create a non-marimo file
        non_marimo_file = Path(temp_dir) / "text.py"
        non_marimo_file.write_text("# This is not a marimo file")

        # Set the file router to use the temp directory
        session_manager.file_router = AppFileRouter.from_directory(temp_dir)

        response = client.post(
            "/api/home/workspace_files",
            headers=HEADERS,
            json={"include_markdown": False},
        )
        body = response.json()
        files = body["files"]

        # In edit mode, all files should be returned
        assert len(files) == 1
        assert str(marimo_file) == files[0]["path"]


@with_session(SESSION_ID)
def test_workspace_files_empty_directory(client: TestClient) -> None:
    """Test workspace files endpoint with an empty directory."""
    session_manager = get_session_manager(client)
    session_manager.mode = SessionMode.RUN

    # Create an empty temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        # Set the file router to use the temp directory
        session_manager.file_router = AppFileRouter.from_directory(temp_dir)

        response = client.post(
            "/api/home/workspace_files",
            headers=HEADERS,
            json={"include_markdown": False},
        )
        body = response.json()
        files = body["files"]

        # Empty directory should return empty list
        assert len(files) == 0
