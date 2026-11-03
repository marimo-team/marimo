# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from marimo._config.config import DEFAULT_CONFIG
from marimo._pyodide.bootstrap import create_session
from marimo._pyodide.pyodide_session import PyodideSession
from marimo._session.model import SessionMode

if TYPE_CHECKING:
    from pathlib import Path


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
    mock_app_file: Path,
) -> None:
    session, _ = create_session(
        filename=str(mock_app_file),
        query_params={},
        user_config=DEFAULT_CONFIG,
    )

    assert isinstance(session, PyodideSession)
    assert session.mode == SessionMode.EDIT


async def test_create_session_with_script_config(
    mock_app_file_with_script_config: Path,
) -> None:
    session, _ = create_session(
        filename=str(mock_app_file_with_script_config),
        query_params={},
        user_config=DEFAULT_CONFIG,
    )

    # Script config should override default theme
    assert session._initial_user_config["display"]["theme"] == "dark"


async def test_create_session_with_invalid_script_config(
    tmp_path: Path,
) -> None:
    # Create a file with invalid config
    filename = tmp_path / "test.py"
    content = f"""# ---
# marimo:
#   invalid: true
# ---

{FILE_CONTENTS}
"""
    filename.write_text(content)

    session, _ = create_session(
        filename=str(filename),
        query_params={},
        user_config=DEFAULT_CONFIG,
    )

    # Invalid config should be ignored and default config should be used
    assert (
        session._initial_user_config["display"]["theme"]
        == DEFAULT_CONFIG["display"]["theme"]
    )


async def test_instantiate(
    mock_app_file: Path,
) -> None:
    session, _ = create_session(
        filename=str(mock_app_file),
        query_params={},
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
