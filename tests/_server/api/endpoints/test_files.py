# Copyright 2024 Marimo. All rights reserved.
import os
import random

from starlette.testclient import TestClient

from tests._server.conftest import get_session_manager
from tests._server.mocks import with_session

SESSION_ID = "session-123"
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    "Marimo-Server-Token": "fake-token",
}


def test_directory_autocomplete(client: TestClient) -> None:
    response = client.post(
        "/api/kernel/directory_autocomplete",
        headers=HEADERS,
        json={
            "prefix": "",
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert len(response.json()["directories"]) > 0


def test_rename(client: TestClient) -> None:
    current_filename = get_session_manager(client).filename

    assert current_filename
    assert os.path.exists(current_filename)

    directory = os.path.dirname(current_filename)
    random_name = random.randint(0, 100000)
    new_filename = f"{directory}/test_{random_name}.py"

    response = client.post(
        "/api/kernel/rename",
        headers=HEADERS,
        json={
            "filename": new_filename,
        },
    )
    assert response.json() == {"success": True}

    assert os.path.exists(new_filename)
    assert not os.path.exists(current_filename)


def test_read_code(client: TestClient) -> None:
    response = client.post(
        "/api/kernel/read_code",
        headers=HEADERS,
        json={},
    )
    assert response.status_code == 200, response.text
    assert response.json()["contents"].startswith("import marimo")


@with_session(SESSION_ID)
def test_save_file(client: TestClient) -> None:
    filename = get_session_manager(client).filename
    assert filename

    response = client.post(
        "/api/kernel/save",
        headers=HEADERS,
        json={
            "cell_ids": ["1"],
            "filename": filename,
            "codes": ["import marimo as mo"],
            "names": ["my_cell"],
            "configs": [
                {
                    "hideCode": True,
                    "disabled": False,
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True
    file_contents = open(filename).read()
    assert "import marimo as mo" in file_contents
    assert "@app.cell(hide_code=True)" in file_contents
    assert "my_cell" in file_contents

    # save back
    response = client.post(
        "/api/kernel/save",
        headers=HEADERS,
        json={
            "cell_ids": ["1"],
            "filename": filename,
            "codes": ["import marimo as mo"],
            "names": ["__"],
            "configs": [
                {
                    "hideCode": False,
                }
            ],
        },
    )


@with_session(SESSION_ID)
def test_save_with_header(client: TestClient) -> None:
    filename = get_session_manager(client).filename
    assert filename
    assert os.path.exists(filename)

    header = (
        '"""This is a docstring"""\n\n' + "# Copyright 2024\n# Linter ignore\n"
    )
    # Prepend a header to the file
    contents = open(filename).read()
    contents = header + contents
    open(filename, "w", encoding="UTF-8").write(contents)

    response = client.post(
        "/api/kernel/save",
        headers=HEADERS,
        json={
            "cell_ids": ["1"],
            "filename": filename,
            "codes": ["import marimo as mo"],
            "names": ["my_cell"],
            "configs": [
                {
                    "hideCode": True,
                    "disabled": False,
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["success"] is True
    file_contents = open(filename).read()
    assert "import marimo as mo" in file_contents
    assert file_contents.startswith(header.rstrip()), "Header was removed"
    assert "@app.cell(hide_code=True)" in file_contents
    assert "my_cell" in file_contents


@with_session(SESSION_ID)
def test_save_with_invalid_file(client: TestClient) -> None:
    filename = get_session_manager(client).filename
    assert filename
    assert os.path.exists(filename)

    header = (
        '"""This is a docstring"""\n\n'
        + 'print("dont do this!")\n'
        + "# Linter ignore\n"
    )

    # Prepend a header to the file
    contents = open(filename).read()
    contents = header + contents
    open(filename, "w", encoding="UTF-8").write(contents)

    response = client.post(
        "/api/kernel/save",
        headers=HEADERS,
        json={
            "cell_ids": ["1"],
            "filename": filename,
            "codes": ["import marimo as mo"],
            "names": ["my_cell"],
            "configs": [
                {
                    "hideCode": True,
                    "disabled": False,
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["success"] is True
    file_contents = open(filename).read()
    assert file_contents.startswith("import marimo"), "Header was not removed"
    assert "@app.cell(hide_code=True)" in file_contents
    assert "my_cell" in file_contents


@with_session(SESSION_ID)
def test_save_file_cannot_rename(client: TestClient) -> None:
    response = client.post(
        "/api/kernel/save",
        headers=HEADERS,
        json={
            "cell_ids": ["1"],
            "filename": "random_filename.py",
            "codes": ["import marimo as mo"],
            "names": ["my_cell"],
            "configs": [
                {
                    "hideCode": True,
                    "disabled": False,
                }
            ],
        },
    )
    assert response.status_code == 400
    assert "cannot rename" in response.text


@with_session(SESSION_ID)
def test_save_app_config(client: TestClient) -> None:
    filename = get_session_manager(client).filename
    assert filename

    file_contents = open(filename).read()
    assert 'marimo.App(width="full"' not in file_contents

    response = client.post(
        "/api/kernel/save_app_config",
        headers=HEADERS,
        json={
            "config": {"width": "full"},
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True
    file_contents = open(filename).read()
    assert 'marimo.App(width="full"' in file_contents
