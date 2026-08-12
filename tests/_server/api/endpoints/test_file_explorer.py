# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, cast

import pytest

from marimo._utils.platform import is_windows
from tests._server.mocks import get_session_manager, token_header

if TYPE_CHECKING:
    from starlette.testclient import TestClient

    from marimo._config.config import PartialMarimoConfig
    from marimo._config.manager import UserConfigManager

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
    data = response.json()
    assert "file" in data
    assert data["isBase64"] is False


def test_file_details_binary(client: TestClient) -> None:
    import base64

    bin_path = os.path.join(test_dir, "binary_file.bin")
    raw_bytes = b"\xff\xfe\xfd\x00\x80"
    with open(bin_path, "wb") as f:
        f.write(raw_bytes)
    response = client.post(
        "/api/files/file_details",
        headers=HEADERS,
        json={"path": bin_path},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["isBase64"] is True
    assert data["contents"] == base64.b64encode(raw_bytes).decode("utf-8")
    os.remove(bin_path)


def test_file_details_caps_oversized_file_when_limited(
    client: TestClient,
    tmp_path: Path,
) -> None:
    path = tmp_path / "large.txt"
    path.write_bytes(b"12345")

    response = client.post(
        "/api/files/file_details",
        headers=HEADERS,
        json={"path": str(path), "maxBytes": 4},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["contents"] is None
    assert data["isBase64"] is False
    assert data["isTooLarge"] is True
    assert data["file"]["size"] == 5


def test_file_details_is_unbounded_without_limit(
    client: TestClient,
    tmp_path: Path,
) -> None:
    path = tmp_path / "large.txt"
    path.write_bytes(b"12345")

    response = client.post(
        "/api/files/file_details",
        headers=HEADERS,
        json={"path": str(path)},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["contents"] == "12345"
    assert data["isTooLarge"] is False


def test_file_details_rejects_negative_limit(
    client: TestClient, tmp_path: Path
) -> None:
    path = tmp_path / "small.txt"
    path.write_text("ok", encoding="utf-8")

    response = client.post(
        "/api/files/file_details",
        headers=HEADERS,
        json={"path": str(path), "maxBytes": -1},
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "maxBytes must be non-negative"


def test_create_and_delete_file_or_directory(client: TestClient) -> None:
    # Create a file with no contents (empty file)
    response = client.post(
        "/api/files/create",
        headers=HEADERS,
        data={
            "path": test_dir,
            "type": "file",
            "name": "new_file.txt",
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


def test_create_file_with_binary_contents(client: TestClient) -> None:
    raw_bytes = b"\xff\xfe\xfd\x00\x80marimo"
    response = client.post(
        "/api/files/create",
        headers=HEADERS,
        data={
            "path": test_dir,
            "type": "file",
            "name": "binary_upload.bin",
        },
        files={"file": ("binary_upload.bin", raw_bytes)},
    )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True

    created_path = os.path.join(test_dir, "binary_upload.bin")
    with open(created_path, "rb") as f:
        assert f.read() == raw_bytes
    os.remove(created_path)


def test_create_directory(client: TestClient) -> None:
    response = client.post(
        "/api/files/create",
        headers=HEADERS,
        data={
            "path": test_dir,
            "type": "directory",
            "name": "new_subdir",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True
    new_dir = os.path.join(test_dir, "new_subdir")
    assert os.path.isdir(new_dir)
    os.rmdir(new_dir)


def test_create_rejects_invalid_type(client: TestClient) -> None:
    response = client.post(
        "/api/files/create",
        headers=HEADERS,
        data={
            "path": test_dir,
            "type": "not_a_real_type",
            "name": "x.txt",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is False
    assert "type" in body["message"].lower()


def test_create_rejects_missing_fields(client: TestClient) -> None:
    response = client.post(
        "/api/files/create",
        headers=HEADERS,
        data={"type": "file"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is False


def test_create_rejects_path_traversal_name(client: TestClient) -> None:
    response = client.post(
        "/api/files/create",
        headers=HEADERS,
        data={
            "path": test_dir,
            "type": "file",
            "name": "../escaped.txt",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is False
    # Confirm nothing was written outside test_dir
    parent_path = os.path.join(os.path.dirname(test_dir), "escaped.txt")
    assert not os.path.exists(parent_path)


def test_create_returns_413_when_upload_exceeds_size_cap(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Shrink the cap so a small payload trips it.
    monkeypatch.setattr(
        "marimo._server.files.os_file_system.MAX_UPLOAD_BYTES", 4
    )
    response = client.post(
        "/api/files/create",
        headers=HEADERS,
        data={
            "path": test_dir,
            "type": "file",
            "name": "too_big.bin",
        },
        files={"file": ("too_big.bin", b"way too much data")},
    )
    assert response.status_code == 413, response.text
    assert not os.path.exists(os.path.join(test_dir, "too_big.bin"))


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

    file_path = sm.workspace.get_unique_file_key()
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


def test_copy_file(client: TestClient) -> None:
    file_path = Path(test_dir).joinpath("test_file.txt")
    file_path.write_text("This is a test file for copying.")
    copy_path = Path(test_dir).joinpath("test_file_copy.txt")
    response = client.post(
        "/api/files/copy",
        headers=HEADERS,
        json={
            "path": test_file_path,
            "newPath": str(copy_path),
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True
    assert copy_path.exists()
    assert copy_path.read_text() == file_path.read_text()


def test_copy_directory(client: TestClient) -> None:
    sub_dir = Path(test_dir).joinpath("test_subdir")
    sub_dir.mkdir(exist_ok=True)
    inner_file = sub_dir.joinpath("inner.txt")
    inner_file.write_text("inner content")

    copy_sub_dir = Path(test_dir).joinpath("test_subdir_copy")
    response = client.post(
        "/api/files/copy",
        headers=HEADERS,
        json={
            "path": str(sub_dir),
            "newPath": str(copy_sub_dir),
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True
    assert copy_sub_dir.joinpath("inner.txt").read_text() == "inner content"


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


def test_download_file_text(client: TestClient) -> None:
    path = os.path.join(test_dir, "download_me.txt")
    with open(path, "w") as f:
        f.write("stream me")
    response = client.get(
        "/api/files/download", headers=HEADERS, params={"path": path}
    )
    assert response.status_code == 200, response.text
    assert response.text == "stream me"
    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment")
    assert "download_me.txt" in disposition
    assert response.headers["x-content-type-options"] == "nosniff"
    os.remove(path)


def test_download_file_binary(client: TestClient) -> None:
    raw_bytes = b"\xff\xfe\xfd\x00\x80marimo"
    path = os.path.join(test_dir, "download_me.bin")
    with open(path, "wb") as f:
        f.write(raw_bytes)
    response = client.get(
        "/api/files/download", headers=HEADERS, params={"path": path}
    )
    assert response.status_code == 200, response.text
    assert response.content == raw_bytes
    assert response.headers["content-type"] == "application/octet-stream"
    os.remove(path)


def test_download_file_unicode_name(client: TestClient) -> None:
    path = os.path.join(test_dir, "émoji 🎉.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("unicode")
    response = client.get(
        "/api/files/download", headers=HEADERS, params={"path": path}
    )
    assert response.status_code == 200, response.text
    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment")
    assert "filename*=UTF-8''" in disposition
    os.remove(path)


def test_download_directory_is_rejected(client: TestClient) -> None:
    response = client.get(
        "/api/files/download", headers=HEADERS, params={"path": test_dir}
    )
    assert response.status_code == 400, response.text


def test_download_missing_file(client: TestClient) -> None:
    response = client.get(
        "/api/files/download",
        headers=HEADERS,
        params={"path": os.path.join(test_dir, "does_not_exist.txt")},
    )
    assert response.status_code == 404, response.text


def test_download_requires_path_param(client: TestClient) -> None:
    response = client.get("/api/files/download", headers=HEADERS)
    assert response.status_code == 400, response.text


def test_download_requires_auth(client: TestClient) -> None:
    response = client.get(
        "/api/files/download", params={"path": test_file_path}
    )
    assert response.status_code == 401, response.text


def test_download_disabled_by_config(
    client: TestClient, user_config_manager: UserConfigManager
) -> None:
    user_config_manager.save_config(
        cast(
            "PartialMarimoConfig", {"server": {"disable_file_downloads": True}}
        )
    )
    response = client.get(
        "/api/files/download", headers=HEADERS, params={"path": test_file_path}
    )
    assert response.status_code == 403, response.text
