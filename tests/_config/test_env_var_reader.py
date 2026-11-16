# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from marimo import _loggers
from marimo._config.config_schema import MarimoConfig
from marimo._config.manager import EnvVarReader
from marimo._config.provenance import (
    DEPRECATED_ENV_VARS,
    env_var_name,
    format_config_source,
)
from marimo._config.schema_utils import config_leaf_types

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    for key in os.environ:
        if key.startswith("MARIMO_") or key in DEPRECATED_ENV_VARS.values():
            monkeypatch.delenv(key)


@pytest.mark.parametrize(
    ("path", "raw", "expected"),
    [
        (("display", "theme"), "dark", "dark"),
        (("package_management", "manager"), "pixi", "pixi"),
        (("server", "skip_update_check"), "true", True),
        (("server", "session_cookie_secure"), "1", True),
        (("server", "session_secret"), "session-secret", "session-secret"),
        (("runtime", "sql_default_limit"), "300", 300),
        (("runtime", "sql_default_limit"), "null", None),
        (("save", "autosave_delay"), "2000", 2000),
        (("completion", "activate_on_typing"), "False", False),
        (("experimental", "debugger"), "true", True),
        (("language_servers", "ty", "enabled"), "true", True),
        (("completion", "copilot"), "github", "github"),
        (("completion", "copilot"), "false", False),
        (("datasources", "auto_discover_tables"), "auto", "auto"),
        (("ai", "max_tokens"), "null", None),
        (("ai", "open_ai", "api_key"), "", ""),
        (("ai", "open_ai", "api_key"), "true", "true"),
        (("runtime", "pythonpath"), '["src", "lib"]', ["src", "lib"]),
        (("runtime", "pythonpath"), "[]", []),
        (
            ("keymap", "overrides"),
            '{"run-cell":"Shift-Enter"}',
            {"run-cell": "Shift-Enter"},
        ),
        (("keymap", "overrides"), "{}", {}),
        (
            ("file_browser", "folders"),
            '[{"path":"/data"}]',
            [{"path": "/data"}],
        ),
        (("cache", "store"), '{"type":"file"}', {"type": "file"}),
        (
            ("mcp", "mcpServers"),
            '{"local":{"command":"python","args":["server.py"]}}',
            {"local": {"command": "python", "args": ["server.py"]}},
        ),
    ],
)
def test_parse_leaf(
    monkeypatch: pytest.MonkeyPatch,
    path: tuple[str, ...],
    raw: str,
    expected: Any,
) -> None:
    monkeypatch.setenv(env_var_name(path), raw)
    config: Any = EnvVarReader().read()
    for component in path:
        assert len(config) == 1
        config = config[component]
    assert config == expected


@pytest.mark.parametrize(
    ("variable", "raw"),
    [
        ("MARIMO_SAVE_AUTOSAVE_DELAY", "secret-invalid-number"),
        ("MARIMO_SAVE_AUTOSAVE_DELAY", "true"),
        ("MARIMO_DISPLAY_THEME", "secret-invalid-theme"),
        ("MARIMO_EXPERIMENTAL_DEBUGGER", "maybe"),
        ("MARIMO_RUNTIME_PYTHONPATH", "[broken-json]"),
        ("MARIMO_RUNTIME_PYTHONPATH", '[1, "src"]'),
        ("MARIMO_KEYMAP_OVERRIDES", '{"run-cell": 123}'),
        ("MARIMO_RUNTIME_PYTHONPATH", "null"),
    ],
)
def test_malformed_value_is_skipped_independently(
    monkeypatch: pytest.MonkeyPatch, variable: str, raw: str
) -> None:
    monkeypatch.setenv(variable, raw)
    monkeypatch.setenv("MARIMO_SERVER_TRANSPORT", "sse")
    with _loggers.capture_output() as (_, _, records):
        assert EnvVarReader().read() == {"server": {"transport": "sse"}}
    assert len(records) == 1
    message = records[0].getMessage()
    assert variable in message
    assert "skipped" in message
    assert raw not in message


