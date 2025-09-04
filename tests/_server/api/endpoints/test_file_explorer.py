# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

from tests._server.mocks import token_header

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


def test_move_file_or_directory(client: TestClient) -> None:
    response = client.post(
        "/api/files/move",
        headers=HEADERS,
        json={
            "path": test_file_path,
            "new_path": os.path.join(test_dir, "renamed.txt"),
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


def test_search_files_basic(client: TestClient, temp_dir: Path) -> None:
    """Test basic file search functionality."""
    response = client.post(
        "/api/files/search",
        headers=HEADERS,
        json={"query": "test", "path": temp_dir},
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    data = response.json()
    assert "files" in data
    assert "query" in data
    assert "total_found" in data
    assert data["query"] == "test"
    assert isinstance(data["files"], list)
    assert isinstance(data["total_found"], int)


def test_search_files_with_matches(client: TestClient, temp_dir: Path) -> None:
    """Test search returns expected matches."""
    # Create test structure
    search_dir = temp_dir

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
        json={"query": "hello", "path": search_dir, "depth": 2},
    )
    assert response.status_code == 200, response.text
    data = response.json()

    # Should find hello.txt, hello_world.py, and hello.md
    assert data["total_found"] >= 2
    file_names = [f["name"] for f in data["files"]]
    assert "hello.txt" in file_names
    assert "hello_world.py" in file_names
