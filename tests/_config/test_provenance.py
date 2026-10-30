# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from marimo import _loggers
from marimo._config.config import (
    DEFAULT_CONFIG,
    PartialMarimoConfig,
    merge_default_config,
)
from marimo._config.manager import (
    EnvConfigReader,
    MarimoConfigManager,
    OverrideConfigReader,
    PyprojectConfigReader,
    ScriptConfigReader,
    SecurityConfigReader,
    UserConfigStore,
)
from marimo._config.provenance import (
    ConfigLayer,
    ConfigSource,
    format_config_source,
)
from marimo._config.resolver import resolve_config_with_sources
from marimo._config.settings import GLOBAL_SETTINGS


def test_leaf_sources_follow_merge_rules() -> None:
    default: ConfigSource = "default"
    project = Path("/project/pyproject.toml")
    resolved = resolve_config_with_sources(
        [
            ConfigLayer(
                cast(
                    PartialMarimoConfig,
                    {
                        "display": {
                            "theme": "light",
                            "custom_css": ["old.css"],
                        },
                        "keymap": {"overrides": {"run": "Ctrl-Enter"}},
                        "ai": {
                            "custom_providers": {
                                "removed": {"api_key": "old"},
                                "gateway.example": {
                                    "api_key": "kept",
                                    "base_url": "old",
                                },
                            }
                        },
                        "future": {"value": 1},
                    },
                ),
                default,
            ),
            ConfigLayer(
                cast(
                    PartialMarimoConfig,
                    {
                        "display": {"theme": "light", "custom_css": []},
                        "keymap": {"overrides": {}},
                        "ai": {
                            "custom_providers": {
                                "gateway.example": {"base_url": "new"}
                            }
                        },
                        "future": None,
                    },
                ),
                project,
            ),
        ]
    )
    assert resolved.config == {
        "display": {"theme": "light", "custom_css": []},
        "keymap": {"overrides": {}},
        "ai": {
            "custom_providers": {
                "gateway.example": {"api_key": "kept", "base_url": "new"}
            }
        },
        "future": None,
    }
    assert resolved.origins == {
        ("display", "theme"): project,
        ("display", "custom_css"): project,
        ("keymap", "overrides"): project,
        ("ai", "custom_providers", "gateway.example", "api_key"): default,
        ("ai", "custom_providers", "gateway.example", "base_url"): project,
        ("future",): project,
    }


def make_user(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, contents: str = ""
) -> UserConfigStore:
    path = tmp_path / "marimo.toml"
    path.write_text(contents)
    user = UserConfigStore()
    monkeypatch.setattr(user, "get_config_path", lambda: str(path))
    return user


def test_environment_output_limits_override_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user(
        tmp_path,
        monkeypatch,
        "[runtime]\noutput_max_bytes = 777\nstd_stream_max_bytes = 888\n",
    )
    (tmp_path / "pyproject.toml").write_text(
        "[tool.marimo.runtime]\noutput_max_bytes = 999\nstd_stream_max_bytes = 1000\n"
    )
    notebook = tmp_path / "app.py"
    notebook.write_text(
        "# /// script\n# [tool.marimo.runtime]\n# output_max_bytes = 1111\n"
        "# std_stream_max_bytes = 2222\n# ///\n"
    )
    monkeypatch.setenv("MARIMO_OUTPUT_MAX_BYTES", "1234")
    monkeypatch.setenv("MARIMO_STD_STREAM_MAX_BYTES", "5678")
    resolved = MarimoConfigManager(
        user,
        PyprojectConfigReader(str(notebook)),
        ScriptConfigReader(str(notebook)),
        EnvConfigReader(),
    ).get_config_with_sources()
    assert resolved.config["runtime"]["output_max_bytes"] == 1234
    assert resolved.config["runtime"]["std_stream_max_bytes"] == 5678
    assert resolved.origins[("runtime", "output_max_bytes")] == "env_var"
    assert resolved.origins[("runtime", "std_stream_max_bytes")] == "env_var"
    assert resolved.origins[("package_management", "manager")] == "inferred"


@pytest.mark.parametrize(
    ("field", "variable"),
    [
        ("output_max_bytes", "MARIMO_OUTPUT_MAX_BYTES"),
        ("std_stream_max_bytes", "MARIMO_STD_STREAM_MAX_BYTES"),
    ],
)
def test_invalid_environment_output_limit_keeps_file_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    variable: str,
) -> None:
    user = make_user(tmp_path, monkeypatch, f"[runtime]\n{field} = 777\n")
    monkeypatch.setenv(variable, "invalid")
    with _loggers.capture_output(log_level=logging.WARNING) as (_, _, records):
        resolved = MarimoConfigManager(
            user, EnvConfigReader()
        ).get_config_with_sources()
    assert resolved.config["runtime"][field] == 777
    assert resolved.origins[("runtime", field)] == user.source
    assert len(records) == 1
    assert (
        records[0]
        .getMessage()
        .startswith(f"Ignoring invalid value 'invalid' for {variable}:")
    )


