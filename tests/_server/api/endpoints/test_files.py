# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import random
import time
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from tests._server.conftest import get_session_manager
from tests._server.mocks import (
    token_header,
    with_session,
    with_websocket_session,
)

if TYPE_CHECKING:
    from starlette.testclient import TestClient, WebSocketTestSession

SESSION_ID = "session-123"
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    **token_header("fake-token"),
}


def _try_assert_n_times(n: int, assert_fn: Callable[[], None]) -> None:
    n_tries = 0
    while n_tries <= n - 1:
        try:
            assert_fn()
            return
        except Exception:
            n_tries += 1
            time.sleep(0.1)
    assert_fn()


@with_session(SESSION_ID)
def test_rename(client: TestClient) -> None:
    current_filename = get_session_manager(
        client
    ).file_router.get_unique_file_key()

    assert current_filename
    current_path = Path(current_filename)
    assert current_path.exists()

    directory = current_path.parent
    random_name = random.randint(0, 100000)
    new_path = directory / f"test_{random_name}.py"

    response = client.post(
        "/api/kernel/rename",
        headers=HEADERS,
        json={
            "filename": str(new_path),
        },
    )
    assert response.json() == {"success": True}

    def _new_path_exists():
        assert new_path.exists()

    _try_assert_n_times(5, _new_path_exists)


@with_session(SESSION_ID)
def test_read_code(client: TestClient) -> None:
    response = client.post(
        "/api/kernel/read_code",
        headers=HEADERS,
        json={},
    )
    assert response.status_code == 200, response.text
    assert response.json()["contents"].strip().startswith("import marimo")


