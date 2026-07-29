# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from marimo import App, __version__
from marimo._ast.app import InternalApp
from marimo._convert.markdown.flavor.base import MarkdownFlavorName
from marimo._dependencies.dependencies import DependencyManager
from marimo._export.requests import PDFExportRequest
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.notification import CellNotification
from marimo._output.utils import uri_encode_component
from marimo._schemas.export_options import PDFExportOptions
from marimo._session.model import SessionMode
from marimo._types.ids import CellId_t, SessionId
from marimo._utils.platform import is_windows
from tests._server.mocks import (
    get_session_manager,
    token_header,
    with_read_session,
    with_session,
)
from tests.mocks import EDGE_CASE_FILENAMES, snapshotter

if TYPE_CHECKING:
    from starlette.testclient import TestClient

snapshot = snapshotter(__file__)

SESSION_ID = SessionId("session-123")
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    **token_header("fake-token"),
}

CODE = uri_encode_component("import marimo as mo")


def _ipynb_export_app() -> InternalApp:
    app = App()

    @app.cell()
    def result(x, y):
        z = x + y
        return (z,)

    @app.cell()
    def __():
        x = 1
        return (x,)

    @app.cell()
    def __():
        y = 1
        return (y,)

    return InternalApp(app)


def test_export_availability_requires_auth(client: TestClient) -> None:
    response = client.get("/api/export/availability")

    assert response.status_code == 401


def test_export_availability_reports_server_dependencies(
    client: TestClient,
) -> None:
    get_session_manager(client).mode = SessionMode.RUN
    with (
        patch.object(DependencyManager.nbformat, "has", return_value=False),
        patch.object(DependencyManager.nbconvert, "has", return_value=True),
        patch.object(DependencyManager.playwright, "has", return_value=False),
    ):
        response = client.get(
            "/api/export/availability",
            headers=token_header(),
        )

    assert response.status_code == 200
    assert response.json() == {
        "source": "server",
        "formats": [
            {
                "format": "html",
                "dependenciesAvailable": True,
                "missingPackages": [],
            },
            {
                "format": "markdown",
                "dependenciesAvailable": True,
                "missingPackages": [],
            },
            {
                "format": "ipynb",
                "dependenciesAvailable": False,
                "missingPackages": ["nbformat"],
            },
            {
                "format": "pdf",
                "dependenciesAvailable": False,
                "missingPackages": ["nbconvert[webpdf]"],
            },
        ],
    }


@with_session(SESSION_ID)
def test_export_html(client: TestClient) -> None:
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session
    session.app_file_manager.filename = "test.py"
    response = client.post(
        "/api/export/html",
        headers={**HEADERS, "Origin": "localhost"},
        json={
            "download": False,
            "files": [],
            "includeCode": True,
        },
    )
    body = response.text
    assert '<marimo-code hidden=""></marimo-code>' not in body
    assert CODE in body
    assert (
        response.headers["content-disposition"]
        == "inline; filename*=UTF-8''test.html"
    )
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    exposed_headers = response.headers["access-control-expose-headers"].lower()
    assert "content-disposition" in exposed_headers


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
            "includeCode": True,
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
            "includeCode": False,
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
            "includeCode": True,
        },
    )
    assert response.status_code == 200
    assert "<marimo-code hidden=" in response.text


# Read session with include_code=True allows code to be included
@with_read_session(SESSION_ID, include_code=True)
def test_export_html_with_code_in_read_with_include_code(
    client: TestClient,
) -> None:
    """Test that HTML export includes code in run mode when include_code=True."""
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session
    session.app_file_manager.filename = "test.py"
    response = client.post(
        "/api/export/html",
        headers=HEADERS,
        json={
            "download": False,
            "files": [],
            "includeCode": True,
        },
    )
    body = response.text
    # Code should be included when include_code=True
    assert '<marimo-code hidden=""></marimo-code>' not in body
    assert CODE in body


