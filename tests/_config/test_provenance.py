# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

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
from marimo._config.provenance import ConfigLayer, ConfigSource
from marimo._config.resolver import resolve_config_with_sources
from marimo._config.settings import GLOBAL_SETTINGS

if TYPE_CHECKING:
    from pathlib import Path


def test_leaf_sources_follow_merge_rules() -> None:
    default = ConfigSource("default")
    project = ConfigSource("project", "/project/pyproject.toml")
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
        ("display", "theme"): ConfigSource("project", str(project_path)),
        ("save", "autosave_delay"): ConfigSource("default"),
        ("runtime", "on_cell_change"): ConfigSource("script", str(notebook)),
        ("runtime", "dotenv"): ConfigSource("inferred", str(notebook)),
        ("server", "transport"): ConfigSource(
            "environment", "MARIMO_SERVER_TRANSPORT"
        ),
        ("sharing", "html"): ConfigSource(
            "security", "MARIMO_RESTRICT_SHARING"
        ),
        ("ai", "open_ai", "api_key"): ConfigSource(
            "user", str(tmp_path / "marimo.toml")
        ),
    }
    assert resolved.config == merge_default_config(
        {
            "display": {"theme": "light", "custom_css": []},
            "runtime": {"on_cell_change": "lazy", "dotenv": []},
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
def test_parse_warnings_identify_the_file(
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
    with _loggers.capture_output() as (_, _, records):
        resolved = MarimoConfigManager(
            user, *readers
        ).get_config_with_sources()
    messages = [record.getMessage() for record in records]
    assert len(messages) == 1
    assert str(path) in messages[0]
    assert "settings were ignored" in messages[0]
    assert (
        resolved.config["display"]["theme"]
        == DEFAULT_CONFIG["display"]["theme"]
    )
    assert resolved.origins[("display", "theme")] == ConfigSource("default")


def test_validation_warning_identifies_source_and_field(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user(
        tmp_path, monkeypatch, '[save]\nautosave_delay = "fast"\n'
    )
    with _loggers.capture_output() as (_, _, records):
        resolved = MarimoConfigManager(user).get_config_with_sources()
    assert [record.getMessage() for record in records] == [
        f"Invalid configuration from user: {tmp_path / 'marimo.toml'}: Expected `int`, got `str` - at `$.save.autosave_delay`"
    ]
    assert resolved.origins[("save", "autosave_delay")] == user.source


def test_legacy_reload_values_keep_their_origin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user(tmp_path, monkeypatch, "[runtime]\nauto_reload = true\n")
    with _loggers.capture_output() as (_, _, records):
        resolved = MarimoConfigManager(user).get_config_with_sources()
    assert records == []
    assert resolved.config["runtime"]["auto_reload"] == "lazy"
    assert resolved.origins[("runtime", "auto_reload")] == user.source