def test_environment_validation_error_uses_variable_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user(tmp_path, monkeypatch)
    monkeypatch.setenv(
        "_MARIMO_CONFIG_OVERLOAD_RUNTIME_AUTO_INSTANTIATE", "invalid"
    )
    with _loggers.capture_output(log_level=logging.WARNING) as (_, _, records):
        MarimoConfigManager(user, EnvConfigReader()).get_config()
    assert [record.getMessage() for record in records] == [
        "Invalid configuration from _MARIMO_CONFIG_OVERLOAD_RUNTIME_AUTO_INSTANTIATE: Expected `bool`, got `str` - at `$.runtime.auto_instantiate`"
    ]


def test_environment_sources_use_variable_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "_MARIMO_CONFIG_OVERLOAD_RUNTIME_AUTO_INSTANTIATE", "true"
    )
    monkeypatch.setenv("MARIMO_RUNTIME_ON_CELL_CHANGE", "lazy")
    monkeypatch.setenv("MARIMO_SERVER_TRANSPORT", "sse")
    layer = EnvConfigReader().read_layer()
    assert layer == ConfigLayer(
        {
            "runtime": {"auto_instantiate": True, "on_cell_change": "lazy"},
            "server": {"transport": "sse"},
        },
        "env_var",
    )
    resolved = resolve_config_with_sources([layer])
    assert {
        path: format_config_source(path, source)
        for path, source in resolved.origins.items()
    } == {
        (
            "runtime",
            "auto_instantiate",
        ): "_MARIMO_CONFIG_OVERLOAD_RUNTIME_AUTO_INSTANTIATE",
        ("runtime", "on_cell_change"): "MARIMO_RUNTIME_ON_CELL_CHANGE",
        ("server", "transport"): "MARIMO_SERVER_TRANSPORT",
    }


@pytest.mark.parametrize("clear_css", [False, True])
def test_project_display_preserves_user_css_unless_explicitly_cleared(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    clear_css: bool,
) -> None:
    user = make_user(
        tmp_path, monkeypatch, '[display]\ncustom_css = ["user.css"]\n'
    )
    project = tmp_path / "pyproject.toml"
    project.write_text(
        '[tool.marimo.display]\ntheme = "dark"\n'
        + ("custom_css = []\n" if clear_css else "")
    )
    reader = PyprojectConfigReader(str(tmp_path))
    resolved = MarimoConfigManager(user, reader).get_config_with_sources()
    assert resolved.config["display"]["custom_css"] == (
        [] if clear_css else ["user.css"]
    )
    assert resolved.origins[("display", "custom_css")] == (
        project if clear_css else user.source
    )


@pytest.mark.parametrize("source", ["user", "project", "script", "override"])
def test_empty_dotenv_disables_inferred_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
) -> None:
    user = make_user(
        tmp_path,
        monkeypatch,
        "[runtime]\ndotenv = []\n" if source == "user" else "",
    )
    (tmp_path / "pyproject.toml").write_text(
        "[tool.marimo.runtime]\ndotenv = []\n" if source == "project" else ""
    )
    notebook = tmp_path / "app.py"
    notebook.write_text(
        "# /// script\n# [tool.marimo.runtime]\n# dotenv = []\n# ///\n"
        if source == "script"
        else ""
    )
    manager = MarimoConfigManager(
        user,
        PyprojectConfigReader(str(notebook)),
        ScriptConfigReader(str(notebook)),
        OverrideConfigReader(
            {"runtime": {"dotenv": []}} if source == "override" else {}
        ),
    )
    resolved = manager.get_config_with_sources(hide_secrets=False)
    assert resolved.config["runtime"]["dotenv"] == []
    sources = {
        "user": user.source,
        "project": tmp_path / "pyproject.toml",
        "script": notebook,
        "override": "override",
    }
    assert resolved.origins[("runtime", "dotenv")] == sources[source]


def test_empty_dotenv_overrides_inherited_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user(
        tmp_path, monkeypatch, '[runtime]\ndotenv = ["custom.env"]\n'
    )
    (tmp_path / "pyproject.toml").write_text(
        "[tool.marimo.runtime]\ndotenv = []\n"
    )
    notebook = tmp_path / "app.py"
    notebook.write_text(
        "# /// script\n# [tool.marimo.runtime]\n# dotenv = []\n# ///\n"
    )
    override = OverrideConfigReader({"runtime": {"dotenv": []}})
    manager = MarimoConfigManager(
        user,
        PyprojectConfigReader(str(notebook)),
        ScriptConfigReader(str(notebook)),
        override,
    )
    resolved = manager.get_config_with_sources(hide_secrets=False)
    assert resolved.config["runtime"]["dotenv"] == []
    assert resolved.origins[("runtime", "dotenv")] == "override"
    assert (
        manager.get_config_overrides(hide_secrets=False)["runtime"]["dotenv"]
        == []
    )
    assert override.read() == {"runtime": {"dotenv": []}}


