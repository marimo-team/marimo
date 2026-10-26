# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

import pytest

from marimo import _loggers
from marimo._config.config_schema import MarimoConfig
from marimo._config.manager import EnvVarReader
from marimo._config.provenance import env_var_name, format_config_source
from marimo._config.schema_utils import config_leaf_types


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    for key in os.environ:
        if key.startswith("MARIMO_"):
            monkeypatch.delenv(key)


@pytest.mark.parametrize(
    ("path", "raw", "expected"),
    [
        (("display", "theme"), "dark", "dark"),
        (("package_management", "manager"), "pixi", "pixi"),
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
