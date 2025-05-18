# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Callable

import pytest

from marimo._config.config import DEFAULT_CONFIG
from marimo._pyodide.bootstrap import create_session, save_file
from marimo._pyodide.pyodide_session import PyodideSession
from marimo._server.model import SessionMode
from marimo._server.models.models import SaveNotebookRequest
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def mock_message_callback() -> Callable[[str], None]:
    def callback(message: str) -> None:
        pass

    return callback


FILE_CONTENTS = """
import marimo

app = marimo.App()

@app.cell
def _():
    "Hello"
    return
"""


@pytest.fixture
def mock_app_file(tmp_path: Path) -> Path:
    filename = tmp_path / "test.py"
    filename.write_text(FILE_CONTENTS)
    return filename


@pytest.fixture
def mock_app_file_with_script_config(tmp_path: Path) -> Path:
    filename = tmp_path / "test.py"
    content = f"""# /// script
# [tool.marimo.runtime]
# auto_instantiate = false
# on_cell_change = "lazy"
# [tool.marimo.display]
# theme = "dark"
# ///

{FILE_CONTENTS}
"""
    filename.write_text(content)
    return filename


async def test_create_session_with_default_config(
    mock_message_callback: Callable[[str], None],
    mock_app_file: Path,
) -> None:
    session, _ = create_session(
        filename=str(mock_app_file),
        query_params={},
        message_callback=mock_message_callback,
        user_config=DEFAULT_CONFIG,
    )

    assert isinstance(session, PyodideSession)
    assert session.mode == SessionMode.EDIT


async def test_create_session_with_script_config(
    mock_message_callback: Callable[[str], None],
    mock_app_file_with_script_config: Path,
) -> None:
    session, _ = create_session(
        filename=str(mock_app_file_with_script_config),
        query_params={},
        message_callback=mock_message_callback,
        user_config=DEFAULT_CONFIG,
    )

    # Script config should override default theme
    assert session._initial_user_config["display"]["theme"] == "dark"


async def test_create_session_with_invalid_script_config(
    mock_message_callback: Callable[[str], None],
    tmp_path: Path,
) -> None:
    # Create a file with invalid config
    filename = tmp_path / "test.py"
    content = """# ---
# marimo:
#   invalid: true
# ---

{FILE_CONTENTS}
"""
    filename.write_text(content)

    session, _ = create_session(
        filename=str(filename),
        query_params={},
        message_callback=mock_message_callback,
        user_config=DEFAULT_CONFIG,
    )

    # Invalid config should be ignored and default config should be used
    assert (
        session._initial_user_config["display"]["theme"]
        == DEFAULT_CONFIG["display"]["theme"]
    )


async def test_instantiate(
    mock_message_callback: Callable[[str], None],
    mock_app_file: Path,
) -> None:
    session, _ = create_session(
        filename=str(mock_app_file),
        query_params={},
        message_callback=mock_message_callback,
        user_config=DEFAULT_CONFIG,
    )

    # Mock the put_control_request method to capture the request
    captured_request = None
    original_put_control_request = session.put_control_request

    def mock_put_control_request(request: Any) -> None:
        nonlocal captured_request
        captured_request = request
        original_put_control_request(request)

    session.put_control_request = mock_put_control_request

    # Call instantiate
    from marimo._pyodide.bootstrap import instantiate

    instantiate(session)

    # Verify the request was created correctly
    assert captured_request is not None
    assert len(captured_request.execution_requests) == 1
    assert captured_request.execution_requests[0].code == '"Hello"'
    assert captured_request.auto_run is True


def test_save_file(
    mock_app_file: Path,
) -> None:
    # Create a save request
    request = SaveNotebookRequest(
        codes=["print('hello')"],
        names=["cell-1"],
        configs=[{}],
        cell_ids=[CellId_t("cell-1")],
        layout=None,
        filename=str(mock_app_file),
    )

    # Save the file
    save_file(
        request=json.dumps(request.__dict__),
        filename=str(mock_app_file),
    )

    # Verify the file was saved correctly
    saved_content = mock_app_file.read_text()
    assert "print('hello')" in saved_content
