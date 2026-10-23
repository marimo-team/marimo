from __future__ import annotations

import os
import tempfile
from typing import TYPE_CHECKING

import pytest

from marimo import _loggers
from marimo._config.config import merge_default_config
from marimo._config.manager import UserConfigStore, get_default_config_manager
from marimo._runtime.commands import (
    CreateNotebookCommand,
    UpdateUIElementCommand,
)
from marimo._utils.platform import is_windows
from tests.conftest import MockedKernel

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("inferred", "inferred"),
        ("user", "custom"),
        ("project", "custom"),
        ("script", "custom"),
        ("multiple", "custom"),
        ("empty_user", None),
        ("empty_project", None),
        ("empty_script", None),
    ],
)
def test_load_resolved_dotenv_paths(
    mocked_kernel: MockedKernel,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    expected: str | None,
) -> None:
    for key in (
        "DOTENV_READER_VALUE",
        "DOTENV_READER_DEFAULT_ONLY",
        "DOTENV_READER_SECONDARY",
    ):
        monkeypatch.setenv(key, "before")
        monkeypatch.delenv(key)
    monkeypatch.setenv("DOTENV_READER_EXISTING", "shell")
    (tmp_path / ".env").write_text(
        "DOTENV_READER_VALUE=inferred\nDOTENV_READER_DEFAULT_ONLY=present\n"
    )
    custom = tmp_path / "custom.env"
    custom.write_text(
        "DOTENV_READER_VALUE=custom\nDOTENV_READER_EXISTING=file\n"
    )
    (tmp_path / "shared.env").write_text(
        "DOTENV_READER_VALUE=second\nDOTENV_READER_SECONDARY=second\n"
    )
    user = tmp_path / "marimo.toml"
    user.write_text(
        f'[runtime]\ndotenv = ["{custom.as_posix()}"]\n'
        if source == "user"
        else "[runtime]\ndotenv = []\n"
        if source == "empty_user"
        else ""
    )
    monkeypatch.setattr(
        UserConfigStore, "get_config_path", lambda _self: str(user)
    )
    project = tmp_path / "pyproject.toml"
    project_settings = {
        "project": '[tool.marimo.runtime]\ndotenv = ["custom.env"]\n',
        "empty_project": "[tool.marimo.runtime]\ndotenv = []\n",
        "multiple": '[tool.marimo.runtime]\ndotenv = ["custom.env", "shared.env"]\n',
    }
    project.write_text(project_settings.get(source, ""))
    notebooks = tmp_path / "notebooks"
    notebooks.mkdir()
    notebook = notebooks / "app.py"
    notebook.write_text(
        '# /// script\n# [tool.marimo.runtime]\n# dotenv = ["custom.env"]\n# ///\n'
        if source == "script"
        else "# /// script\n# [tool.marimo.runtime]\n# dotenv = []\n# ///\n"
        if source == "empty_script"
        else ""
    )
    manager = get_default_config_manager(current_path=str(notebook))
    mocked_kernel.k.user_config = manager.get_config(hide_secrets=False)
    mocked_kernel.k.load_dotenv()
    assert {
        key: os.environ.get(key)
        for key in (
            "DOTENV_READER_VALUE",
            "DOTENV_READER_DEFAULT_ONLY",
            "DOTENV_READER_EXISTING",
            "DOTENV_READER_SECONDARY",
        )
    } == {
        "DOTENV_READER_VALUE": expected,
        "DOTENV_READER_DEFAULT_ONLY": "present"
        if source == "inferred"
        else None,
        "DOTENV_READER_EXISTING": "shell",
        "DOTENV_READER_SECONDARY": "second" if source == "multiple" else None,
    }


# These tests work with and without python-dotenv installed.


@pytest.mark.skipif(
    is_windows(),
    reason="Does not work on Windows",
)
def test_load_dotenv_success(mocked_kernel: MockedKernel):
    # Create a temporary .env file
    with tempfile.NamedTemporaryFile(suffix=".env", mode="w+") as env_file:
        env_file.write("TEST_VAR=test_value\n")
        env_file.write("ANOTHER_VAR=another_value\n")
        env_file.flush()

        # Create a custom config with the path to our temp .env file
        custom_config = merge_default_config(
            {
                "runtime": {
                    "dotenv": [env_file.name],
                },
            }
        )
        mocked_kernel.k.user_config = custom_config

        # Load the .env file
        mocked_kernel.k.load_dotenv()

        # Check that the environment variables were set
        assert os.environ.get("TEST_VAR") == "test_value"
        assert os.environ.get("ANOTHER_VAR") == "another_value"


def test_load_dotenv_nonexistent_file(
    mocked_kernel: MockedKernel,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing = tmp_path / "missing.env"
    other_missing = tmp_path / "also-missing.env"
    valid = tmp_path / "valid.env"
    valid.write_text("DOTENV_AFTER_MISSING=loaded\n")
    monkeypatch.setenv("DOTENV_AFTER_MISSING", "before")
    monkeypatch.delenv("DOTENV_AFTER_MISSING")
    custom_config = merge_default_config(
        {
            "runtime": {
                "dotenv": [str(missing), str(valid), str(other_missing)],
            },
        }
    )
    mocked_kernel.k.user_config = custom_config

    with _loggers.capture_output() as (_, _, records):
        mocked_kernel.k.load_dotenv()
    assert [(record.levelname, record.getMessage()) for record in records] == [
        ("WARNING", f"Dotenv file not found: {missing}"),
        ("WARNING", f"Dotenv file not found: {other_missing}"),
    ]
    assert os.environ["DOTENV_AFTER_MISSING"] == "loaded"


@pytest.mark.skipif(
    is_windows(),
    reason="Does not work on Windows",
)
async def test_load_dotenv_on_instantiate(mocked_kernel: MockedKernel):
    # Create a temporary .env file
    with tempfile.NamedTemporaryFile(suffix=".env", mode="w+") as env_file:
        env_file.write("INSTANTIATE_TEST_VAR=instantiate_value\n")
        env_file.flush()

        # Create a custom config with the path to our temp .env file
        custom_config = merge_default_config(
            {
                "runtime": {
                    "dotenv": [env_file.name],
                },
            }
        )
        mocked_kernel.k.user_config = custom_config

        # Create a CreationRequest
        request = CreateNotebookCommand(
            execution_requests=(),
            cell_ids=(),
            set_ui_element_value_request=UpdateUIElementCommand(
                object_ids=[],
                values=[],
            ),
            auto_run=True,
        )

        # Call instantiate, which should call load_dotenv
        await mocked_kernel.k.instantiate(request)

        # Check that the environment variable was set
        assert os.environ.get("INSTANTIATE_TEST_VAR") == "instantiate_value"
