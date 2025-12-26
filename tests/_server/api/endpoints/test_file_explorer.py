# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

import pytest

from marimo._utils.platform import is_windows
from tests._server.mocks import get_session_manager, token_header

if TYPE_CHECKING:
    from starlette.testclient import TestClient

HEADERS = {
    **token_header("fake-token"),
}

temp_dir = TemporaryDirectory()
test_dir = temp_dir.name
test_file_name = "test_file.txt"
test_file_path = os.path.join(test_dir, test_file_name)
test_content = "Hello, World!"
with open(test_file_path, "w") as f:
    f.write(test_content)


def test_list_files(client: TestClient) -> None:
    response = client.post(
        "/api/files/list_files",
        headers=HEADERS,
        json={"path": test_dir},
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert "files" in response.json()


def test_file_details(client: TestClient) -> None:
    response = client.post(
        "/api/files/file_details",
        headers=HEADERS,
        json={"path": test_file_path},
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert "file" in response.json()


def test_create_and_delete_file_or_directory(client: TestClient) -> None:
    # Create a file
    response = client.post(
        "/api/files/create",
        headers=HEADERS,
        json={
            "path": test_dir,
            "type": "file",
            "name": "new_file.txt",
            "contents": "",
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert response.json()["success"] is True

    # Delete the file
    response = client.post(
        "/api/files/delete",
        headers=HEADERS,
        json={"path": f"{test_dir}/new_file.txt"},
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert response.json()["success"] is True


def test_update_file(client: TestClient) -> None:
    response = client.post(
        "/api/files/update",
        headers=HEADERS,
        json={
            "path": test_file_path,
            "contents": "new content",
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert response.json()["success"] is True
    with open(test_file_path) as f:
        assert f.read() == "new content"
    with open(test_file_path, "w") as f:
        f.write(test_content)


@pytest.mark.flaky(reruns=3)
@pytest.mark.skipif(is_windows(), reason="not supported on Windows")
def test_update_file_with_session(client: TestClient) -> None:
    sm = get_session_manager(client)
    # Enable watch mode (file watcher is set up automatically)
    sm.watch = True

    file_path = sm.file_router.get_unique_file_key()
    assert file_path
    file_path = Path(file_path)
    assert file_path.exists()

    # Create a session by connecting via websocket
    with client.websocket_connect(
        "/ws?session_id=test-session&access_token=fake-token"
    ) as websocket:
        # Receive kernel ready message
        data = websocket.receive_json()
        assert data["op"] == "kernel-ready"

        # Verify file watcher was attached when session was created
        assert len(sm._watcher_manager._callbacks) == 1

        # Update the file
        response = client.post(
            "/api/files/update",
            headers=HEADERS,
            json={
                "path": str(file_path),
                "contents": "@app.cell\ndef _(): x=10; x\n",
            },
        )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/json"
        assert response.json()["success"] is True
        file_contents = file_path.read_text()
        assert "@app.cell" in file_contents
        assert "x=10; x" in file_contents

        # Shutdown
        client.post("/api/kernel/shutdown", headers=HEADERS)

    # Clean up
    sm.watch = False
    sm._watcher_manager.stop_all()


def test_move_file_or_directory(client: TestClient) -> None:
    response = client.post(
        "/api/files/move",
        headers=HEADERS,
        json={
            "path": test_file_path,
            "newPath": os.path.join(test_dir, "renamed.txt"),
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert response.json()["success"] is True


def test_open_file(client: TestClient) -> None:
    response = client.post(
        "/api/files/open",
        headers=HEADERS,
        json={"path": test_file_path},
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert "success" in response.json()


def test_search_files_basic(client: TestClient, tmp_path: Path) -> None:
    """Test basic file search functionality."""
    response = client.post(
        "/api/files/search",
        headers=HEADERS,
        json={"query": "test", "path": str(tmp_path)},
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    data = response.json()
    assert "files" in data
    assert "query" in data
    assert "totalFound" in data
    assert data["query"] == "test"
    assert isinstance(data["files"], list)
    assert isinstance(data["totalFound"], int)


def test_search_files_with_matches(client: TestClient, tmp_path: Path) -> None:
    """Test search returns expected matches."""
    # Create test structure
    search_dir = tmp_path

    # Create test files
    Path(search_dir, "hello.txt").write_text("content")
    Path(search_dir, "world.txt").write_text("content")
    Path(search_dir, "hello_world.py").write_text("print('hello')")

    # Create subdirectory with files
    sub_dir = Path(search_dir, "subdir")
    sub_dir.mkdir()
    Path(sub_dir, "hello.md").write_text("# Hello")

    response = client.post(
        "/api/files/search",
        headers=HEADERS,
        json={"query": "hello", "path": str(search_dir), "depth": 2},
    )
    assert response.status_code == 200, response.text
    data = response.json()

    # Should find hello.txt, hello_world.py, and hello.md
    assert data["totalFound"] >= 2
    file_names = [f["name"] for f in data["files"]]
    assert "hello.txt" in file_names
    assert "hello_world.py" in file_names


def test_search_files_with_directory_and_file_filters(
    client: TestClient, tmp_path: Path
) -> None:
    """Test directory and file filtering parameters in API."""
    # Create test structure
    (tmp_path / "test_file.txt").write_text("content")
    (tmp_path / "test_file.py").write_text("# test content")
    test_subdir = tmp_path / "test_dir"
    test_subdir.mkdir()
    (test_subdir / "nested_file.txt").write_text("content")

    # Test searching for files only
    response = client.post(
        "/api/files/search",
        headers=HEADERS,
        json={
            "query": "test",
            "path": str(tmp_path),
            "includeFiles": True,
            "includeDirectories": False,
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()

    # Should only find files
    for file_info in data["files"]:
        assert not file_info["isDirectory"], (
            f"Found directory {file_info['name']} when includeFiles=True, includeDirectories=False"
        )
    assert data["totalFound"] >= 2  # Should find test files

    # Test searching for directories only
    response = client.post(
        "/api/files/search",
        headers=HEADERS,
        json={
            "query": "test",
            "path": str(tmp_path),
            "includeFiles": False,
            "includeDirectories": True,
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()

    # Should only find directories
    for file_info in data["files"]:
        assert file_info["isDirectory"], (
            f"Found file {file_info['name']} when includeFiles=False, includeDirectories=True"
        )
    assert data["totalFound"] >= 1  # Should find test_dir

    # Test with both file and directory filters as false
    response = client.post(
        "/api/files/search",
        headers=HEADERS,
        json={
            "query": "test",
            "path": str(tmp_path),
            "includeFiles": False,
            "includeDirectories": False,
        },
    )
    assert response.status_code == 200, response.text
    data_both_false = response.json()
    assert data_both_false["totalFound"] == 0

    # Compare with no filter
    response = client.post(
        "/api/files/search",
        headers=HEADERS,
        json={"query": "test", "path": str(tmp_path)},
    )
    assert response.status_code == 200, response.text
    data_no_filter = response.json()
    assert data_no_filter["totalFound"] == 3
