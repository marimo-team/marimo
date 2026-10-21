# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import subprocess

import pytest
from click.testing import CliRunner
from inline_snapshot import snapshot

from marimo._cli.config.commands import config
from marimo._cli.config.utils import format_config_docs
from marimo._config.config_schema import MCPServerStdioConfig, SaveConfig
from marimo._utils.platform import is_windows


@pytest.mark.xfail(condition=is_windows(), reason="flaky on Windows")
def test_config_show() -> None:
    p = subprocess.run(
        ["marimo", "config", "show"],
        capture_output=True,
    )
    assert p.returncode == 0, p.stderr.decode()
    output = p.stdout.decode()
    assert "User config from" in output
    assert "[formatting]" in output


def test_config_describe() -> None:
    p = subprocess.run(
        ["marimo", "config", "describe"],
        capture_output=True,
    )
    assert p.returncode == 0, p.stderr.decode()


def test_config_describe_field_metadata() -> None:
    assert format_config_docs(SaveConfig) == snapshot(
        """\
# Configuration for saving.

autosave: Literal['off', 'after_delay']
# one of `"off"` or `"after_delay"`
# Default: 'after_delay'

autosave_delay: int
# Delay in milliseconds before automatically saving.
# Default: 1000

format_on_save: bool
# if `True`, format the code on save
# Default: False"""
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
    assert "[ai.models]" in output
    assert "[ai.open_ai]" in output
    assert "[experimental]" in output
    assert "[cache]" in output
    assert "[venv]" in output
    assert "# Enable live debugging with gutter breakpoints and pdb." in output
    assert "[Deprecated] model: str | None" in output
    assert "[Deprecated] [Sensitive] api_key: str | None" in output
    assert "[Sensitive] codeium_api_key: str | None" in output
    assert "[Sensitive] activate_on_typing" not in output
    assert (
        "# Deprecated completion model. Use ai.models.autocomplete_model instead."
        in output
    )
    assert "# Deprecated" not in {line.strip() for line in output.splitlines()}
    assert "[Deprecated] activate_on_typing" not in output
    assert "custom_css: list[str]" in output
    assert "max_tokens: int | None" in output
    assert "# Default: unset" not in output
    assert "# Default: dynamic" in output
    assert "# Default: []" in output
    assert "# Default: {}" in output
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
# Configuration for STDIO transport MCP servers

command: str
# Command used to launch the MCP server.
# Required

args: list[str] | None
# Arguments passed to the MCP server command.

[Sensitive] env: dict[str, str] | None
# Environment variables supplied to the MCP server.

disabled: bool | None
# Disable this MCP server."""
    )
