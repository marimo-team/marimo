# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, cast

import pytest
from click.testing import CliRunner
from inline_snapshot import snapshot

from marimo import _loggers
from marimo._cli.config import commands
from marimo._cli.config.commands import config
from marimo._cli.config.utils import (
    format_config_docs,
    format_config_with_sources,
)
from marimo._config.config import PartialMarimoConfig
from marimo._config.config_schema import MCPServerStdioConfig, SaveConfig
from marimo._config.manager import MarimoConfigManager, UserConfigStore
from marimo._config.provenance import ConfigLayer
from marimo._config.resolver import resolve_config_with_sources
from marimo._utils.platform import is_windows

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.xfail(condition=is_windows(), reason="flaky on Windows")
def test_config_show() -> None:
    p = subprocess.run(
        ["marimo", "config", "show"],
        capture_output=True,
    )
    assert p.returncode == 0, p.stderr.decode()
    output = p.stdout.decode()
    assert output.startswith("[ai]")
    assert "sources shown in comments" not in output
    assert "[formatting]" in output


def test_config_describe() -> None:
    p = subprocess.run(
        ["marimo", "config", "describe"],
        capture_output=True,
    )
    assert p.returncode == 0, p.stderr.decode()


def test_config_show_environment_source_names() -> None:
    resolved = resolve_config_with_sources(
        [
            ConfigLayer(
                {
                    "runtime": {"output_max_bytes": 1000},
                    "server": {"transport": "sse"},
                },
                "env_var",
            )
        ]
    )
    assert format_config_with_sources(resolved) == snapshot("""\
[runtime]
output_max_bytes = 1000 # MARIMO_OUTPUT_MAX_BYTES

[server]
transport = "sse" # MARIMO_SERVER_TRANSPORT""")


def test_config_show_source_comments_are_valid_toml(tmp_path: Path) -> None:
    import tomlkit

    values = cast(
        PartialMarimoConfig,
        {
            "display": {"theme": "dark", "custom_css": ["styles.css"]},
            "keymap": {"overrides": {}},
            "file_browser": {"folders": [{"path": "/data", "name": "Data"}]},
        },
    )
    source = tmp_path / "pyproject.toml"
    resolved = resolve_config_with_sources([ConfigLayer(values, source)])
    output = format_config_with_sources(resolved)
    assert output.replace(str(source), "/project/pyproject.toml") == snapshot(
        """\
[display]
custom_css = ["styles.css"] # /project/pyproject.toml
theme = "dark" # /project/pyproject.toml

[[file_browser.folders]] # /project/pyproject.toml
name = "Data"
path = "/data"

[keymap.overrides] # /project/pyproject.toml"""
    )
    assert tomlkit.parse(output).unwrap() == values


@pytest.mark.parametrize("show_sources", [False, True])
def test_config_show_includes_notebook_sources_and_does_not_save(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    show_sources: bool,
) -> None:
    user_path = tmp_path / "marimo.toml"
    contents = (
        '[display]\ntheme = "dark"\n[ai.open_ai]\napi_key = "private-key"\n'
    )
    user_path.write_text(contents)
    notebook = tmp_path / "app.py"
    notebook.write_text(
        '# /// script\n# [tool.marimo.runtime]\n# on_cell_change = "lazy"\n# ///\n'
    )
    user = UserConfigStore()
    monkeypatch.setattr(user, "get_config_path", lambda: str(user_path))
    from marimo._config.manager import ScriptConfigReader

    def manager(*, current_path: str) -> MarimoConfigManager:
        assert current_path == str(notebook)
        return MarimoConfigManager(user, ScriptConfigReader(current_path))

    monkeypatch.setattr(commands, "get_default_config_manager", manager)
    args = ["show", str(notebook)]
    if show_sources:
        args.append("--show-sources")
    result = CliRunner().invoke(commands.config, args)
    assert result.exit_code == 0, result.output
    if show_sources:
        assert f'theme = "dark" # {user_path}' in result.output
        assert f'on_cell_change = "lazy" # {notebook}' in result.output
    else:
        assert 'theme = "dark"\n' in result.output
        assert 'on_cell_change = "lazy"\n' in result.output
        assert "#" not in result.output
    assert 'api_key = "********"' in result.output
    assert "private-key" not in result.output
    assert user_path.read_text() == contents


def test_config_show_relative_notebook_finds_parent_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import tomlkit

    user_path = tmp_path / "marimo.toml"
    user_path.write_text("")
    monkeypatch.setattr(
        UserConfigStore, "get_config_path", lambda _self: str(user_path)
    )
    project = tmp_path / "pyproject.toml"
    project.write_text('[tool.marimo.display]\ntheme = "dark"\n')
    notebooks = tmp_path / "notebooks"
    notebooks.mkdir()
    notebook = notebooks / "app.py"
    notebook.write_text(
        '# /// script\n# [tool.marimo.runtime]\n# on_cell_change = "lazy"\n# ///\n'
    )
    monkeypatch.chdir(notebooks)
    runner = CliRunner()
    relative = runner.invoke(config, ["show", "app.py", "--show-sources"])
    absolute = runner.invoke(config, ["show", str(notebook), "--show-sources"])
    assert relative.exit_code == absolute.exit_code == 0, relative.output
    assert relative.output == absolute.output
    values = tomlkit.parse(relative.output).unwrap()
    assert values["display"]["theme"] == "dark"
    assert values["runtime"]["on_cell_change"] == "lazy"
    assert f'theme = "dark" # {project}' in relative.output
    assert f'on_cell_change = "lazy" # {notebook}' in relative.output


