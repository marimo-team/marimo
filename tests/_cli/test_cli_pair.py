# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from marimo._cli.cli import main as cli_main
from marimo._cli.pair.commands import (
    AgentConfig,
    _opencode_skill_dirs,
    _plugin_skill_dirs,
    pair_agents,
)

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
        assert "--file" in result.output
        assert "--session" not in result.output


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

    def test_prompt_with_file(self) -> None:
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "prompt",
                "--url",
                TEST_URL,
                "--file",
                "notebooks/example.py",
            ],
        )
        assert result.exit_code == 0
        assert TEST_URL in result.output
        assert "notebooks/example.py" in result.output
        assert "--file notebooks/example.py" in result.output

    def test_prompt_without_file_omits_flag(self) -> None:
        result = _runner.invoke(
            cli_main, ["pair", "prompt", "--url", TEST_URL]
        )
        assert result.exit_code == 0
        assert "--file" not in result.output
        assert "--session" not in result.output

    def test_prompt_rejects_removed_session_option(self) -> None:
        result = _runner.invoke(
            cli_main,
            ["pair", "prompt", "--url", TEST_URL, "--session", "s_ab12cd"],
        )
        assert result.exit_code != 0
        assert "--session" in result.output

    def test_prompt_shell_quotes_file_paths(self) -> None:
        cases = [
            ("relative/path.py", "--file relative/path.py"),
            ("/tmp/my notebook.py", "--file '/tmp/my notebook.py'"),
            (
                r"C:\Users\Jane Doe\notebook.py",
                r"--file 'C:\Users\Jane Doe\notebook.py'",
            ),
            (
                r"\\server\share\my notebook.py",
                r"--file '\\server\share\my notebook.py'",
            ),
            (
                "notebooks/it's.py",
                """--file 'notebooks/it'"'"'s.py'""",
            ),
        ]
        for file_path, expected in cases:
            result = _runner.invoke(
                cli_main,
                [
                    "pair",
                    "prompt",
                    "--url",
                    TEST_URL,
                    "--file",
                    file_path,
                ],
            )
            assert result.exit_code == 0
            assert expected in result.output

    def test_prompt_shell_quotes_url_with_metacharacters(self) -> None:
        # The execute-code.sh command is meant to be copy-pasted into a shell,
        # so a url with metacharacters (`&`) must be quoted so it isn't split.
        url = "http://localhost:8000?file=a&b"
        result = _runner.invoke(cli_main, ["pair", "prompt", "--url", url])
        assert result.exit_code == 0
        assert f"execute-code.sh --url '{url}'" in result.output

    def test_prompt_skill_missing(self) -> None:
        with patch.object(AgentConfig, "has_skill", return_value=False):
            for flag in ("--claude", "--codex", "--opencode"):
                result = _runner.invoke(
                    cli_main,
                    ["pair", "prompt", "--url", TEST_URL, flag],
                )
                assert result.exit_code == 0, flag
                assert "could not be found" in result.output, flag

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
    def test_with_token_writes_file_and_outputs_prompt(
        self, tmp_path: Path
    ) -> None:
        with patch(
            "marimo._cli.pair.commands._token_dir", return_value=tmp_path
        ):
            result = _runner.invoke(
                cli_main,
                ["pair", "prompt", "--url", TEST_URL, "--with-token"],
                input="my-secret-token\n",
            )
        assert result.exit_code == 0
        assert TEST_URL in result.output
        assert "execute-code.sh" in result.output
        assert "token" in result.output.lower()
        assert "cat" in result.output

        url_hash = hashlib.sha256(TEST_URL.encode()).hexdigest()[:6]
        token_file = tmp_path / f"{url_hash}-token.txt"
        assert token_file.exists()
        assert token_file.read_text() == "my-secret-token"
        if sys.platform != "win32":
            assert oct(token_file.stat().st_mode & 0o777) == "0o600"

    def test_with_token_and_file(self, tmp_path: Path) -> None:
        with patch(
            "marimo._cli.pair.commands._token_dir", return_value=tmp_path
        ):
            result = _runner.invoke(
                cli_main,
                [
                    "pair",
                    "prompt",
                    "--url",
                    TEST_URL,
                    "--file",
                    "notebooks/my notebook.py",
                    "--with-token",
                ],
                input="my-secret-token\n",
            )
        assert result.exit_code == 0
        assert "--file 'notebooks/my notebook.py'" in result.output
        # The token hint should target the same file.
        assert "--file 'notebooks/my notebook.py' --token" in result.output

    def test_with_token_still_requires_url(self) -> None:
        result = _runner.invoke(
            cli_main,
            ["pair", "prompt", "--with-token"],
            input="tok\n",
        )
        assert result.exit_code != 0

    def test_with_token_and_agent_flag(self, tmp_path: Path) -> None:
        with (
            patch.object(AgentConfig, "has_skill", return_value=True),
            patch(
                "marimo._cli.pair.commands._token_dir",
                return_value=tmp_path,
            ),
        ):
            result = _runner.invoke(
                cli_main,
                [
                    "pair",
                    "prompt",
                    "--url",
                    TEST_URL,
                    "--claude",
                    "--with-token",
                ],
                input="secret\n",
            )
        assert result.exit_code == 0
        assert TEST_URL in result.output
        assert "token" in result.output.lower()

    def test_with_token_and_skill_missing_fails(self) -> None:
        with patch.object(AgentConfig, "has_skill", return_value=False):
            result = _runner.invoke(
                cli_main,
                [
                    "pair",
                    "prompt",
                    "--url",
                    TEST_URL,
                    "--claude",
                    "--with-token",
                ],
                input="secret\n",
            )
        assert result.exit_code == 0
        assert "could not be found" in result.output

    def test_without_token_no_token_hint(self) -> None:
        result = _runner.invoke(
            cli_main, ["pair", "prompt", "--url", TEST_URL]
        )
        assert result.exit_code == 0
        assert "cat" not in result.output


