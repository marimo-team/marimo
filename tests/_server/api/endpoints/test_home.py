# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from marimo._server.file_router import AppFileRouter
from marimo._server.models.home import MarimoFile
from marimo._session.model import SessionMode
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
def test_workspace_files_in_run_mode(client: TestClient) -> None:
    session_manager = get_session_manager(client)
    session_manager.mode = SessionMode.RUN

    with tempfile.TemporaryDirectory() as temp_dir:
        marimo_file = Path(temp_dir) / "notebook.py"
        marimo_file.write_text("import marimo\napp = marimo.App()")

        non_marimo_file = Path(temp_dir) / "text.txt"
        non_marimo_file.write_text("This is not a marimo file")

        session_manager.file_router = AppFileRouter.from_directory(temp_dir)

        response = client.post(
            "/api/home/workspace_files",
            headers=HEADERS,
            json={"include_markdown": False},
        )
        body = response.json()
        files = body["files"]

        assert len(files) == 1
        assert body["root"] == temp_dir
        assert files[0]["path"] == marimo_file.name


@with_session(SESSION_ID)
def test_workspace_files_empty_directory(client: TestClient) -> None:
    session_manager = get_session_manager(client)
    session_manager.mode = SessionMode.RUN

    with tempfile.TemporaryDirectory() as temp_dir:
        session_manager.file_router = AppFileRouter.from_directory(temp_dir)

        response = client.post(
            "/api/home/workspace_files",
            headers=HEADERS,
            json={"include_markdown": False},
        )
        body = response.json()
        files = body["files"]

    assert len(files) == 0


@with_session(SESSION_ID)
def test_workspace_files_run_mode_allowlist(client: TestClient) -> None:
    session_manager = get_session_manager(client)
    session_manager.mode = SessionMode.RUN

    with tempfile.TemporaryDirectory() as temp_dir:
        file_one = Path(temp_dir) / "one.py"
        file_one.write_text("import marimo\napp = marimo.App()")
        file_two = Path(temp_dir) / "two.py"
        file_two.write_text("import marimo\napp = marimo.App()")

        marimo_files = [
            MarimoFile(
                name=file_one.name,
                path=str(file_one),
                last_modified=file_one.stat().st_mtime,
            ),
            MarimoFile(
                name=file_two.name,
                path=str(file_two),
                last_modified=file_two.stat().st_mtime,
            ),
        ]
        session_manager.file_router = AppFileRouter.from_files(
            marimo_files,
            directory=temp_dir,
            allow_single_file_key=False,
        )

        response = client.post(
            "/api/home/workspace_files",
            headers=HEADERS,
            json={"include_markdown": False},
        )
        body = response.json()
        files = body["files"]

        assert body["root"] == temp_dir
        assert {file["path"] for file in files} == {
            str(file_one),
            str(file_two),
        }


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


@with_session(SESSION_ID)
def test_running_notebooks_returns_relative_paths(client: TestClient) -> None:
    """Test that running_notebooks returns paths relative to file router directory.

    This is a regression test for the bug where `marimo edit subdirectory`
    would return paths like `subdirectory/notebook.py` instead of `notebook.py`.
    """
    from marimo._server.file_router import LazyListOfFilesAppFileRouter

    session_manager = get_session_manager(client)

    # Create a temp directory structure: /tmp/xxx/subdir/notebook.py
    with tempfile.TemporaryDirectory() as tmp_base:
        subdir = os.path.join(tmp_base, "subdir")
        os.makedirs(subdir)

        # Create a notebook file in the subdirectory
        notebook_path = os.path.join(subdir, "notebook.py")
        content = inspect.cleandoc(
            """
            import marimo
            app = marimo.App()

            @app.cell
            def __():
                return

            if __name__ == "__main__":
                app.run()
            """
        )
        with open(notebook_path, "w") as f:
            f.write(content)

        # Create a file router pointing to the subdirectory
        # This simulates `marimo edit subdir`
        file_router = LazyListOfFilesAppFileRouter(
            subdir, include_markdown=False
        )

        # Replace the session manager's file router
        original_file_router = session_manager.file_router
        session_manager.file_router = file_router

        # Update the session's filename to the absolute path of the notebook
        session = session_manager.get_session(SESSION_ID)
        assert session is not None
        original_filename = session.app_file_manager.filename
        session.app_file_manager.filename = notebook_path

        try:
            response = client.post(
                "/api/home/running_notebooks",
                headers=HEADERS,
            )
            body = response.json()
            files = body["files"]

            assert len(files) == 1
            # The path should be relative to the subdirectory, not the CWD
            # i.e., "notebook.py" not "subdir/notebook.py"
            assert files[0]["path"] == "notebook.py"
            assert files[0]["name"] == "notebook.py"
        finally:
            # Restore original state
            session_manager.file_router = original_file_router
            session.app_file_manager.filename = original_filename


