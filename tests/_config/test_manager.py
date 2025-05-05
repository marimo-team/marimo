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
        "runtime": {
            "dotenv": [str(tmp_path / ".env")],
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


def test_project_config_manager_resolve_paths(tmp_path: Path) -> None:
    # Create a pyproject.toml with pythonpath and dotenv settings
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_content = """
    [tool.marimo.runtime]
    pythonpath = ["src", "lib"]
    dotenv = [".env", "config/.env"]
    """
    pyproject_path.write_text(textwrap.dedent(pyproject_content))

    # Create the directory structure
    (tmp_path / "src").mkdir()
    (tmp_path / "lib").mkdir()
    (tmp_path / "config").mkdir()
    (tmp_path / ".env").touch()
    (tmp_path / "config" / ".env").touch()

    # Initialize ProjectConfigManager
    manager = get_default_config_manager(current_path=str(pyproject_path))
    config = manager.get_config(hide_secrets=False)

    # Verify pythonpath resolution
    expected_pythonpath = [
        str((tmp_path / "src").absolute()),
        str((tmp_path / "lib").absolute()),
    ]
    assert config["runtime"]["pythonpath"] == expected_pythonpath

    # Verify dotenv resolution
    expected_dotenv = [
        str((tmp_path / ".env").absolute()),
        str((tmp_path / "config" / ".env").absolute()),
    ]
    assert config["runtime"]["dotenv"] == expected_dotenv


def test_project_config_manager_resolve_invalid_paths(tmp_path: Path) -> None:
    # Create a pyproject.toml with invalid path types
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_content = """
    [tool.marimo.runtime]
    pythonpath = "not_a_list"
    dotenv = 123
    """
    pyproject_path.write_text(textwrap.dedent(pyproject_content))

    # Initialize ProjectConfigManager
    manager = get_default_config_manager(current_path=str(pyproject_path))
    config = manager.get_config(hide_secrets=False)

    # Verify invalid paths are not modified
    assert config["runtime"]["pythonpath"] == "not_a_list"
    assert config["runtime"]["dotenv"] == 123


def test_project_config_manager_resolve_missing_paths(tmp_path: Path) -> None:
    # Create a pyproject.toml without path settings
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_content = """
    [tool.marimo.runtime]
    other_setting = "value"
    """
    pyproject_path.write_text(textwrap.dedent(pyproject_content))

    # Initialize ProjectConfigManager
    manager = get_default_config_manager(current_path=str(pyproject_path))
    config = manager.get_config(hide_secrets=False)

    # Verify missing paths don't cause issues
    assert config["runtime"].get("pythonpath", []) == []
    assert config["runtime"]["dotenv"] == [str(tmp_path / ".env")]
    assert config["runtime"]["other_setting"] == "value"


def test_project_config_manager_resolve_custom_css(tmp_path: Path) -> None:
    # Create a pyproject.toml with custom_css paths
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_content = """
    [tool.marimo.display]
    custom_css = ["styles.css", "themes/dark.css"]
    """
    pyproject_path.write_text(textwrap.dedent(pyproject_content))

    # Initialize ProjectConfigManager
    manager = get_default_config_manager(current_path=str(pyproject_path))
    config = manager.get_config(hide_secrets=False)

    # Verify custom_css paths are resolved correctly
    expected_custom_css = [
        str((tmp_path / "styles.css").absolute()),
        str((tmp_path / "themes" / "dark.css").absolute()),
    ]
    assert config["display"]["custom_css"] == expected_custom_css


def test_project_config_manager_resolve_invalid_custom_css(
    tmp_path: Path,
) -> None:
    # Create a pyproject.toml with invalid custom_css type
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_content = """
    [tool.marimo.display]
    custom_css = "not_a_list"
    """
    pyproject_path.write_text(textwrap.dedent(pyproject_content))

    # Initialize ProjectConfigManager
    # Initialize ProjectConfigManager
    manager = get_default_config_manager(current_path=str(pyproject_path))
    config = manager.get_config(hide_secrets=False)

    # Verify invalid custom_css is not modified
    assert config["display"]["custom_css"] == "not_a_list"