def test_manager_tracks_file_environment_default_and_security_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user(
        tmp_path,
        monkeypatch,
        '[display]\ntheme = "dark"\n[ai.open_ai]\napi_key = "private-key"\n',
    )
    project_path = tmp_path / "pyproject.toml"
    project_path.write_text('[tool.marimo.display]\ntheme = "light"\n')
    notebook = tmp_path / "app.py"
    notebook.write_text(
        '# /// script\n# [tool.marimo.runtime]\n# on_cell_change = "lazy"\n# ///\n'
    )
    monkeypatch.setenv("MARIMO_SERVER_TRANSPORT", "sse")
    monkeypatch.setattr(GLOBAL_SETTINGS, "RESTRICT_SHARING", True)
    manager = MarimoConfigManager(
        user,
        PyprojectConfigReader(str(tmp_path)),
        ScriptConfigReader(str(notebook)),
        EnvConfigReader(),
        SecurityConfigReader(),
    )
    resolved = manager.get_config_with_sources()
    paths = [
        ("display", "theme"),
        ("save", "autosave_delay"),
        ("runtime", "on_cell_change"),
        ("runtime", "dotenv"),
        ("server", "transport"),
        ("sharing", "html"),
        ("ai", "open_ai", "api_key"),
    ]
    assert {path: resolved.origins[path] for path in paths} == {
        ("display", "theme"): project_path,
        ("save", "autosave_delay"): "default",
        ("runtime", "on_cell_change"): notebook,
        ("runtime", "dotenv"): "inferred",
        ("server", "transport"): "env_var",
        ("sharing", "html"): "env_var",
        ("ai", "open_ai", "api_key"): tmp_path / "marimo.toml",
    }
    assert resolved.config == merge_default_config(
        {
            "display": {"theme": "light"},
            "runtime": {"on_cell_change": "lazy"},
            "server": {"transport": "sse"},
            "sharing": {"html": False, "wasm": False, "molab": False},
            "ai": {"open_ai": {"api_key": "********"}},
        }
    )
    assert (
        manager.get_config(hide_secrets=False)["ai"]["open_ai"]["api_key"]
        == "private-key"
    )


def test_manager_preserves_record_merge_grouping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user(
        tmp_path,
        monkeypatch,
        '[ai.custom_providers.gateway]\napi_key = "user-key"\n',
    )
    first = OverrideConfigReader(
        {"ai": {"custom_providers": {"other": {"base_url": "https://other"}}}}
    )
    last = OverrideConfigReader(
        {
            "ai": {
                "custom_providers": {
                    "gateway": {"base_url": "https://gateway"}
                }
            }
        }
    )
    resolved = MarimoConfigManager(user, first, last).get_config_with_sources(
        hide_secrets=False
    )
    assert resolved.config["ai"]["custom_providers"] == {
        "gateway": {"api_key": "user-key", "base_url": "https://gateway"}
    }
    assert (
        resolved.origins[("ai", "custom_providers", "gateway", "api_key")]
        == user.source
    )
    assert (
        resolved.origins[("ai", "custom_providers", "gateway", "base_url")]
        == last.source
    )
    assert not any("other" in path for path in resolved.origins)


@pytest.mark.parametrize("kind", ["user", "project", "script"])
def test_parse_errors_identify_the_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    user = make_user(tmp_path, monkeypatch)
    readers: list[Any] = []
    if kind == "user":
        path = tmp_path / "marimo.toml"
        contents = "[display\n"
    elif kind == "project":
        path = tmp_path / "pyproject.toml"
        contents = "[tool.marimo.display\n"
        path.write_text(contents)
        readers.append(PyprojectConfigReader(str(tmp_path)))
    else:
        path = tmp_path / "app.py"
        contents = "# /// script\n# [tool.marimo.display\n# ///\n"
        readers.append(ScriptConfigReader(str(path)))
    path.write_text(contents)
    with _loggers.capture_output(log_level=logging.WARNING) as (_, _, records):
        resolved = MarimoConfigManager(
            user, *readers
        ).get_config_with_sources()
    messages = [record.getMessage() for record in records]
    assert len(messages) == 1
    assert str(path) in messages[0]
    assert (
        "Expected ']'"
        if sys.version_info >= (3, 11)
        else "Unexpected character: '\\n'"
    ) in messages[0]
    assert "Settings from this file were skipped" in messages[0]
    assert (
        resolved.config["display"]["theme"]
        == DEFAULT_CONFIG["display"]["theme"]
    )
    assert resolved.origins[("display", "theme")] == "default"