def test_config_show_reports_malformed_project_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_path = tmp_path / "marimo.toml"
    user_path.write_text("")
    project = tmp_path / "pyproject.toml"
    project.write_text("[tool.marimo.display\n")
    user = UserConfigStore()
    monkeypatch.setattr(user, "get_config_path", lambda: str(user_path))
    from marimo._config.manager import PyprojectConfigReader

    monkeypatch.setattr(
        commands,
        "get_default_config_manager",
        lambda **_: MarimoConfigManager(
            user, PyprojectConfigReader(str(tmp_path))
        ),
    )
    with _loggers.capture_output() as (_, _, records):
        result = CliRunner().invoke(commands.config, ["show"])
    assert result.exit_code == 0, result.output
    assert len(records) == 1
    assert str(project) in records[0].getMessage()
    assert "Settings from this file were skipped" in records[0].getMessage()
    assert 'theme = "light"\n' in result.output
    assert "# default" not in result.output


@pytest.mark.parametrize("show_sources", [False, True])
def test_config_show_parse_error_is_readable_and_printed_once(
    tmp_path: Path, show_sources: bool
) -> None:
    config_path = tmp_path / ".marimo.toml"
    config_path.write_text('[display]\ntheme = "light\n')
    args = ["marimo", "config", "show"]
    if show_sources:
        args.append("--show-sources")
    result = subprocess.run(args, cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stderr.count("Error:") == 1
    error_line, explanation, blank_line = result.stderr.splitlines()
    assert blank_line == ""
    assert error_line.startswith(
        f'Error: Could not load configuration from {config_path}: "'
    )
    assert error_line.endswith('"')
    assert "line 2" in error_line
    assert "Settings from this file were skipped" in explanation
    assert "other configuration sources still apply" in result.stderr
    assert "[E " not in result.stderr
    assert result.stdout.startswith("[ai]")


def test_config_describe_field_metadata() -> None:
    assert format_config_docs(SaveConfig) == snapshot(
        """\
Configuration for saving.

autosave
  one of `"off"` or `"after_delay"`
  Type: Literal['off', 'after_delay']
  Default: 'after_delay'

autosave_delay
  Delay in milliseconds before automatically saving.
  Type: int
  Default: 1000

format_on_save
  if `True`, format the code on save
  Type: bool
  Default: False"""
    )


def test_config_describe_nested_and_optional_sections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Describing the schema must not resolve config or environment defaults.
    monkeypatch.setenv("MARIMO_OUTPUT_MAX_BYTES", "invalid")
    monkeypatch.setenv("OPENAI_API_KEY", "secret-api-key")
    result = CliRunner().invoke(config, ["describe"])
    assert result.exit_code == 0, result.output
    output = result.output
    assert "  [ai.models]\n" in output
    assert "  [ai.open_ai]\n" in output
    assert "\n[experimental] (Experimental) " + "─" * 32 + "\n" in output
    assert "\n[cache] " + "─" * 32 + "\n" in output
    assert "\n[venv] " + "─" * 32 + "\n" in output
    assert "Enable live debugging with gutter breakpoints and pdb." in output
    assert "completion.model (Deprecated)\n" in output
    assert "completion.api_key (Deprecated, Sensitive)\n" in output
    assert "completion.codeium_api_key (Sensitive)\n" in output
    assert "completion.activate_on_typing (Sensitive)" not in output
    assert "experimental.debugger (Experimental)\n" in output
    assert "[Deprecated]" not in output
    assert "[Sensitive]" not in output
    assert (
        "Deprecated completion model. Use ai.models.autocomplete_model instead."
        in output
    )
    assert not any(
        line.lstrip().startswith("#") for line in output.splitlines()
    )
    assert "completion.activate_on_typing (Deprecated)" not in output
    assert (
        "display.custom_css\n    list of paths to custom CSS files\n    Type: list[str]"
        in output
    )
    assert (
        "ai.max_tokens\n    the maximum number of tokens to use in AI completions\n    Type: int | None"
        in output
    )
    assert "Default: unset" not in output
    assert "Default: dynamic" in output
    assert "Default: []" in output
    assert "Default: {}" in output
    assert (
        "dict[str, MCPServerStdioConfig | MCPServerStreamableHttpConfig]"
        in output
    )
    assert "UnsetType" not in output
    assert "Annotated" not in output
    assert "ClassVar" not in output
    assert "__marimo_transport__" not in output
    assert "secret-api-key" not in output


def test_config_describe_required_and_nullable_fields() -> None:
    assert format_config_docs(MCPServerStdioConfig) == snapshot(
        """\
Configuration for STDIO transport MCP servers

command
  Command used to launch the MCP server.
  Type: str
  Required

args
  Arguments passed to the MCP server command.
  Type: list[str] | None

env (Sensitive)
  Environment variables supplied to the MCP server.
  Type: dict[str, str] | None

disabled
  Disable this MCP server.
  Type: bool | None"""
    )
