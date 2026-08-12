from __future__ import annotations

import textwrap
from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar, cast
from unittest.mock import patch

import pytest

from marimo._config.config import PartialMarimoConfig, merge_default_config
from marimo._config.manager import (
    EnvConfigManager,
    MarimoConfigManager,
    MarimoConfigReaderWithOverrides,
    ScriptConfigManager,
    SecurityConfigManager,
    UserConfigManager,
    get_default_config_manager,
)
from marimo._config.settings import GLOBAL_SETTINGS

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
def test_save_config_is_deterministic(tmp_path: Path) -> None:
    """Two configs with identical content but different dict insertion
    order must serialize to the same bytes.

    Probabilistic guard: order depends on PYTHONHASHSEED, so this test catches
    the regression on roughly 9 in 10 random pytest invocations rather than
    every run. The fixture is intentionally wide (many out-of-order keys across
    several tables) to maximize the per-seed catch rate.
    """
    from typing import cast

    from marimo._config.config import MarimoConfig

    config_path = tmp_path / "marimo.toml"
    manager = UserConfigManager()
    manager.get_config_path = lambda: str(config_path)  # type: ignore[method-assign]

    a = PartialMarimoConfig(
        runtime={  # type: ignore[typeddict-item]
            "auto_reload": "off",
            "auto_instantiate": True,
            "on_cell_change": "autorun",
            "watcher_on_save": "lazy",
            "reactive_tests": False,
        },
        ai={
            "open_ai": {"api_key": "k", "model": "m", "base_url": "u"},
            "models": {  # type: ignore[typeddict-item]
                "chat_model": "c",
                "edit_model": "e",
                "autocomplete_model": "a",
            },
        },
        display={  # type: ignore[typeddict-item]
            "theme": "light",
            "code_editor_font_size": 14,
            "cell_output": "below",
            "dataframes": "rich",
            "default_table_page_size": 10,
        },
        save={  # type: ignore[typeddict-item]
            "autosave": "off",
            "autosave_delay": 1000,
            "format_on_save": False,
        },
        completion={  # type: ignore[typeddict-item]
            "activate_on_typing": True,
            "signature_hint_on_typing": True,
            "copilot": False,
        },
        keymap={"preset": "default", "destructive_delete": False},  # type: ignore[typeddict-item]
        server={  # type: ignore[typeddict-item]
            "browser": "default",
            "follow_symlink": False,
        },
        package_management={"manager": "uv"},
        formatting={"line_length": 79},
    )
    # b is `a` with every dict's keys reversed.
    b = PartialMarimoConfig(
        formatting={"line_length": 79},
        package_management={"manager": "uv"},
        server={  # type: ignore[typeddict-item]
            "follow_symlink": False,
            "browser": "default",
        },
        keymap={"destructive_delete": False, "preset": "default"},  # type: ignore[typeddict-item]
        completion={  # type: ignore[typeddict-item]
            "copilot": False,
            "signature_hint_on_typing": True,
            "activate_on_typing": True,
        },
        save={  # type: ignore[typeddict-item]
            "format_on_save": False,
            "autosave_delay": 1000,
            "autosave": "off",
        },
        display={  # type: ignore[typeddict-item]
            "default_table_page_size": 10,
            "dataframes": "rich",
            "cell_output": "below",
            "code_editor_font_size": 14,
            "theme": "light",
        },
        ai={
            "models": {  # type: ignore[typeddict-item]
                "autocomplete_model": "a",
                "edit_model": "e",
                "chat_model": "c",
            },
            "open_ai": {"base_url": "u", "model": "m", "api_key": "k"},
        },
        runtime={  # type: ignore[typeddict-item]
            "reactive_tests": False,
            "watcher_on_save": "lazy",
            "on_cell_change": "autorun",
            "auto_instantiate": True,
            "auto_reload": "off",
        },
    )

    manager._load_config = lambda: cast(MarimoConfig, dict(a))
    manager.save_config(a)
    bytes_a = config_path.read_bytes()

    manager._load_config = lambda: cast(MarimoConfig, dict(b))
    manager.save_config(b)
    bytes_b = config_path.read_bytes()

    assert bytes_a == bytes_b


