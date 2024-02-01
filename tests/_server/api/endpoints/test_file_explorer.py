# Copyright 2024 Marimo. All rights reserved.


import os
from tempfile import TemporaryDirectory

from starlette.testclient import TestClient

HEADERS = {
    "Marimo-Server-Token": "fake-token",
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


def test_update_file_or_directory(client: TestClient) -> None:
    response = client.post(
        "/api/files/update",
        headers=HEADERS,
        json={
            "path": test_file_path,
            "new_path": os.path.join(test_dir, "renamed.txt"),
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert response.json()["success"] is True
