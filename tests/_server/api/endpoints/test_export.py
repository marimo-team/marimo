# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from marimo import __version__
from marimo._dependencies.dependencies import DependencyManager
from marimo._output.utils import uri_encode_component
from marimo._types.ids import SessionId
from tests._server.conftest import get_session_manager
from tests._server.mocks import (
    token_header,
    with_read_session,
    with_session,
)
from tests.mocks import snapshotter

if TYPE_CHECKING:
    from starlette.testclient import TestClient

snapshot = snapshotter(__file__)

SESSION_ID = SessionId("session-123")
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    **token_header("fake-token"),
}

CODE = uri_encode_component("import marimo as mo")


@with_session(SESSION_ID)
def test_export_html(client: TestClient) -> None:
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session
    session.app_file_manager.filename = "test.py"
    response = client.post(
        "/api/export/html",
        headers=HEADERS,
        json={
            "download": False,
            "files": [],
            "include_code": True,
        },
    )
    body = response.text
    assert '<marimo-code hidden=""></marimo-code>' not in body
    assert CODE in body


@with_session(SESSION_ID)
def test_export_html_skew_protection(client: TestClient) -> None:
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session
    session.app_file_manager.filename = "test.py"
    response = client.post(
        "/api/export/html",
        headers={
            **HEADERS,
            "Marimo-Server-Token": "old-skew-id",
        },
        json={
            "download": False,
            "files": [],
            "include_code": True,
        },
    )
    assert response.status_code == 401
    assert response.json() == {"error": "Invalid server token"}


@with_session(SESSION_ID)
def test_export_html_no_code(client: TestClient) -> None:
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session
    session.app_file_manager.filename = "test.py"
    response = client.post(
        "/api/export/html",
        headers=HEADERS,
        json={
            "download": False,
            "files": [],
            "include_code": False,
        },
    )
    body = response.text
    assert '<marimo-code hidden=""></marimo-code>' in body
    assert CODE not in body


@with_session(SESSION_ID)
def test_export_html_file_not_found(client: TestClient) -> None:
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session
    session.app_file_manager.filename = "test.py"
    response = client.post(
        "/api/export/html",
        headers=HEADERS,
        json={
            "download": False,
            "files": ["/test-10.csv"],
            "include_code": True,
        },
    )
    assert response.status_code == 200
    assert "<marimo-code hidden=" in response.text


# Read session forces empty code
@with_read_session(SESSION_ID)
def test_export_html_no_code_in_read(client: TestClient) -> None:
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session
    session.app_file_manager.filename = "test.py"
    response = client.post(
        "/api/export/html",
        headers=HEADERS,
        json={
            "download": False,
            "files": [],
            "include_code": True,
        },
    )
    body = response.text
    assert '<marimo-code hidden=""></marimo-code>' in body
    assert CODE not in body

    session = get_session_manager(client).get_session(SESSION_ID)
    assert session
    session.app_file_manager.filename = "test.py"
    response = client.post(
        "/api/export/html",
        headers=HEADERS,
        json={
            "download": False,
            "files": [],
            "include_code": False,
        },
    )
    body = response.text
    assert '<marimo-code hidden=""></marimo-code>' in body
    assert CODE not in body


@with_session(SESSION_ID)
def test_export_script(client: TestClient) -> None:
    response = client.post(
        "/api/export/script",
        headers=HEADERS,
        json={
            "download": False,
        },
    )
    assert response.status_code == 200
    assert "__generated_with = " in response.text


@pytest.mark.xfail(reason="flakey", strict=False)
@with_session(SESSION_ID)
def test_export_markdown(client: TestClient) -> None:
    response = client.post(
        "/api/export/markdown",
        headers=HEADERS,
        json={
            "download": False,
        },
    )
    assert response.status_code == 200
    assert f"marimo-version: {__version__}" in response.text
    assert "```python {.marimo}" in response.text


@with_read_session(SESSION_ID)
def test_other_exports_dont_work_in_read(client: TestClient) -> None:
    response = client.post(
        "/api/export/markdown",
        headers=HEADERS,
        json={
            "download": False,
        },
    )
    assert response.status_code == 401
    response = client.post(
        "/api/export/script",
        headers=HEADERS,
        json={
            "download": False,
        },
    )
    assert response.status_code == 401


@with_session(SESSION_ID)
def test_auto_export_html(client: TestClient, temp_marimo_file: str) -> None:
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session
    assert temp_marimo_file is not None
    session.app_file_manager.filename = temp_marimo_file

    response = client.post(
        "/api/export/auto_export/html",
        headers=HEADERS,
        json={
            "download": False,
            "files": [],
            "include_code": True,
        },
    )
    assert response.status_code == 200
    assert response.json() == {"success": True}

    response = client.post(
        "/api/export/auto_export/html",
        headers=HEADERS,
        json={
            "download": False,
            "files": [],
            "include_code": True,
        },
    )
    # Not modified response
    assert response.status_code == 304

    # Assert __marimo__ directory is created
    assert os.path.exists(
        os.path.join(os.path.dirname(temp_marimo_file), "__marimo__")
    )