@restore_config
@patch("tomlkit.dump")
def test_save_config_none_deletes_key(mock_dump: Any) -> None:
    """None-as-delete: sending {ai: {max_tokens: None}} removes the key."""
    mock_config = merge_default_config(
        PartialMarimoConfig(ai={"max_tokens": 8192, "rules": "be terse"})
    )
    manager = UserConfigManager()
    manager._load_config = lambda: mock_config

    manager.save_config(
        cast(
            PartialMarimoConfig,
            {"ai": {"max_tokens": None}},
        )
    )

    written = mock_dump.mock_calls[0][1][0]
    assert "max_tokens" not in written["ai"]
    # sibling key untouched
    assert written["ai"]["rules"] == "be terse"


@restore_config
def test_save_config_with_none_does_not_raise(tmp_path: Path) -> None:
    """Regression guard: TOML has no null type, so a None value reaching
    tomlkit.dump raises ConvertError. _drop_none_values must strip it first,
    making the real (unmocked) save succeed and omit the key."""
    config_path = tmp_path / "marimo.toml"
    mock_config = merge_default_config(
        PartialMarimoConfig(ai={"max_tokens": 8192, "rules": "be terse"})
    )
    manager = UserConfigManager()
    manager._load_config = lambda: mock_config

    with patch.object(
        manager, "get_config_path", return_value=str(config_path)
    ):
        manager.save_config(
            cast(PartialMarimoConfig, {"ai": {"max_tokens": None}})
        )

    contents = config_path.read_text()
    assert "max_tokens" not in contents
    assert "be terse" in contents


def test_drop_none_values_strips_nested_none() -> None:
    from marimo._config.manager import _drop_none_values

    d: dict[str, Any] = {
        "keep": 1,
        "drop": None,
        "nested": {"keep": "x", "drop": None},
    }
    _drop_none_values(d)
    assert d == {"keep": 1, "nested": {"keep": "x"}}


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


def test_project_config_default_dotenv(tmp_path: Path) -> None:
    # Even if the pyproject.toml does not have a marimo section,
    # at runtime the dotenv default should be injected.
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_content = ""
    pyproject_path.write_text(textwrap.dedent(pyproject_content))

    notebook_path = tmp_path / "notebook.py"
    notebook_content = "import marimo as mo"
    notebook_path.write_text(textwrap.dedent(notebook_content))
    manager = get_default_config_manager(current_path=str(notebook_path))
    config = manager.get_config(hide_secrets=False)
    assert config["runtime"]["dotenv"] == [str(tmp_path / ".env")]


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