class TestOpencodeSkillDirs:
    def test_opencode_skill_dirs(self) -> None:
        cwd = Path.cwd()
        home = Path.home()
        assert _opencode_skill_dirs() == [
            cwd / ".opencode" / "skills",
            home / ".config" / "opencode" / "skills",
            cwd / ".claude" / "skills",
            home / ".claude" / "skills",
            cwd / ".agents" / "skills",
            home / ".agents" / "skills",
        ]


class TestAgentConfig:
    def test_has_skill_true(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "skills"
        (skill_dir / "marimo-pair").mkdir(parents=True)
        (skill_dir / "marimo-pair" / "SKILL.md").write_text("test")

        agent = AgentConfig(name="test", skill_dirs=[skill_dir])
        assert agent.has_skill() is True

    def test_has_skill_false(self, tmp_path: Path) -> None:
        agent = AgentConfig(name="test", skill_dirs=[tmp_path / "nonexistent"])
        assert agent.has_skill() is False

    def test_has_skill_empty_dirs(self) -> None:
        agent = AgentConfig(name="test", skill_dirs=[])
        assert agent.has_skill() is False

    def test_has_skill_multiple_dirs_first_match(self, tmp_path: Path) -> None:
        dir1 = tmp_path / "a" / "skills"
        dir2 = tmp_path / "b" / "skills"
        (dir1 / "marimo-pair").mkdir(parents=True)
        (dir1 / "marimo-pair" / "SKILL.md").write_text("test")

        agent = AgentConfig(name="test", skill_dirs=[dir1, dir2])
        assert agent.has_skill() is True

    def test_has_skill_multiple_dirs_second_match(
        self, tmp_path: Path
    ) -> None:
        dir1 = tmp_path / "a" / "skills"
        dir2 = tmp_path / "b" / "skills"
        (dir2 / "marimo-pair").mkdir(parents=True)
        (dir2 / "marimo-pair" / "SKILL.md").write_text("test")

        agent = AgentConfig(name="test", skill_dirs=[dir1, dir2])
        assert agent.has_skill() is True


class TestPluginSkillDirs:
    def test_pair_agents_discovers_plugin_skills(self, tmp_path: Path) -> None:
        claude_skill_dir = (
            tmp_path
            / ".claude"
            / "plugins"
            / "marketplaces"
            / "marimo-pair"
            / "skills"
            / "marimo-pair"
        )
        codex_skill_dir = (
            tmp_path
            / ".codex"
            / "plugins"
            / "cache"
            / "marimo-pair"
            / "marimo-pair"
            / "0.0.18"
            / "skills"
            / "marimo-pair"
        )
        claude_skill_dir.mkdir(parents=True)
        codex_skill_dir.mkdir(parents=True)
        (claude_skill_dir / "SKILL.md").write_text("test")
        (codex_skill_dir / "SKILL.md").write_text("test")

        with (
            patch.object(Path, "home", return_value=tmp_path),
            patch.object(Path, "cwd", return_value=tmp_path),
        ):
            agents = pair_agents()

        assert agents["claude"].has_skill() is True
        assert agents["codex"].has_skill() is True

    def test_claude_marketplace_layout(self, tmp_path: Path) -> None:
        skill_dir = (
            tmp_path / "plugins" / "marketplaces" / "marimo-pair" / "skills"
        )
        (skill_dir / "marimo-pair").mkdir(parents=True)
        (skill_dir / "marimo-pair" / "SKILL.md").write_text("test")

        agent = AgentConfig(
            name="Claude Code",
            skill_dirs=_plugin_skill_dirs(tmp_path),
        )
        assert agent.has_skill() is True

    def test_plugin_cache_layout(self, tmp_path: Path) -> None:
        skill_dir = (
            tmp_path
            / "plugins"
            / "cache"
            / "marimo-pair"
            / "marimo-pair"
            / "0.0.18"
            / "skills"
        )
        (skill_dir / "marimo-pair").mkdir(parents=True)
        (skill_dir / "marimo-pair" / "SKILL.md").write_text("test")

        agent = AgentConfig(
            name="Codex",
            skill_dirs=_plugin_skill_dirs(tmp_path),
        )
        assert agent.has_skill() is True
