# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any, cast

from marimo._server.api.deps import AppState
from marimo._server.api.endpoints.assets import _inject_service_worker
from marimo._server.api.utils import parse_title
from marimo._server.file_router import AppFileRouter
from tests._server.mocks import token_header, with_file_router

if TYPE_CHECKING:
    from starlette.testclient import TestClient


def test_index(client: TestClient) -> None:
    session_manager = AppState.from_app(cast(Any, client.app)).session_manager

    # Login page
    response = client.get("/")  # no header
    assert response.status_code == 200, response.text
    assert "Login" in response.text
    assert "marimo-filename" not in response.text

    response = client.get("/", headers=token_header())
    assert response.status_code == 200, response.text
    content = response.text
    filename = session_manager.file_router.get_unique_file_key()
    title = parse_title(filename)
    assert f"<marimo-filename hidden>{filename}</marimo-filename>" in content
    assert filename is not None
    assert filename in content
    assert "<marimo-mode data-mode='edit'" in content
    assert f"<title>{title}</title>" in content

    # Check for /public file service worker
    assert "public-files-sw.js" in content


@with_file_router(AppFileRouter.from_files([]))
def test_index_when_empty(client: TestClient) -> None:
    # Login page
    response = client.get("/")  # no header
    assert response.status_code == 200, response.text
    assert "Login" in response.text
    assert "marimo-filename" not in response.text

    response = client.get("/", headers=token_header())
    assert response.status_code == 200, response.text
    content = response.text
    assert "<marimo-filename hidden></marimo-filename>" in content
    assert "<marimo-mode data-mode='home'" in content
    assert "<title>marimo</title>" in content


@with_file_router(AppFileRouter.new_file())
def test_index_when_new_file(client: TestClient) -> None:
    # Login page
    response = client.get("/")  # no header
    assert response.status_code == 200, response.text
    assert "Login" in response.text
    assert "marimo-filename" not in response.text

    response = client.get("/", headers=token_header())
    assert response.status_code == 200, response.text
    content = response.text
    assert "<marimo-filename hidden></marimo-filename>" in content
    assert "<marimo-mode data-mode='edit'" in content
    assert "<title>marimo</title>" in content


TEMP_DIR = TemporaryDirectory()


@with_file_router(AppFileRouter.from_directory(TEMP_DIR.name))
def test_index_with_directory(client: TestClient) -> None:
    response = client.get("/", headers=token_header())
    assert response.status_code == 200, response.text
    content = response.text
    assert "<marimo-filename" in content
    assert "<marimo-mode data-mode='home'" in content
    assert "<title>marimo</title>" in content


def test_favicon(client: TestClient) -> None:
    response = client.get("/favicon.ico")
    assert response.status_code == 200, response.text
    content_type = response.headers["content-type"]
    assert (
        content_type == "image/x-icon"
        or content_type == "image/vnd.microsoft.icon"
    )


def test_unknown_file(client: TestClient) -> None:
    response = client.get("/unknown_file")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"detail": "Not Found"}


def test_vfile(client: TestClient) -> None:
    response = client.get("/@file/example.txt")
    assert response.status_code == 401, response.text

    response = client.get("/@file/empty.txt", headers=token_header())
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.content == b""

    response = client.get("/@file/bad.txt", headers=token_header())
    assert response.status_code == 404, response.text
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"detail": "Invalid virtual file request"}


def test_public_file_serving(client: TestClient) -> None:
    # Setup app state with a mock notebook
    app_state = AppState.from_app(cast(Any, client.app))
    file_key = app_state.session_manager.file_router.get_unique_file_key()
    assert file_key is not None
    assert file_key.endswith(".py")

    # Create a test file in a public directory
    notebook_dir = Path(file_key).parent
    public_dir = notebook_dir / "public"
    public_dir.mkdir(parents=True, exist_ok=True)
    test_file = public_dir / "test.txt"
    test_file.write_text("test content")

    # Test without notebook ID header
    response = client.get("/public/test.txt", headers=token_header())
    assert response.status_code == 404

    # Test with notebook ID header
    headers = {**token_header(), "X-Notebook-Id": file_key}
    response = client.get("/public/test.txt", headers=headers)
    assert response.status_code == 200
    assert response.text == "test content"

    # Test non-existent file
    response = client.get("/public/nonexistent.txt", headers=headers)
    assert response.status_code == 404

    # Cleanup
    test_file.unlink()


def test_service_worker(client: TestClient) -> None:
    response = client.get("/public-files-sw.js")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/javascript"
    assert "self.addEventListener('fetch'" in response.text
    assert "X-Notebook-Id" in response.text


def test_public_file_security(client: TestClient) -> None:
    # Setup app state
    app_state = AppState.from_app(cast(Any, client.app))
    file_key = app_state.session_manager.file_router.get_unique_file_key()
    assert file_key is not None
    assert file_key.endswith(".py")

    # Setup notebook and directories
    notebook_dir = Path(file_key).parent
    public_dir = notebook_dir / "public"
    secret_dir = notebook_dir / "secret"
    public_dir.mkdir(parents=True, exist_ok=True)
    secret_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Create test files
        (public_dir / "safe.txt").write_text("public content")
        (secret_dir / "secret.txt").write_text("secret content")

        # Create a symlink in public pointing outside
        os.symlink(
            str(secret_dir / "secret.txt"), str(public_dir / "symlink.txt")
        )

        app_manager = app_state.session_manager.app_manager(file_key)
        app_manager.filename = str(notebook_dir / "notebook.py")

        headers = {**token_header(), "X-Notebook-Id": file_key}

        # Test normal file access
        response = client.get("/public/safe.txt", headers=headers)
        assert response.status_code == 200
        assert response.text == "public content"

        # Test path traversal attempt
        response = client.get(
            "/public/data/../../secret/secret.txt", headers=headers
        )
        assert response.status_code == 404

        # Test symlink attempt
        response = client.get("/public/symlink.txt", headers=headers)
        assert response.status_code == 403

    finally:
        # Cleanup
        shutil.rmtree(public_dir, ignore_errors=True)
        shutil.rmtree(secret_dir, ignore_errors=True)


def test_inject_service_worker() -> None:
    assert (
        "const notebookId = 'path%2Fto%2Fnotebook.py';"
        in _inject_service_worker("<body></body>", "path/to/notebook.py")
    )
    assert (
        "const notebookId = 'c%3A%5Cpath%5Cto%5Cnotebook.py';"
        in _inject_service_worker("<body></body>", r"c:\path\to\notebook.py")
    )