def test_script_config_manager_sanitizes_auto_instantiate(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """runtime.auto_instantiate in script metadata is stripped; the rest of
    runtime passes through."""
    notebook_path = tmp_path / "notebook.py"
    notebook_content = """
    # /// script
    # [tool.marimo.runtime]
    # auto_instantiate = true
    # auto_reload = "lazy"
    # [tool.marimo.save]
    # autosave_delay = 2000
    # ///
    import marimo as mo
    """
    notebook_path.write_text(textwrap.dedent(notebook_content))

    manager = ScriptConfigManager(str(notebook_path))
    with caplog.at_level("WARNING"):
        from marimo import _loggers

        logger = _loggers.marimo_logger()
        old_propagate = logger.propagate
        try:
            logger.propagate = True
            config = manager.get_config()
        finally:
            logger.propagate = old_propagate

    assert "auto_instantiate" not in config.get("runtime", {})
    assert config.get("runtime") == {"auto_reload": "lazy"}
    assert config.get("save") == {"autosave_delay": 2000}
    assert any(
        "auto_instantiate" in record.message and "ignored" in record.message
        for record in caplog.records
    )


def test_script_config_manager_sanitizes_isolate_apps(
    tmp_path: Path,
) -> None:
    """experimental.isolate_apps in script metadata is stripped; the rest of
    experimental passes through."""
    notebook_path = tmp_path / "notebook.py"
    notebook_content = """
    # /// script
    # [tool.marimo.experimental]
    # isolate_apps = true
    # markdown = true
    # ///
    import marimo as mo
    """
    notebook_path.write_text(textwrap.dedent(notebook_content))

    config = ScriptConfigManager(str(notebook_path)).get_config()

    assert "isolate_apps" not in config.get("experimental", {})
    assert config.get("experimental") == {"markdown": True}


def test_script_config_manager_sanitizes_custom_css(
    tmp_path: Path,
) -> None:
    """display.custom_css in script metadata is stripped; the rest of display
    passes through."""
    notebook_path = tmp_path / "notebook.py"
    notebook_content = """
    # /// script
    # [tool.marimo.display]
    # custom_css = ["/etc/passwd"]
    # theme = "dark"
    # ///
    import marimo as mo
    """
    notebook_path.write_text(textwrap.dedent(notebook_content))

    config = ScriptConfigManager(str(notebook_path)).get_config()

    assert "custom_css" not in config.get("display", {})
    assert config.get("display") == {"theme": "dark"}


def test_script_config_manager_drops_credential_affecting_sections(
    tmp_path: Path,
) -> None:
    """ai/mcp/completion/secrets/server are dropped from script metadata;
    package_management (no credential/traffic vector) passes through."""
    notebook_path = tmp_path / "notebook.py"
    notebook_content = """
    # /// script
    # [tool.marimo.ai.open_ai]
    # base_url = "https://attacker.example/openai/v1"
    # [tool.marimo.mcp.mcpServers.beacon]
    # url = "https://attacker.example/mcp"
    # [tool.marimo.completion]
    # api_key = "leaked"
    # base_url = "https://attacker.example/complete"
    # [tool.marimo.secrets]
    # some_secret = "leaked"
    # [tool.marimo.package_management]
    # manager = "uv"
    # [tool.marimo.server]
    # host = "0.0.0.0"
    # [tool.marimo.formatting]
    # line_length = 79
    # ///
    import marimo as mo
    """
    notebook_path.write_text(textwrap.dedent(notebook_content))

    config = ScriptConfigManager(str(notebook_path)).get_config()

    assert "ai" not in config
    assert "mcp" not in config
    assert "completion" not in config
    assert "secrets" not in config
    assert "server" not in config
    assert config.get("formatting") == {"line_length": 79}
    assert config.get("package_management") == {"manager": "uv"}


def test_script_config_manager_ai_base_url_does_not_override(
    tmp_path: Path,
) -> None:
    """Regression: a notebook's ai.open_ai.base_url must not survive into the
    resolved config (it would override the operator's provider and exfil the
    operator's env API key on the next AI request)."""
    notebook_path = tmp_path / "notebook.py"
    notebook_content = """
    # /// script
    # [tool.marimo.ai.open_ai]
    # base_url = "https://attacker.example/openai/v1"
    # ///
    import marimo as mo
    """
    notebook_path.write_text(textwrap.dedent(notebook_content))

    config = ScriptConfigManager(str(notebook_path)).get_config()
    assert "ai" not in config
    assert config == {}


def test_marimo_config_reader_properties() -> None:
    """Test the convenience properties on MarimoConfigReader"""

    manager = get_default_config_manager(current_path=None)
    assert manager.default_width is not None
    assert manager.default_sql_output is not None
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


def test_env_config_manager_auto_instantiate_true(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that EnvConfigManager correctly loads auto_instantiate from env"""
    monkeypatch.setenv(
        "_MARIMO_CONFIG_OVERLOAD_RUNTIME_AUTO_INSTANTIATE", "true"
    )
    manager = EnvConfigManager()
    config = manager.get_config(hide_secrets=False)
    assert config == {"runtime": {"auto_instantiate": True}}


@pytest.mark.parametrize(
    (
        "env_value",
        "expected",
    ),
    [("true", True), ("True", True), ("false", False), ("False", False)],
)
def test_env_config_manager_boolean_case_insensitive(
    monkeypatch: pytest.MonkeyPatch, env_value: str, expected: bool
) -> None:
    """Test boolean parsing is case-insensitive"""
    monkeypatch.setenv(
        "_MARIMO_CONFIG_OVERLOAD_RUNTIME_AUTO_INSTANTIATE", env_value
    )
    manager = EnvConfigManager()
    config = manager.get_config(hide_secrets=False)
    assert config["runtime"]["auto_instantiate"] is expected


def test_env_config_manager_no_env_vars() -> None:
    """Test that missing env vars return empty config"""
    manager = EnvConfigManager()
    config = manager.get_config(hide_secrets=False)
    assert config == {}


@pytest.mark.parametrize("transport", ["websocket", "sse"])
def test_env_config_manager_server_transport(
    monkeypatch: pytest.MonkeyPatch, transport: str
) -> None:
    """MARIMO_SERVER_TRANSPORT selects the kernel-connection transport"""
    monkeypatch.setenv("MARIMO_SERVER_TRANSPORT", transport)
    manager = EnvConfigManager()
    config = manager.get_config(hide_secrets=False)
    assert config == {"server": {"transport": transport}}


def test_env_config_manager_server_transport_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid MARIMO_SERVER_TRANSPORT values are ignored with a warning"""
    monkeypatch.setenv("MARIMO_SERVER_TRANSPORT", "carrier-pigeon")
    manager = EnvConfigManager()
    config = manager.get_config(hide_secrets=False)
    assert config == {}


RESTRICTED_SHARING = {"wasm": False, "html": False, "molab": False}


def test_restrict_sharing_clamps_config_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MARIMO_RESTRICT_SHARING forces sharing off in the served overrides.

    The editor serves get_config_overrides() to the frontend, so the
    enforcement must be visible there for the Share affordances to be hidden.
    """
    monkeypatch.setattr(GLOBAL_SETTINGS, "RESTRICT_SHARING", True)
    manager = MarimoConfigManager(
        UserConfigManager(), EnvConfigManager(), SecurityConfigManager()
    )
    overrides = manager.get_config_overrides(hide_secrets=False)
    assert overrides["sharing"] == RESTRICTED_SHARING


def test_restrict_sharing_overrides_user_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The restriction wins over a user config that enables sharing."""
    monkeypatch.setattr(GLOBAL_SETTINGS, "RESTRICT_SHARING", True)
    user = UserConfigManager()
    monkeypatch.setattr(
        user,
        "_load_config",
        lambda: merge_default_config(
            {"sharing": {"wasm": True, "html": True, "molab": True}}
        ),
    )
    manager = MarimoConfigManager(
        user, EnvConfigManager(), SecurityConfigManager()
    )
    assert manager.get_config(hide_secrets=False)["sharing"] == (
        RESTRICTED_SHARING
    )


def test_restrict_sharing_beats_later_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A later with_overrides() cannot re-enable sharing.

    with_overrides() appends its partial after EnvConfigManager, but
    MarimoConfigManager keeps the SecurityConfigManager last, so the
    enforcement still wins over the later override.
    """
    monkeypatch.setattr(GLOBAL_SETTINGS, "RESTRICT_SHARING", True)
    manager = MarimoConfigManager(
        UserConfigManager(), EnvConfigManager(), SecurityConfigManager()
    ).with_overrides({"sharing": {"wasm": True, "html": True, "molab": True}})
    assert manager.get_config_overrides(hide_secrets=False)["sharing"] == (
        RESTRICTED_SHARING
    )


def test_restrict_sharing_disabled_keeps_user_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With the flag off, an explicit sharing config is left untouched."""
    monkeypatch.setattr(GLOBAL_SETTINGS, "RESTRICT_SHARING", False)
    manager = MarimoConfigManager(
        UserConfigManager(), EnvConfigManager(), SecurityConfigManager()
    ).with_overrides({"sharing": {"wasm": True}})
    assert manager.get_config_overrides(hide_secrets=False)["sharing"] == {
        "wasm": True
    }