# Read session without include_code forces empty code
@with_read_session(SESSION_ID, include_code=False)
def test_export_html_no_code_in_read(client: TestClient) -> None:
    """Test that HTML export excludes code in run mode when include_code=False."""
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session
    session.app_file_manager.filename = "test.py"
    # Even if request asks for code, it should be denied
    response = client.post(
        "/api/export/html",
        headers=HEADERS,
        json={
            "download": False,
            "files": [],
            "includeCode": True,
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
            "includeCode": False,
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
    # Check that the Content-Disposition header has the correct .md extension
    assert "Content-Disposition" in response.headers
    # The temp file has .py extension, should be converted to .md
    assert re.match(
        r"filename=.*\.md", response.headers["Content-Disposition"]
    )


@with_session(SESSION_ID)
def test_export_markdown_uses_qmd_filename(
    client: TestClient, *, temp_marimo_file: str
) -> None:
    qmd_path = Path(temp_marimo_file).with_suffix(".qmd")
    qmd_path.write_text("```{marimo .python}\nx = 1\n```", encoding="utf-8")
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session
    session.app_file_manager.filename = str(qmd_path)

    response = client.post(
        "/api/export/markdown",
        headers=HEADERS,
        json={
            "download": False,
        },
    )

    assert response.status_code == 200
    assert "```{marimo .python" in response.text
    assert response.headers["Content-Disposition"].startswith("inline;")
    assert qmd_path.name in response.headers["Content-Disposition"]
    assert response.headers["Content-Type"] == "text/plain; charset=utf-8"


@with_session(SESSION_ID)
def test_export_markdown_uses_requested_flavor(
    client: TestClient,
    *,
    temp_marimo_file: str,
) -> None:
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session
    session.app_file_manager.filename = temp_marimo_file

    cases: list[tuple[MarkdownFlavorName, str, str]] = [
        ("pymdown", ".md", "```python {.marimo}"),
        ("qmd", ".qmd", "```{marimo .python"),
        ("mystmd", ".myst.md", "```{marimo} python"),
        ("mdx", ".mdx", "```python marimo"),
    ]
    for flavor, expected_suffix, expected_fence in cases:
        response = client.post(
            "/api/export/markdown",
            headers=HEADERS,
            json={
                "download": False,
                "flavor": flavor,
            },
        )

        expected_filename = f"{Path(temp_marimo_file).stem}{expected_suffix}"
        assert response.status_code == 200
        assert expected_fence in response.text
        assert (
            response.headers["Content-Disposition"]
            == f"inline; filename*=UTF-8''{expected_filename}"
        )
        assert response.headers["Content-Type"] == "text/plain; charset=utf-8"


@pytest.mark.skipif(
    not DependencyManager.nbformat.has(), reason="nbformat not installed"
)
@with_session(SESSION_ID)
def test_export_ipynb(client: TestClient) -> None:
    response = client.post(
        "/api/export/ipynb",
        headers=HEADERS,
        json={
            "download": False,
        },
    )
    assert response.status_code == 200
    ipynb_json = json.loads(response.text)
    assert "cells" in ipynb_json
    assert ipynb_json["nbformat"] == 4
    assert response.headers["content-disposition"].startswith(
        "inline; filename*=UTF-8''"
    )
    assert response.headers["content-disposition"].endswith(".ipynb")
    assert response.headers["content-type"] == "text/plain; charset=utf-8"


@pytest.mark.skipif(
    not DependencyManager.nbformat.has(), reason="nbformat not installed"
)
@with_session(SESSION_ID)
def test_export_ipynb_uses_requested_sort_mode(client: TestClient) -> None:
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session
    session.app_file_manager.app = _ipynb_export_app()

    top_down = ["z = x + y", "x = 1", "y = 1"]
    topological = ["x = 1", "y = 1", "z = x + y"]
    cases = [
        ({"download": False}, top_down),
        ({"download": False, "sortMode": "top-down"}, top_down),
        ({"download": False, "sortMode": "topological"}, topological),
    ]

    for request_body, expected_sources in cases:
        response = client.post(
            "/api/export/ipynb",
            headers=HEADERS,
            json=request_body,
        )

        assert response.status_code == 200
        cells = json.loads(response.text)["cells"]
        assert ["".join(cell["source"]) for cell in cells] == expected_sources


@pytest.mark.skipif(
    not DependencyManager.nbformat.has(), reason="nbformat not installed"
)
@with_session(SESSION_ID)
def test_export_ipynb_selects_current_session_outputs(
    client: TestClient,
) -> None:
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session
    app = _ipynb_export_app()
    session.app_file_manager.app = app

    output_cell_id = next(
        cell_data.cell_id
        for cell_data in app.cell_manager.cell_data()
        if cell_data.code == "x = 1"
    )
    session.session_view.add_notification(
        CellNotification(
            cell_id=output_cell_id,
            output=CellOutput(
                channel=CellChannel.OUTPUT,
                mimetype="text/plain",
                data="current output",
            ),
        )
    )

    current_output = [
        {
            "data": {"text/plain": ["current output"]},
            "metadata": {},
            "output_type": "display_data",
        }
    ]
    cases = [
        ({"download": False}, current_output),
        ({"download": False, "includeOutputs": True}, current_output),
        ({"download": False, "includeOutputs": False}, []),
    ]

    for request_body, expected_outputs in cases:
        response = client.post(
            "/api/export/ipynb",
            headers=HEADERS,
            json=request_body,
        )

        assert response.status_code == 200
        cells = json.loads(response.text)["cells"]
        output_cell = next(
            cell for cell in cells if "".join(cell["source"]) == "x = 1"
        )
        assert output_cell["outputs"] == expected_outputs


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
    response = client.post(
        "/api/export/ipynb",
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
    session.session_view.add_notification(
        CellNotification(
            cell_id=CellId_t("new_cell"),
            output=CellOutput(
                data="hello",
                mimetype="text/plain",
                channel=CellChannel.OUTPUT,
            ),
        )
    )

    response = client.post(
        "/api/export/auto_export/html",
        headers=HEADERS,
        json={
            "download": False,
            "files": [],
            "includeCode": True,
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
            "includeCode": True,
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
    session.session_view.add_notification(
        CellNotification(
            cell_id=CellId_t("new_cell"),
            output=None,
            console=[CellOutput.stdout("hello")],
        )
    )

    response = client.post(
        "/api/export/auto_export/html",
        headers=HEADERS,
        json={
            "download": False,
            "files": [],
            "includeCode": False,
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
            "includeCode": False,
        },
    )
    # Not modified response
    assert response.status_code == 304

    # Assert __marimo__ file is created
    assert os.path.exists(
        os.path.join(os.path.dirname(temp_marimo_file), "__marimo__")
    )


@with_session(SESSION_ID)
def test_auto_export_html_no_operations(
    client: TestClient, temp_marimo_file: str
) -> None:
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session
    session.app_file_manager.filename = temp_marimo_file
    assert session.session_view.is_empty()

    response = client.post(
        "/api/export/auto_export/html",
        headers=HEADERS,
        json={
            "download": False,
            "files": [],
            "includeCode": True,
        },
    )
    # Not modified response
    assert response.status_code == 304


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


@with_session(SESSION_ID)
def test_auto_export_ipynb_missing_nbformat_notifies_once(
    client: TestClient, *, temp_marimo_file: str
) -> None:
    """Missing-nbformat alert fires at most once per session."""
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session
    session.app_file_manager.filename = temp_marimo_file

    with (
        patch.object(
            DependencyManager.nbformat,
            "has",
            return_value=False,
        ),
        patch(
            "marimo._server.api.endpoints.export.notify_server_missing_packages"
        ) as mock_notify,
    ):
        # First call should notify.
        response = client.post(
            "/api/export/auto_export/ipynb",
            headers=HEADERS,
            json={"download": False},
        )
        assert response.status_code == 304
        mock_notify.assert_called_once_with(session, SESSION_ID, ["nbformat"])

        # Reset the export guard to exercise package notification deduplication.
        session.session_view.needs_export = lambda _: True
        response = client.post(
            "/api/export/auto_export/ipynb",
            headers=HEADERS,
            json={"download": False},
        )
        assert response.status_code == 304
        assert mock_notify.call_count == 1


@pytest.mark.skipif(
    not DependencyManager.nbformat.has() or is_windows(),
    reason="nbformat not installed or on Windows",
)
@pytest.mark.flaky(reruns=3)
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
            "cellIds": ["new_cell"],
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
            "cellIds": ["new_cell"],
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

    # Verify the cell output is correct
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session

    # Wait for the cell operation to be created
    timeout = 2
    start = time.time()
    cell_notification = None
    while time.time() - start < timeout:
        if "new_cell" not in session.session_view.cell_notifications:
            time.sleep(0.1)
            continue
        cell_notification = session.session_view.cell_notifications["new_cell"]
        if (
            cell_notification.output is not None
            and cell_notification.output.data
        ):
            break
    assert cell_notification
    assert cell_notification.output is not None
    assert "3.14" in cell_notification.output.data

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

    # Verify the ipynb file exists
    filename = Path(temp_marimo_file).name.replace(".py", ".ipynb")
    ipynb_path = marimo_dir / filename

    # Wait for the ipynb file to be created
    time.sleep(0.2)
    notebook = ipynb_path.read_text()
    assert "<pre class='text-xs'>3.14</pre>" in notebook


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
            "includeCode": False,
        },
    )
    body = response.text
    assert '"code_editor_font_size": 999' in body


@with_session(SESSION_ID)
def test_auto_export_html_unnamed_file(client: TestClient) -> None:
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session
    # Ensure the file is unnamed
    session.app_file_manager.filename = None

    response = client.post(
        "/api/export/auto_export/html",
        headers=HEADERS,
        json={
            "download": False,
            "files": [],
            "includeCode": True,
        },
    )

    # Should return 400 Bad Request when file is unnamed
    assert response.status_code == 400
    assert "File must have a name before exporting" in response.text


@with_session(SESSION_ID)
def test_export_html_unnamed_file(client: TestClient) -> None:
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session
    # Ensure the file is unnamed
    session.app_file_manager.filename = None

    response = client.post(
        "/api/export/html",
        headers=HEADERS,
        json={
            "download": False,
            "files": [],
            "includeCode": True,
        },
    )

    # Should return 400 Bad Request when file is unnamed
    assert response.status_code == 400
    assert "File must have a name before exporting" in response.text


@with_session(SESSION_ID)
def test_export_html_download_edge_case_filenames(client: TestClient) -> None:
    """Test that HTML export with download=True works for non-ASCII filenames."""
    for filename in EDGE_CASE_FILENAMES:
        session = get_session_manager(client).get_session(SESSION_ID)
        assert session
        session.app_file_manager.filename = filename
        response = client.post(
            "/api/export/html",
            headers=HEADERS,
            json={
                "download": True,
                "files": [],
                "includeCode": True,
            },
        )
        assert response.status_code == 200, f"Failed for filename: {filename}"
        assert "Content-Disposition" in response.headers
        assert "attachment" in response.headers["Content-Disposition"]


@with_session(SESSION_ID)
def test_export_script_download_edge_case_filenames(
    client: TestClient,
) -> None:
    """Test that script export with download=True works for non-ASCII filenames."""
    for filename in EDGE_CASE_FILENAMES:
        session = get_session_manager(client).get_session(SESSION_ID)
        assert session
        session.app_file_manager.filename = filename
        response = client.post(
            "/api/export/script",
            headers=HEADERS,
            json={
                "download": True,
            },
        )
        assert response.status_code == 200, f"Failed for filename: {filename}"
        assert "Content-Disposition" in response.headers
        assert "attachment" in response.headers["Content-Disposition"]


@pytest.mark.skipif(
    not DependencyManager.nbformat.has(), reason="nbformat not installed"
)
@with_session(SESSION_ID)
def test_export_ipynb_download_edge_case_filenames(
    client: TestClient,
) -> None:
    """Test that ipynb export with download=True works for non-ASCII filenames."""
    for filename in EDGE_CASE_FILENAMES:
        session = get_session_manager(client).get_session(SESSION_ID)
        assert session
        session.app_file_manager.filename = filename
        response = client.post(
            "/api/export/ipynb",
            headers=HEADERS,
            json={
                "download": True,
            },
        )
        assert response.status_code == 200, f"Failed for filename: {filename}"
        assert "Content-Disposition" in response.headers
        assert "attachment" in response.headers["Content-Disposition"]


@with_session(SESSION_ID)
def test_update_cell_outputs_new_cell(client: TestClient) -> None:
    """Test updating cell outputs for a cell with no existing output."""
    session = get_session_manager(client).get_session(SESSION_ID)
    assert session

    # Create a cell notification without output
    cell_id = CellId_t("test_cell")
    session.session_view.cell_notifications[cell_id] = CellNotification(
        cell_id=cell_id,
        output=None,
        status="idle",
    )

    response = client.post(
        "/api/export/update_cell_outputs",
        headers=HEADERS,
        json={
            "cellIdsToOutput": {
                cell_id: ["image/png", "data:image/png;base64,iVBORw0KGgo="]
            }
        },
    )

    assert response.status_code == 200
    assert response.json() == {"success": True}
    assert session.session_view.needs_export("ipynb")

    # Verify output was created
    cell_notification = session.session_view.cell_notifications[cell_id]
    assert cell_notification.output is not None
    assert cell_notification.output == CellOutput(
        channel=CellChannel.OUTPUT,
        mimetype="image/png",
        data="data:image/png;base64,iVBORw0KGgo=",
        timestamp=cell_notification.output.timestamp,
    )


@with_session(SESSION_ID)
def test_update_cell_outputs_missing_cell(client: TestClient) -> None:
    """Test updating cell outputs for non-existent cell logs warning."""
    response = client.post(
        "/api/export/update_cell_outputs",
        headers=HEADERS,
        json={
            "cellIdsToOutput": {
                "nonexistent_cell": ["image/png", "data:image/png;base64,test"]
            }
        },
    )

    # Should succeed but log a warning
    assert response.status_code == 200
    assert response.json() == {"success": True}


@with_session(SESSION_ID)
def test_update_cell_outputs_empty_request(client: TestClient) -> None:
    """Test updating cell outputs with empty cellIdsToOutput."""
    response = client.post(
        "/api/export/update_cell_outputs",
        headers=HEADERS,
        json={"cellIdsToOutput": {}},
    )

    # Should succeed even with empty request
    assert response.status_code == 200
    assert response.json() == {"success": True}


@with_session(SESSION_ID)
def test_export_pdf_endpoint(client: TestClient) -> None:
    from unittest.mock import AsyncMock, patch

    session = get_session_manager(client).get_session(SESSION_ID)
    assert session
    session.app_file_manager.filename = "test.py"

    render_pdf_mock = AsyncMock(return_value=b"mock_pdf_content")
    with patch(
        "marimo._server.api.endpoints.export.render_pdf",
        render_pdf_mock,
    ):
        response = client.post(
            "/api/export/pdf",
            headers=HEADERS,
            json={"webpdf": False},
        )

    assert response.status_code == 200
    assert response.content == b"mock_pdf_content"
    assert response.headers["content-type"] == "application/pdf"
    assert (
        response.headers["content-disposition"]
        == "attachment; filename*=UTF-8''test.pdf"
    )
    render_pdf_mock.assert_awaited_once_with(
        PDFExportRequest(
            app=session.app_file_manager.app,
            session_view=session.session_view,
            options=PDFExportOptions(
                webpdf=False,
                preset="document",
                include_inputs=False,
            ),
        )
    )


@with_session(SESSION_ID)
def test_export_pdf_endpoint_uses_requested_options(
    client: TestClient,
) -> None:
    from unittest.mock import AsyncMock, patch

    session = get_session_manager(client).get_session(SESSION_ID)
    assert session
    session.app_file_manager.filename = "test.py"

    render_pdf_mock = AsyncMock(return_value=b"mock_pdf_content")
    with patch(
        "marimo._server.api.endpoints.export.render_pdf",
        render_pdf_mock,
    ):
        response = client.post(
            "/api/export/pdf",
            headers=HEADERS,
            json={
                "webpdf": True,
                "preset": "slides",
                "includeInputs": False,
                "includeOutputs": False,
            },
        )

    assert response.status_code == 200
    render_pdf_mock.assert_awaited_once_with(
        PDFExportRequest(
            app=session.app_file_manager.app,
            session_view=None,
            options=PDFExportOptions(
                webpdf=True,
                preset="slides",
                include_inputs=False,
            ),
        )
    )


@with_session(SESSION_ID)
def test_export_pdf_endpoint_uses_browser_captured_outputs(
    client: TestClient,
) -> None:
    from unittest.mock import AsyncMock, patch

    session = get_session_manager(client).get_session(SESSION_ID)
    assert session
    session.app_file_manager.filename = "test.py"
    cell_id = CellId_t("test_cell")
    session.session_view.cell_notifications[cell_id] = CellNotification(
        cell_id=cell_id,
        output=CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="text/html",
            data="<div>current output</div>",
        ),
        status="idle",
    )

    capture_response = client.post(
        "/api/export/update_cell_outputs",
        headers=HEADERS,
        json={
            "cellIdsToOutput": {
                cell_id: ["image/png", "data:image/png;base64,ZmFrZQ=="]
            }
        },
    )
    assert capture_response.status_code == 200

    render_pdf_mock = AsyncMock(return_value=b"mock_pdf_content")
    with patch(
        "marimo._server.api.endpoints.export.render_pdf",
        render_pdf_mock,
    ):
        response = client.post(
            "/api/export/pdf",
            headers=HEADERS,
            json={"webpdf": False, "includeOutputs": True},
        )

    assert response.status_code == 200
    render_request = render_pdf_mock.await_args.args[0]
    assert isinstance(render_request, PDFExportRequest)
    assert render_request.session_view is session.session_view
    captured_output = render_request.session_view.cell_notifications[
        cell_id
    ].output
    assert captured_output is not None
    assert captured_output == CellOutput(
        channel=CellChannel.OUTPUT,
        mimetype="application/vnd.marimo+mimebundle",
        data={
            "text/html": "<div>current output</div>",
            "image/png": "data:image/png;base64,ZmFrZQ==",
        },
        timestamp=captured_output.timestamp,
    )


@with_session(SESSION_ID)
def test_export_pdf_endpoint_returns_error_on_failure(
    client: TestClient,
) -> None:
    """Test PDF export endpoint returns error when export fails."""
    from unittest.mock import AsyncMock, patch

    session = get_session_manager(client).get_session(SESSION_ID)
    assert session
    session.app_file_manager.filename = "test.py"

    render_pdf_mock = AsyncMock(return_value=None)

    with patch(
        "marimo._server.api.endpoints.export.render_pdf",
        render_pdf_mock,
    ):
        response = client.post(
            "/api/export/pdf",
            headers=HEADERS,
            json={"webpdf": False},
        )

    assert response.status_code == 500
    assert "Failed to export PDF" in response.text