def test_validation_error_identifies_source_and_field(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user(
        tmp_path, monkeypatch, '[save]\nautosave_delay = "fast"\n'
    )
    project = tmp_path / "pyproject.toml"
    project.write_text('[tool.marimo.display]\ntheme = "dark"\n')
    with _loggers.capture_output(log_level=logging.WARNING) as (_, _, records):
        resolved = MarimoConfigManager(
            user, PyprojectConfigReader(str(tmp_path))
        ).get_config_with_sources()
    assert [record.getMessage() for record in records] == [
        f"Invalid configuration from {tmp_path / 'marimo.toml'}: Expected `int`, got `str` - at `$.save.autosave_delay`"
    ]
    assert resolved.origins[("save", "autosave_delay")] == user.source


@pytest.mark.parametrize(
    ("overlay", "expected"),
    [
        ('args = ["--verbose"]', {"args": ["--verbose"]}),
        ("disabled = true", {"disabled": True}),
    ],
)
def test_sparse_mcp_overlay_inherits_transport_without_validation_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    overlay: str,
    expected: dict[str, Any],
) -> None:
    user = make_user(
        tmp_path, monkeypatch, '[mcp.mcpServers.example]\ncommand = "uvx"\n'
    )
    project = tmp_path / "pyproject.toml"
    project.write_text(f"[tool.marimo.mcp.mcpServers.example]\n{overlay}\n")
    reader = PyprojectConfigReader(str(tmp_path))
    manager = MarimoConfigManager(user, reader)
    with _loggers.capture_output(log_level=logging.WARNING) as (_, _, records):
        overrides = manager.get_config_overrides()
        resolved = manager.get_config_with_sources()
        assert manager.get_config() == resolved.config
    assert records == []
    assert overrides["mcp"]["mcpServers"] == {"example": expected}
    assert resolved.config["mcp"]["mcpServers"] == {
        "example": {"command": "uvx", **expected}
    }
    assert {
        path: source
        for path, source in resolved.origins.items()
        if path[:3] == ("mcp", "mcpServers", "example")
    } == {
        ("mcp", "mcpServers", "example", "command"): user.source,
        (
            "mcp",
            "mcpServers",
            "example",
            overlay.split(" = ", maxsplit=1)[0],
        ): reader.source,
    }


@pytest.mark.parametrize(
    ("overlay", "error"),
    [
        (
            "args = 123",
            "Expected `array | null`, got `int` - at `$.mcp.mcpServers[...].args`",
        ),
        (
            "args = [123]",
            "Expected `str`, got `int` - at `$.mcp.mcpServers[...].args[0]`",
        ),
        (
            'disabled = "no"',
            "Expected `bool | null`, got `str` - at `$.mcp.mcpServers[...].disabled`",
        ),
    ],
)
def test_invalid_mcp_overlay_reports_project_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    overlay: str,
    error: str,
) -> None:
    user = make_user(
        tmp_path, monkeypatch, '[mcp.mcpServers.example]\ncommand = "uvx"\n'
    )
    project = tmp_path / "pyproject.toml"
    project.write_text(f"[tool.marimo.mcp.mcpServers.example]\n{overlay}\n")
    with _loggers.capture_output(log_level=logging.WARNING) as (_, _, records):
        MarimoConfigManager(
            user, PyprojectConfigReader(str(tmp_path))
        ).get_config_with_sources()
    assert [record.getMessage() for record in records] == [
        f"Invalid configuration from {project}: {error}"
    ]


def test_overridden_invalid_value_does_not_report_validation_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user(
        tmp_path, monkeypatch, '[save]\nautosave_delay = "fast"\n'
    )
    with _loggers.capture_output(log_level=logging.WARNING) as (_, _, records):
        resolved = MarimoConfigManager(
            user, OverrideConfigReader({"save": {"autosave_delay": 1000}})
        ).get_config_with_sources()
    assert records == []
    assert resolved.config["save"]["autosave_delay"] == 1000


def test_legacy_reload_values_keep_their_origin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user(tmp_path, monkeypatch, "[runtime]\nauto_reload = true\n")
    with _loggers.capture_output(log_level=logging.WARNING) as (_, _, records):
        resolved = MarimoConfigManager(user).get_config_with_sources()
    assert records == []
    assert resolved.config["runtime"]["auto_reload"] == "lazy"
    assert resolved.origins[("runtime", "auto_reload")] == user.source
