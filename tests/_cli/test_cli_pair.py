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


class TestPairPromptWithToken:
    def test_with_token_writes_file_and_outputs_prompt(self) -> None:
        result = _runner.invoke(
            cli_main,
            ["pair", "prompt", "--url", TEST_URL, "--with-token"],
            input="my-secret-token\n",
        )
        assert result.exit_code == 0
        # Should output the prompt (not just the file path)
        assert TEST_URL in result.output
        assert "execute-code.sh" in result.output
        assert "token" in result.output.lower()
        assert "cat" in result.output

        # Verify the token file was written
        import hashlib

        from marimo._cli.pair.commands import _token_dir

        url_hash = hashlib.sha256(TEST_URL.encode()).hexdigest()[:6]
        token_file = _token_dir() / f"{url_hash}-token.txt"
        assert token_file.exists()
        assert token_file.read_text() == "my-secret-token"
        assert oct(token_file.stat().st_mode & 0o777) == "0o600"
        token_file.unlink()

    def test_with_token_no_url_required(self) -> None:
        # --url is still required by click even with --with-token
        result = _runner.invoke(
            cli_main,
            ["pair", "prompt", "--with-token"],
            input="tok\n",
        )
        assert result.exit_code != 0
