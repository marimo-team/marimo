# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from marimo._cli.cli import main as cli_main
from marimo._cli.pair.commands import AgentConfig

_runner = CliRunner()

TEST_URL = "https://localhost:8000?auth=tok123"


class TestPairGroup:
    def test_pair_help(self) -> None:
        result = _runner.invoke(cli_main, ["pair", "--help"])
        assert result.exit_code == 0
        assert "pair programming" in result.output.lower()
        assert "prompt" in result.output

    def test_prompt_help(self) -> None:
        result = _runner.invoke(cli_main, ["pair", "prompt", "--help"])
        assert result.exit_code == 0
        assert "--url" in result.output
        assert "--claude" in result.output
        assert "--codex" in result.output
        assert "--opencode" in result.output


class TestPairPrompt:
    def test_prompt_requires_url(self) -> None:
        result = _runner.invoke(cli_main, ["pair", "prompt"])
        assert result.exit_code != 0

    def test_prompt_outputs_url(self) -> None:
        result = _runner.invoke(
            cli_main, ["pair", "prompt", "--url", TEST_URL]
        )
        assert result.exit_code == 0
        assert TEST_URL in result.output
        assert "execute-code.sh" in result.output
        assert "marimo-pair" in result.output

    def test_prompt_skill_missing(self) -> None:
        with patch.object(AgentConfig, "has_skill", return_value=False):
            for flag in ("--claude", "--codex", "--opencode"):
                result = _runner.invoke(
                    cli_main,
                    ["pair", "prompt", "--url", TEST_URL, flag],
                )
                assert result.exit_code != 0, flag
                assert "not installed" in result.output, flag

    def test_prompt_skill_installed(self) -> None:
        with patch.object(AgentConfig, "has_skill", return_value=True):
            for flag in ("--claude", "--codex", "--opencode"):
                result = _runner.invoke(
                    cli_main,
                    ["pair", "prompt", "--url", TEST_URL, flag],
                )
                assert result.exit_code == 0, flag
                assert TEST_URL in result.output, flag