@pytest.mark.skipif(sys.platform == "win32", reason="Failing on Windows CI")
@with_session(SESSION_ID, auto_shutdown=False)
def test_shutdown_session_returns_relative_paths(client: TestClient) -> None:
    """Test that shutdown_session returns paths relative to file router directory."""
    from marimo._server.file_router import LazyListOfFilesAppFileRouter

    session_manager = get_session_manager(client)

    # Create a second session to test shutdown returns correct paths
    # for remaining sessions
    with tempfile.TemporaryDirectory() as tmp_base:
        subdir = os.path.join(tmp_base, "subdir")
        os.makedirs(subdir)

        notebook_path = os.path.join(subdir, "notebook.py")
        content = inspect.cleandoc(
            """
            import marimo
            app = marimo.App()

            @app.cell
            def __():
                return

            if __name__ == "__main__":
                app.run()
            """
        )
        with open(notebook_path, "w") as f:
            f.write(content)

        file_router = LazyListOfFilesAppFileRouter(
            subdir, include_markdown=False
        )

        original_file_router = session_manager.file_router
        session_manager.file_router = file_router

        session = session_manager.get_session(SESSION_ID)
        assert session is not None
        original_filename = session.app_file_manager.filename
        session.app_file_manager.filename = notebook_path

        try:
            # Shutdown the session - response should have empty files
            # since we're shutting down the only session
            response = client.post(
                "/api/home/shutdown_session",
                headers=HEADERS,
                json={"sessionId": SESSION_ID},
            )
            assert response.status_code == 200
            # After shutdown, no sessions remain
            assert response.json() == {"files": []}
        finally:
            session_manager.file_router = original_file_router
            # Note: session is already shut down, so we don't restore filename


@pytest.mark.xfail(
    sys.platform == "win32",
    reason="Flaky on Windows - websocket cleanup may hang due to background threads. See #7774",
    strict=False,
)
def test_running_notebooks_handles_files_outside_directory(
    client: TestClient,
) -> None:
    """Test that files outside the directory still get pretty_path treatment."""
    from marimo._server.file_router import LazyListOfFilesAppFileRouter

    session_manager = get_session_manager(client)
    auth_token = session_manager.auth_token
    headers = token_header(auth_token)

    # Connect a session
    with client.websocket_connect(
        f"/ws?session_id={SESSION_ID}", headers=headers
    ) as websocket:
        data = websocket.receive_text()
        assert data

        # Create two separate temp directories
        with tempfile.TemporaryDirectory() as router_dir:
            with tempfile.TemporaryDirectory() as file_dir:
                # Create a notebook in file_dir (outside router_dir)
                notebook_path = os.path.join(file_dir, "outside.py")
                content = inspect.cleandoc(
                    """
                    import marimo
                    app = marimo.App()

                    @app.cell
                    def __():
                        return

                    if __name__ == "__main__":
                        app.run()
                    """
                )
                with open(notebook_path, "w") as f:
                    f.write(content)

                # Set up file router pointing to router_dir
                file_router = LazyListOfFilesAppFileRouter(
                    router_dir, include_markdown=False
                )

                original_file_router = session_manager.file_router
                session_manager.file_router = file_router

                session = session_manager.get_session(SESSION_ID)
                assert session is not None
                original_filename = session.app_file_manager.filename
                session.app_file_manager.filename = notebook_path

                try:
                    response = client.post(
                        "/api/home/running_notebooks",
                        headers=HEADERS,
                    )
                    body = response.json()
                    files = body["files"]

                    assert len(files) == 1
                    # File is outside directory, so it should use pretty_path
                    # which returns the path as-is or relative to CWD
                    # The important thing is it doesn't crash
                    assert files[0]["name"] == "outside.py"
                    # Path should contain the filename (exact path depends on CWD)
                    assert "outside.py" in files[0]["path"]
                finally:
                    session_manager.file_router = original_file_router
                    session.app_file_manager.filename = original_filename