@with_session(SESSION_ID)
def test_save_file(client: TestClient) -> None:
    filename = get_session_manager(client).file_router.get_unique_file_key()
    assert filename
    path = Path(filename)

    response = client.post(
        "/api/kernel/save",
        headers=HEADERS,
        json={
            "cell_ids": ["1"],
            "filename": str(path),
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

    def _assert_contents():
        file_contents = path.read_text()
        assert "import marimo" in response.text
        assert "import marimo as mo" in file_contents
        assert "@app.cell(hide_code=True)" in file_contents
        assert "my_cell" in file_contents

    _try_assert_n_times(5, _assert_contents)

    # save back
    response = client.post(
        "/api/kernel/save",
        headers=HEADERS,
        json={
            "cell_ids": ["1"],
            "filename": str(path),
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
    filename = get_session_manager(client).file_router.get_unique_file_key()
    assert filename
    path = Path(filename)
    assert path.exists()

    header = (
        '"""This is a docstring"""\n\n' + "# Copyright 2024\n# Linter ignore\n"
    )
    # Prepend a header to the file
    contents = path.read_text()
    contents = header + contents
    path.write_text(contents, encoding="UTF-8")

    response = client.post(
        "/api/kernel/save",
        headers=HEADERS,
        json={
            "cell_ids": ["1"],
            "filename": str(path),
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
    assert "import marimo" in response.text

    def _assert_contents():
        file_contents = path.read_text()
        assert "import marimo as mo" in file_contents
        # Race condition with uv (seen in python 3.10)
        if file_contents.startswith("# ///"):
            file_contents = file_contents.split("# ///")[2].lstrip()
        assert file_contents.startswith(header.rstrip()), "Header was removed"
        assert "@app.cell(hide_code=True)" in file_contents
        assert "my_cell" in file_contents

    _try_assert_n_times(5, _assert_contents)


@with_session(SESSION_ID)
def test_save_with_invalid_file(client: TestClient) -> None:
    filename = get_session_manager(client).file_router.get_unique_file_key()
    assert filename
    path = Path(filename)
    assert path.exists()

    header = (
        '"""This is a docstring"""\n\n'
        + 'print("dont do this!")\n'
        + "# Linter ignore\n"
    )

    # Prepend a header to the file
    contents = path.read_text()
    contents = header + contents
    path.write_text(contents)

    response = client.post(
        "/api/kernel/save",
        headers=HEADERS,
        json={
            "cell_ids": ["1"],
            "filename": str(path),
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
    assert "import marimo" in response.text

    def _assert_contents():
        file_contents = path.read_text()
        assert "@app.cell(hide_code=True)" in file_contents
        assert "my_cell" in file_contents

        # Race condition with uv (seen in python 3.10)
        if file_contents.startswith("# ///"):
            file_contents = file_contents.split("# ///")[2].lstrip()
        assert file_contents.startswith("import marimo"), (
            "Header was not removed"
        )

    _try_assert_n_times(5, _assert_contents)


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
    body = response.json()
    assert body["detail"]
    assert "cannot rename" in body["detail"]


@with_session(SESSION_ID)
def test_save_app_config(client: TestClient) -> None:
    filename = get_session_manager(client).file_router.get_unique_file_key()
    assert filename
    path = Path(filename)

    def _wait_for_file_reset():
        file_contents = path.read_text()
        assert 'marimo.App(width="medium"' not in file_contents

    _try_assert_n_times(5, _wait_for_file_reset)

    response = client.post(
        "/api/kernel/save_app_config",
        headers=HEADERS,
        json={
            "config": {"width": "medium"},
        },
    )
    assert response.status_code == 200, response.text
    assert "import marimo" in response.text

    def _assert_contents():
        file_contents = path.read_text()
        assert 'marimo.App(width="medium"' in file_contents

    _try_assert_n_times(5, _assert_contents)


@with_session(SESSION_ID)
def test_copy_file(client: TestClient) -> None:
    filename = get_session_manager(client).file_router.get_unique_file_key()
    assert filename
    path = Path(filename)
    assert path.exists()
    file_contents = path.read_text()
    assert "import marimo as mo" in file_contents
    assert 'marimo.App(width="full"' in file_contents

    filename_copy = f"_{os.path.basename(filename)}"
    copied_file = os.path.join(os.path.dirname(filename), filename_copy)
    response = client.post(
        "/api/kernel/copy",
        headers=HEADERS,
        json={
            "source": filename,
            "destination": copied_file,
        },
    )
    assert response.status_code == 200, response.text
    assert filename_copy in response.text

    def _assert_contents():
        file_contents = open(copied_file).read()
        assert "import marimo as mo" in file_contents
        assert 'marimo.App(width="full"' in file_contents

    _try_assert_n_times(5, _assert_contents)


@with_websocket_session(SESSION_ID)
def test_rename_propagates(
    client: TestClient, websocket: WebSocketTestSession
) -> None:
    current_filename = get_session_manager(
        client
    ).file_router.get_unique_file_key()

    assert current_filename
    assert os.path.exists(current_filename)

    initial_response = client.post(
        "/api/kernel/run",
        headers=HEADERS,
        json={
            "cell_ids": ["cell-1", "cell-2"],
            "codes": ["b = __file__", "a = 'x' + __file__"],
        },
    )
    assert initial_response.json() == {"success": True}
    assert initial_response.status_code == 200, initial_response.text

    variables = {}
    while len(variables) < 2:
        data = websocket.receive_json()
        if data["op"] == "variable-values":
            for var in data["data"]["variables"]:
                variables[var["name"]] = var["value"]

    # Variable outputs are truncated to 50 characters
    # current_filename can exceed this count on windows and OSX.
    assert ("x" + current_filename).startswith(variables["a"])
    assert current_filename.startswith(variables["b"])

    directory = os.path.dirname(current_filename)
    random_name = random.randint(0, 100000)
    new_filename = os.path.join(directory, f"test_{random_name}.py")

    response = client.post(
        "/api/kernel/rename",
        headers=HEADERS,
        json={
            "filename": new_filename,
        },
    )
    assert response.json() == {"success": True}
    assert response.status_code == 200, response.text

    variables = {}
    while len(variables) < 2:
        data = websocket.receive_json()
        if data["op"] == "variable-values":
            for var in data["data"]["variables"]:
                variables[var["name"]] = var["value"]

    assert ("x" + new_filename).startswith(variables["a"])
    assert new_filename.startswith(variables["b"])
