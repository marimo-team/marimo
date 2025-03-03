from __future__ import annotations

import textwrap
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, TypeVar
from unittest.mock import patch

from marimo._config.config import PartialMarimoConfig, merge_default_config
from marimo._config.manager import (
    MarimoConfigManager,
    MarimoConfigReaderWithOverrides,
    ScriptConfigManager,
    UserConfigManager,
    get_default_config_manager,
)

if TYPE_CHECKING:
    from pathlib import Path

F = TypeVar("F", bound=Callable[..., Any])


def restore_config(f: F) -> F:
    config = UserConfigManager().get_config()

    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return f(*args, **kwargs)
        finally:
            UserConfigManager().save_config(config)

    return wrapper  # type: ignore


@restore_config
@patch("tomlkit.dump")
def test_save_config(mock_dump: Any) -> None:
    mock_config = merge_default_config(PartialMarimoConfig())
    manager = UserConfigManager()
    manager._load_config = lambda: mock_config

    result = manager.save_config(mock_config)

    assert result == mock_config

    assert mock_dump.mock_calls[0][1][0] == mock_config


@restore_config
@patch("tomlkit.dump")
def test_can_save_secrets(mock_dump: Any) -> None:
    mock_config = merge_default_config(PartialMarimoConfig())
    manager = UserConfigManager()
    manager._load_config = lambda: mock_config

    new_config = manager.save_config(
        merge_default_config(
            PartialMarimoConfig(ai={"open_ai": {"api_key": "super_secret"}})
        )
    )
    manager._load_config = lambda: new_config

    assert (
        mock_dump.mock_calls[0][1][0]["ai"]["open_ai"]["api_key"]
        == "super_secret"
    )

    # Do not overwrite secrets
    manager.save_config(
        merge_default_config(
            PartialMarimoConfig(ai={"open_ai": {"api_key": "********"}})
        )
    )
    assert (
        mock_dump.mock_calls[1][1][0]["ai"]["open_ai"]["api_key"]
        == "super_secret"
    )


@restore_config
def test_can_read_secrets() -> None:
    manager = UserConfigManager()
    mock_config = merge_default_config(
        PartialMarimoConfig(ai={"open_ai": {"api_key": "super_secret"}})
    )
    manager._load_config = lambda: mock_config

    assert manager.get_config()["ai"]["open_ai"]["api_key"] == "********"
    assert (
        manager.get_config(hide_secrets=False)["ai"]["open_ai"]["api_key"]
        == "super_secret"
    )


@restore_config
def test_get_config() -> None:
    mock_config = merge_default_config(PartialMarimoConfig())
    manager = UserConfigManager()
    manager._load_config = lambda: mock_config

    result = manager.get_config()

    assert result == mock_config


@restore_config
def test_get_config_with_override() -> None:
    mock_config = merge_default_config(PartialMarimoConfig())
    user = UserConfigManager()
    user._load_config = lambda: mock_config

    manager = MarimoConfigManager(
        user,
        MarimoConfigReaderWithOverrides(
            {
                "runtime": {
                    "on_cell_change": "autorun",
                    "auto_instantiate": True,
                    "auto_reload": "lazy",
                    "watcher_on_save": "lazy",
                }
            }
        ),
    )
    assert manager.get_config()["runtime"]["auto_reload"] == "lazy"

    manager = get_default_config_manager(current_path=None).with_overrides(
        {
            "runtime": {
                "on_cell_change": "autorun",
                "auto_instantiate": True,
                "auto_reload": "lazy",
                "watcher_on_save": "lazy",
            }
        }
    )
    assert manager.get_config()["runtime"]["auto_reload"] == "lazy"


@restore_config
def test_with_multiple_overrides() -> None:
    manager = get_default_config_manager(current_path=None).with_overrides(
        {
            "package_management": {
                "manager": "pixi",
            }
        }
    )
    assert manager.get_config()["package_management"]["manager"] == "pixi"

    next_manager = manager.with_overrides(
        {
            "package_management": {
                "manager": "uv",
            }
        }
    )
    assert next_manager.get_config()["package_management"]["manager"] == "uv"

    assert manager.get_config()["package_management"]["manager"] == "pixi"


def test_project_config_manager_with_script_metadata(tmp_path: Path) -> None:
    # Create a notebook file with script metadata
    notebook_path = tmp_path / "notebook.py"
    notebook_content = """
    # /// script
    # requires-python = ">=3.11"
    # dependencies = ["polars"]
    # [tool.marimo]
    # formatting = {line_length = 79}
    # [tool.marimo.save]
    # autosave_delay = 1000
    # ///

    import marimo as mo
    """
    notebook_path.write_text(textwrap.dedent(notebook_content))

    # Create a pyproject.toml file
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_content = """
    [tool.marimo]
    formatting = {line_length = 100}
    [tool.marimo.save]
    format_on_save = true
    autosave = "after_delay"
    """
    pyproject_path.write_text(textwrap.dedent(pyproject_content))

    # Initialize ProjectConfigManager with the notebook path
    manager = get_default_config_manager(current_path=str(notebook_path))
    config = manager.get_config_overrides(hide_secrets=False)

    # Verify that script metadata takes precedence over pyproject.toml
    assert config == {
        "formatting": {"line_length": 79},  # From script metadata
        "save": {
            "autosave_delay": 1000,  # From script metadata
            "format_on_save": True,  # From pyproject.toml
            "autosave": "after_delay",  # From pyproject.toml
        },
    }


def test_script_config_manager_empty_file(tmp_path: Path) -> None:
    notebook_path = tmp_path / "notebook.py"
    notebook_path.write_text("import marimo as mo")

    manager = ScriptConfigManager(str(notebook_path))
    assert manager.get_config() == {}


def test_script_config_manager_no_file() -> None:
    manager = ScriptConfigManager(None)
    assert manager.get_config() == {}


def test_script_config_manager_with_metadata(tmp_path: Path) -> None:
    notebook_path = tmp_path / "notebook.py"
    notebook_content = """
    # /// script
    # [tool.marimo]
    # formatting = {line_length = 79}
    # [tool.marimo.save]
    # autosave_delay = 1000
    # ///
    import marimo as mo
    """
    notebook_path.write_text(textwrap.dedent(notebook_content))

    manager = ScriptConfigManager(str(notebook_path))
    assert manager.get_config() == {
        "formatting": {"line_length": 79},
        "save": {"autosave_delay": 1000},
    }


def test_script_config_manager_invalid_toml(tmp_path: Path) -> None:
    notebook_path = tmp_path / "notebook.py"
    notebook_content = """
    # /// script
    # [invalid toml
    # ///
    """
    notebook_path.write_text(textwrap.dedent(notebook_content))

    manager = ScriptConfigManager(str(notebook_path))
    assert manager.get_config() == {}


def test_script_config_manager_no_marimo_section(tmp_path: Path) -> None:
    notebook_path = tmp_path / "notebook.py"
    notebook_content = """
    # /// script
    # [tool.other]
    # key = "value"
    # ///
    """
    notebook_path.write_text(textwrap.dedent(notebook_content))

    manager = ScriptConfigManager(str(notebook_path))
    assert manager.get_config() == {}


def test_marimo_config_reader_properties() -> None:
    """Test the convenience properties on MarimoConfigReader"""

    manager = get_default_config_manager(current_path=None)
    assert manager.default_width is not None
    assert manager.theme is not None
    assert manager.package_manager is not None