@with_session(SESSION_ID)
def test_auto_export_html_no_code(
    client: TestClient, temp_marimo_file: str
) -> None:
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session
    session.app_file_manager.filename = temp_marimo_file

    response = client.post(
        "/api/export/auto_export/html",
        headers=HEADERS,
        json={
            "download": False,
            "files": [],
            "include_code": False,
        },
    )
    assert response.status_code == 200
    assert response.json() == {"success": True}

    response = client.post(
        "/api/export/auto_export/html",
        headers=HEADERS,
        json={
            "download": False,
            "files": [],
            "include_code": False,
        },
    )
    # Not modified response
    assert response.status_code == 304

    # Assert __marimo__ file is created
    assert os.path.exists(
        os.path.join(os.path.dirname(temp_marimo_file), "__marimo__")
    )


@with_session(SESSION_ID)
def test_auto_export_markdown(
    client: TestClient, *, temp_marimo_file: str
) -> None:
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session
    session.app_file_manager.filename = temp_marimo_file

    response = client.post(
        "/api/export/auto_export/markdown",
        headers=HEADERS,
        json={
            "download": False,
        },
    )
    assert response.status_code == 200
    assert response.json() == {"success": True}

    response = client.post(
        "/api/export/auto_export/markdown",
        headers=HEADERS,
        json={
            "download": False,
        },
    )
    # Not modified response
    assert response.status_code == 304

    # Assert __marimo__ file is created
    assert os.path.exists(
        os.path.join(os.path.dirname(temp_marimo_file), "__marimo__")
    )


@pytest.mark.skipif(
    not DependencyManager.nbformat.has(), reason="nbformat not installed"
)
@with_session(SESSION_ID)
def test_auto_export_ipynb(
    client: TestClient, *, temp_marimo_file: str
) -> None:
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session
    session.app_file_manager.filename = temp_marimo_file

    response = client.post(
        "/api/export/auto_export/ipynb",
        headers=HEADERS,
        json={
            "download": False,
        },
    )
    assert response.status_code == 200
    assert response.json() == {"success": True}

    response = client.post(
        "/api/export/auto_export/ipynb",
        headers=HEADERS,
        json={
            "download": False,
        },
    )
    # Not modified response
    assert response.status_code == 304

    # Assert __marimo__ file is created
    assert os.path.exists(
        os.path.join(os.path.dirname(temp_marimo_file), "__marimo__")
    )


@pytest.mark.skipif(
    not DependencyManager.nbformat.has(), reason="nbformat not installed"
)
@with_session(SESSION_ID)
def test_auto_export_ipynb_with_new_cell(
    client: TestClient, *, temp_marimo_file: str
) -> None:
    """Test that auto-exporting to ipynb works after creating and running a new cell.

    This test addresses the bug in https://github.com/marimo-team/marimo/issues/3992
    where cell ID inconsistency causes KeyError when auto-exporting as ipynb.
    """
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session
    session.app_file_manager.filename = temp_marimo_file

    # First, create and run a cell with constant value 1
    create_cell_response = client.post(
        "/api/kernel/run",
        headers=HEADERS,
        json={
            "cell_ids": ["new_cell"],
            "codes": ["3.14"],
        },
    )
    assert create_cell_response.status_code == 200

    time.sleep(0.5)

    # Save the session
    save_response = client.post(
        "/api/kernel/save",
        headers=HEADERS,
        json={
            "cell_ids": ["new_cell"],
            "filename": temp_marimo_file,
            "codes": ["3.14"],
            "names": ["_"],
            "configs": [
                {
                    "hideCode": True,
                    "disabled": False,
                }
            ],
        },
    )
    assert save_response.status_code == 200, save_response.text

    # Clean up the marimo directory
    marimo_dir = Path(temp_marimo_file).parent / "__marimo__"
    shutil.rmtree(marimo_dir, ignore_errors=True)

    # Now attempt to auto-export as ipynb
    export_response = client.post(
        "/api/export/auto_export/ipynb",
        headers=HEADERS,
        json={
            "download": False,
        },
    )
    assert export_response.status_code == 200
    assert export_response.json() == {"success": True}

    # Verify the exported file exists
    assert marimo_dir.exists()

    # Verify the cell output is correct
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session
    cell_op = session.session_view.cell_operations["new_cell"]
    assert cell_op.output is not None
    assert "3.14" in cell_op.output.data

    # Verify the ipynb file exists
    filename = Path(temp_marimo_file).name.replace(".py", ".ipynb")
    ipynb_path = marimo_dir / filename
    notebook = ipynb_path.read_text()
    assert "<pre style='font-size: 12px'>3.14</pre>" in notebook


@with_session(SESSION_ID)
def test_export_html_with_script_config(client: TestClient) -> None:
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session
    session.config_manager = session.config_manager.with_overrides(
        {"display": {"code_editor_font_size": 999}}
    )
    response = client.post(
        "/api/export/html",
        headers=HEADERS,
        json={
            "download": False,
            "files": [],
            "include_code": False,
        },
    )
    body = response.text
    assert '"code_editor_font_size": 999' in body