def test_only_declared_leaves_are_addressable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MARIMO_DISPLAY", '{"theme":"dark"}')
    monkeypatch.setenv("MARIMO_KEYMAP_OVERRIDES_RUN_CELL", "Shift-Enter")
    monkeypatch.setenv("MARIMO_UNKNOWN_OPTION", "true")
    monkeypatch.setenv("MARIMO_CONFIG_SERVER_TRANSPORT", "sse")
    assert EnvVarReader().read() == {}


def test_environment_names_are_unique() -> None:
    paths = config_leaf_types(MarimoConfig)
    names = [env_var_name(path) for path in paths]
    assert len(names) == len(set(names))


def test_dictionary_entry_source_names_whole_variable() -> None:
    assert (
        format_config_source(("keymap", "overrides", "run-cell"), "env_var")
        == "env var: MARIMO_KEYMAP_OVERRIDES"
    )
    assert (
        format_config_source(
            ("mcp", "mcpServers", "local", "command"), "env_var"
        )
        == "env var: MARIMO_MCP_MCPSERVERS"
    )
    assert (
        format_config_source(("sharing", "html"), "MARIMO_RESTRICT_SHARING")
        == "env var: MARIMO_RESTRICT_SHARING"
    )


def test_security_enforcement_overrides_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from marimo._config.manager import SecurityConfigReader
    from marimo._config.resolver import resolve_config_with_sources
    from marimo._config.settings import GLOBAL_SETTINGS

    monkeypatch.setenv("MARIMO_SHARING_HTML", "true")
    monkeypatch.setattr(GLOBAL_SETTINGS, "RESTRICT_SHARING", True)
    resolved = resolve_config_with_sources(
        [EnvVarReader().read_layer(), SecurityConfigReader().read_layer()]
    )
    assert resolved.config["sharing"]["html"] is False
    assert (
        format_config_source(
            ("sharing", "html"), resolved.origins[("sharing", "html")]
        )
        == "env var: MARIMO_RESTRICT_SHARING"
    )


def test_migrated_settings_from_user_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from marimo._config.manager import MarimoConfigManager, UserConfigStore
    from marimo._server.main import create_starlette_app

    path = tmp_path / "marimo.toml"
    path.write_text(
        '[runtime]\nsql_default_limit = 200\n[server]\nskip_update_check = true\nsession_cookie_secure = true\nsession_secret = "private-secret"\n'
    )
    user = UserConfigStore()
    monkeypatch.setattr(user, "get_config_path", lambda: str(path))
    monkeypatch.setattr(
        "marimo._config.manager.is_trusted_user_config_path", lambda _: True
    )
    manager = MarimoConfigManager(user)
    config = manager.get_config(hide_secrets=False).to_dict()
    assert config["runtime"]["sql_default_limit"] == 200
    assert config["server"] == {
        "disable_file_downloads": False,
        "browser": "default",
        "follow_symlink": False,
        "skip_update_check": True,
        "session_cookie_secure": True,
        "session_secret": "private-secret",
    }
    assert manager.get_config().server.session_secret == "********"
    assert (
        create_starlette_app(
            base_url="",
            server_config=manager.get_config(hide_secrets=False).server,
        ).state.session_secret
        == "private-secret"
    )


def test_session_secret_from_project_is_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from marimo._config.manager import (
        MarimoConfigManager,
        PyprojectConfigReader,
        UserConfigStore,
    )

    user_path = tmp_path / "marimo.toml"
    user_path.write_text('[server]\nsession_secret = "user-secret"\n')
    user = UserConfigStore()
    monkeypatch.setattr(user, "get_config_path", lambda: str(user_path))
    monkeypatch.setattr(
        "marimo._config.manager.is_trusted_user_config_path", lambda _: True
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.marimo.server]\nsession_secret = "project-secret"\n'
    )
    manager = MarimoConfigManager(user, PyprojectConfigReader(str(tmp_path)))
    assert (
        manager.get_config(hide_secrets=False).to_dict()["server"][
            "session_secret"
        ]
        == "user-secret"
    )


@pytest.mark.parametrize(
    ("path", "raw", "expected"),
    [
        (("runtime", "auto_instantiate"), "true", True),
        (("runtime", "output_max_bytes"), "120_000", 120000),
        (("runtime", "std_stream_max_bytes"), "45000", 45000),
        (("runtime", "sql_default_limit"), "300", 300),
        (("server", "skip_update_check"), "1", True),
        (("server", "session_cookie_secure"), "true", True),
        (
            ("server", "session_secret"),
            "private-session-secret",
            "private-session-secret",
        ),
    ],
)
def test_deprecated_environment_names(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    path: tuple[str, ...],
    raw: str,
    expected: Any,
) -> None:
    import logging

    from marimo._config.manager import MarimoConfigManager, UserConfigStore

    variable = DEPRECATED_ENV_VARS[path]
    monkeypatch.setenv(variable, raw)
    path_to_config = tmp_path / ".marimo.toml"
    path_to_config.write_text("")
    user = UserConfigStore()
    monkeypatch.setattr(user, "get_config_path", lambda: str(path_to_config))
    with _loggers.capture_output(log_level=logging.WARNING) as (_, _, records):
        resolved = MarimoConfigManager(
            user, EnvVarReader(deprecated=True), EnvVarReader()
        ).get_config_with_sources(hide_secrets=False)
    value: Any = resolved.config
    for component in path:
        value = value[component]
    assert value == expected
    assert [record.getMessage() for record in records] == [
        f"Environment variable {variable} is deprecated and will be removed in marimo 1.0. Use {env_var_name(path)} instead."
    ]
    assert (
        format_config_source(path, resolved.origins[path])
        == f"env var: {variable} (deprecated)"
    )


@pytest.mark.parametrize("new_value", ["456", "invalid", ""])
def test_new_name_takes_precedence_over_deprecated_name(
    monkeypatch: pytest.MonkeyPatch,
    new_value: str,
) -> None:
    from marimo._config.resolver import resolve_config_with_sources

    path = ("runtime", "output_max_bytes")
    monkeypatch.setenv(DEPRECATED_ENV_VARS[path], "123")
    monkeypatch.setenv(env_var_name(path), new_value)
    with _loggers.capture_output() as (_, _, records):
        resolved = resolve_config_with_sources(
            [
                EnvVarReader(deprecated=True).read_layer(),
                EnvVarReader().read_layer(),
            ]
        )
    if new_value == "456":
        assert resolved.config == {"runtime": {"output_max_bytes": 456}}
        assert (
            format_config_source(path, resolved.origins[path])
            == f"env var: {env_var_name(path)}"
        )
    else:
        assert resolved.config == {}
    assert "will be removed in marimo 1.0" in records[0].getMessage()


def test_invalid_deprecated_value_is_skipped_without_disclosing_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MARIMO_OUTPUT_MAX_BYTES", "private-invalid-value")
    with _loggers.capture_output() as (_, _, records):
        assert EnvVarReader(deprecated=True).read() == {}
    assert len(records) == 2
    assert "marimo 1.0" in records[0].getMessage()
    assert "MARIMO_OUTPUT_MAX_BYTES" in records[1].getMessage()
    assert all(
        "private-invalid-value" not in record.getMessage()
        for record in records
    )


@pytest.mark.parametrize("deprecated", [False, True])
def test_negative_sql_environment_limit_is_skipped(
    monkeypatch: pytest.MonkeyPatch,
    deprecated: bool,
) -> None:
    variable = (
        "MARIMO_SQL_DEFAULT_LIMIT"
        if deprecated
        else "MARIMO_RUNTIME_SQL_DEFAULT_LIMIT"
    )
    monkeypatch.setenv(variable, "-1")
    with _loggers.capture_output() as (_, _, records):
        assert EnvVarReader(deprecated=deprecated).read() == {}
    assert "skipped" in records[-1].getMessage()
