# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner, Result

import marimo._cli.pair.commands as pair_commands
from marimo._cli.cli import main as cli_main
from marimo._cli.pair.client import (
    ExecutionResult,
    PairError,
    PairServer,
    SessionInfo,
)
from marimo._cli.pair.commands import (
    AgentConfig,
    _opencode_skill_dirs,
    _plugin_skill_dirs,
    pair_agents,
)
from marimo._cli.pair.discovery import DiscoveryResult

if TYPE_CHECKING:
    from collections.abc import Generator

_runner = CliRunner()

TEST_URL = "https://localhost:8000"


@dataclass
class FakeGuideClient:
    token: str | None = None

    def version(self) -> str:
        return "0.24.1"

    def resolve_session(
        self,
        *,
        session_id: str | None,
        notebook: str | None,
    ) -> SessionInfo:
        return SessionInfo(
            session_id or "resolved-session",
            notebook or "notebook.py",
            notebook,
        )


@pytest.fixture
def guide_client() -> Generator[FakeGuideClient, None, None]:
    client = FakeGuideClient()

    def factory(
        server: PairServer,
        *,
        token: str | None,
    ) -> FakeGuideClient:
        del server
        client.token = token
        return client

    with patch.object(pair_commands, "PairClient", side_effect=factory):
        yield client


class TestPairGroup:
    def test_pair_help(self) -> None:
        result = _runner.invoke(cli_main, ["pair", "--help"])
        assert result.exit_code == 0
        assert "pair programming" in result.output.lower()
        assert "discover" in result.output
        assert "guide" in result.output
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
    @pytest.fixture(autouse=True)
    def _guide_client(self, guide_client: FakeGuideClient) -> None:
        del guide_client

    def test_prompt_requires_url(self) -> None:
        result = _runner.invoke(cli_main, ["pair", "prompt"])
        assert result.exit_code != 0

    def test_prompt_outputs_url(self) -> None:
        result = _runner.invoke(
            cli_main, ["pair", "prompt", "--url", TEST_URL]
        )
        assert result.exit_code == 0
        assert TEST_URL in result.output
        assert "marimo pair execute" in result.output
        assert "execute-code.sh" not in result.output

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
        assert "--session resolved-session" in result.output

    def test_prompt_without_file_omits_flag(self) -> None:
        result = _runner.invoke(
            cli_main, ["pair", "prompt", "--url", TEST_URL]
        )
        assert result.exit_code == 0
        assert "--file" not in result.output
        assert "--session resolved-session" in result.output

    def test_prompt_rejects_removed_session_option(self) -> None:
        result = _runner.invoke(
            cli_main,
            ["pair", "prompt", "--url", TEST_URL, "--session", "s_ab12cd"],
        )
        assert result.exit_code != 0
        assert "--session" in result.output

    def test_prompt_preserves_opaque_file_keys(self) -> None:
        cases = [
            "relative/path.py",
            "/tmp/my notebook.py",
            r"C:\Users\Jane Doe\notebook.py",
            r"\\server\share\my notebook.py",
            "notebooks/it's.py",
        ]
        for file_path in cases:
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
            assert f"Notebook key: `{file_path}`" in result.output

    def test_prompt_shell_quotes_url_with_metacharacters(self) -> None:
        # The generated command is meant to be copy-pasted into a shell, so a
        # URL with metacharacters (`&`) must be quoted so it is not split.
        url = "http://localhost:8000?file=a&b"
        result = _runner.invoke(cli_main, ["pair", "prompt", "--url", url])
        assert result.exit_code == 0
        assert f"--url '{url}'" in result.output

    def test_prompt_skill_missing(self) -> None:
        with patch.object(AgentConfig, "has_skill", return_value=False):
            for flag in ("--claude", "--codex", "--opencode"):
                result = _runner.invoke(
                    cli_main,
                    ["pair", "prompt", "--url", TEST_URL, flag],
                )
                assert result.exit_code == 0, flag
                assert "could not be found" in result.output, flag
                assert (
                    "npx skills add marimo-team/marimo --skill marimo-pair"
                    in result.stderr
                ), flag

    def test_prompt_skill_installed(self) -> None:
        with patch.object(AgentConfig, "has_skill", return_value=True):
            for flag in ("--claude", "--codex", "--opencode"):
                result = _runner.invoke(
                    cli_main,
                    ["pair", "prompt", "--url", TEST_URL, flag],
                )
                assert result.exit_code == 0, flag
                assert TEST_URL in result.output, flag


class TestPairDiscover:
    def test_discover_help(self) -> None:
        result = _runner.invoke(cli_main, ["pair", "discover", "--help"])

        assert result.exit_code == 0
        assert "--format" in result.output
        assert "--json-errors" in result.output

    def test_discover_json_matches_frozen_fixture(self) -> None:
        fixture_path = (
            Path(__file__).parent
            / "fixtures"
            / "marimo_pair_v0_0_19"
            / "discover-output.json"
        )
        expected_text = fixture_path.read_text(encoding="utf-8")
        expected = json.loads(expected_text)
        discovery = DiscoveryResult(
            servers=tuple(PairServer(**entry) for entry in expected),
            warnings=(),
        )

        with patch(
            "marimo._cli.pair.commands.discover_servers",
            return_value=discovery,
        ):
            result = _runner.invoke(
                cli_main,
                ["pair", "discover", "--format", "json"],
            )

        assert result.exit_code == 0
        assert result.stdout == expected_text
        assert result.stderr == ""

    def test_discover_text_uses_stable_tab_separated_fields(self) -> None:
        discovery = DiscoveryResult(
            servers=(
                PairServer(
                    server_id="127.0.0.1:2718",
                    origin="local",
                    url="http://127.0.0.1:2718",
                    started_at="2026-08-31T00:00:00+00:00",
                    version="0.24.0",
                ),
            ),
            warnings=(),
        )

        with patch(
            "marimo._cli.pair.commands.discover_servers",
            return_value=discovery,
        ):
            result = _runner.invoke(cli_main, ["pair", "discover"])

        assert result.exit_code == 0
        assert result.stdout == (
            "127.0.0.1:2718\tlocal\thttp://127.0.0.1:2718\t"
            "0.24.0\t2026-08-31T00:00:00+00:00\n"
        )
        assert result.stderr == ""

    def test_discover_writes_warnings_only_to_stderr(self) -> None:
        discovery = DiscoveryResult(
            servers=(),
            warnings=("The Windows-host server is unreachable.",),
        )

        with patch(
            "marimo._cli.pair.commands.discover_servers",
            return_value=discovery,
        ):
            result = _runner.invoke(
                cli_main,
                ["pair", "discover", "--format", "json"],
            )

        assert result.exit_code == 0
        assert json.loads(result.stdout) == []
        assert result.stderr == "The Windows-host server is unreachable.\n"

    @pytest.mark.parametrize("output_format", ["text", "json"])
    def test_discover_redacts_url_userinfo_and_query_values(
        self,
        output_format: str,
    ) -> None:
        discovery = DiscoveryResult(
            servers=(
                PairServer(
                    server_id="localhost:2718",
                    origin="direct",
                    url=(
                        "http://user:secret@localhost:2718/base"
                        "?token=secret&mode=edit"
                    ),
                    started_at="2026-08-31T00:00:00+00:00",
                    version="0.24.0",
                ),
            ),
            warnings=(),
        )

        with patch(
            "marimo._cli.pair.commands.discover_servers",
            return_value=discovery,
        ):
            result = _runner.invoke(
                cli_main,
                ["pair", "discover", "--format", output_format],
            )

        assert result.exit_code == 0
        assert "user" not in result.stdout
        assert "secret" not in result.stdout
        assert "token=REDACTED&mode=REDACTED" in result.stdout

    @pytest.mark.parametrize(
        ("arguments", "expected_stderr"),
        [
            ([], "Error: No marimo server was found.\n"),
            (
                ["--json-errors"],
                '{"kind": "no_server", "message": "No marimo server was found."}\n',
            ),
        ],
    )
    def test_discover_renders_stable_errors(
        self,
        arguments: list[str],
        expected_stderr: str,
    ) -> None:
        with patch(
            "marimo._cli.pair.commands.discover_servers",
            side_effect=PairError(
                kind="no_server",
                message="No marimo server was found.",
            ),
        ):
            result = _runner.invoke(
                cli_main,
                ["pair", "discover", *arguments],
            )

        assert result.exit_code == 1
        assert result.stdout == ""
        assert result.stderr == expected_stderr


class TestPairGuide:
    def test_guide_help_matches_execute_target_options(self) -> None:
        guide_help = _runner.invoke(cli_main, ["pair", "guide", "--help"])
        execute_help = _runner.invoke(cli_main, ["pair", "execute", "--help"])

        assert guide_help.exit_code == 0
        for option in (
            "--url",
            "--session",
            "--notebook",
            "--file",
            "--token-file",
            "--allow-insecure-http",
            "--json-errors",
        ):
            assert option in guide_help.output
            assert option in execute_help.output

    def test_guide_writes_only_guide_to_stdout(
        self, guide_client: FakeGuideClient
    ) -> None:
        result = _runner.invoke(
            cli_main,
            ["pair", "guide", "--url", "https://example.com"],
        )

        assert result.exit_code == 0
        assert "Server: `https://example.com`" in result.stdout
        assert "Session: `resolved-session`" in result.stdout
        assert "marimo pair execute" in result.stdout
        assert result.stderr == ""
        assert guide_client.token is None

    def test_guide_writes_discovery_warnings_to_stderr(
        self, guide_client: FakeGuideClient
    ) -> None:
        server = PairServer(
            "local",
            "local",
            "http://127.0.0.1:2718",
            "",
            "0.24.1",
        )
        with patch.object(
            pair_commands,
            "discover_servers",
            return_value=DiscoveryResult(
                (server,), ("Ignored one stale server record.",)
            ),
        ):
            result = _runner.invoke(cli_main, ["pair", "guide"])

        assert result.exit_code == 0
        assert "Server: `http://127.0.0.1:2718`" in result.stdout
        assert "Ignored one stale server record." not in result.stdout
        assert result.stderr == "Ignored one stale server record.\n"
        assert guide_client.token is None

    @pytest.mark.parametrize(
        ("arguments", "expected_stderr"),
        [
            (
                [],
                (
                    "Error: More than one reachable marimo server was found. "
                    "Run `marimo pair discover` to list targets.\n"
                ),
            ),
            (
                ["--json-errors"],
                (
                    '{"kind": "ambiguous_server", "message": "More than one '
                    "reachable marimo server was found. Run `marimo pair "
                    'discover` to list targets."}\n'
                ),
            ),
        ],
    )
    def test_guide_ambiguity_has_exact_recovery_command(
        self,
        guide_client: FakeGuideClient,
        arguments: list[str],
        expected_stderr: str,
    ) -> None:
        del guide_client
        servers = (
            PairServer("one", "local", "http://127.0.0.1:2718", "", ""),
            PairServer("two", "local", "http://127.0.0.1:2719", "", ""),
        )
        with patch.object(
            pair_commands,
            "discover_servers",
            return_value=DiscoveryResult(servers, ()),
        ):
            result = _runner.invoke(cli_main, ["pair", "guide", *arguments])

        assert result.exit_code == 1
        assert result.stdout == ""
        assert result.stderr == expected_stderr

    def test_guide_file_alias_selects_notebook(
        self, guide_client: FakeGuideClient
    ) -> None:
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "guide",
                "--url",
                "https://example.com",
                "--file",
                "opaque/notebook.py",
            ],
        )

        assert result.exit_code == 0
        assert "Notebook key: `opaque/notebook.py`" in result.stdout
        assert guide_client.token is None


class TestPairPromptWithToken:
    @pytest.fixture(autouse=True)
    def _guide_client(self, guide_client: FakeGuideClient) -> None:
        del guide_client

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
        assert "marimo pair execute" in result.output
        assert "execute-code.sh" not in result.output
        assert "my-secret-token" not in result.output

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
        assert "Notebook key: `notebooks/my notebook.py`" in result.output
        assert "--session resolved-session" in result.output
        assert "--token-file" in result.output

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
        assert "Token source: `none`" in result.output
        assert "--token-file" not in result.output


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


@dataclass
class FakeExecutionClient:
    version_text: str = "0.24.0"
    result: ExecutionResult = field(
        default_factory=lambda: ExecutionResult(success=True, output="")
    )
    version_error: BaseException | None = None
    execution_error: BaseException | None = None
    token: str | None = None
    session_selector: tuple[str | None, str | None] | None = None
    executed: tuple[str, str] | None = None

    def version(self) -> str:
        if self.version_error is not None:
            raise self.version_error
        return self.version_text

    def resolve_session(
        self,
        *,
        session_id: str | None,
        notebook: str | None,
    ) -> SessionInfo:
        self.session_selector = (session_id, notebook)
        return SessionInfo("resolved-session", "notebook.py", "/notebook.py")

    def execute(
        self,
        session_id: str,
        code: str,
        *,
        stdout: object,
        stderr: object,
    ) -> ExecutionResult:
        del stdout, stderr
        self.executed = (session_id, code)
        if self.execution_error is not None:
            raise self.execution_error
        return self.result


def _invoke_pair_execute(
    arguments: list[str],
    *,
    client: FakeExecutionClient | None = None,
    input_text: str | None = None,
    environment: dict[str, str] | None = None,
) -> tuple[Result, FakeExecutionClient, MagicMock]:
    execution_client = client or FakeExecutionClient()

    def client_factory(
        server: PairServer,
        *,
        token: str | None,
    ) -> FakeExecutionClient:
        del server
        execution_client.token = token
        return execution_client

    with (
        patch.object(
            pair_commands,
            "PairClient",
            side_effect=client_factory,
            create=True,
        ),
        patch.object(
            pair_commands,
            "ensure_client_version",
            create=True,
        ) as ensure_version,
    ):
        result = _runner.invoke(
            cli_main,
            ["pair", "execute", *arguments],
            input=input_text,
            env=environment,
        )
    return result, execution_client, ensure_version


class TestPairExecute:
    def test_execute_help_lists_target_and_input_options(self) -> None:
        result = _runner.invoke(cli_main, ["pair", "execute", "--help"])

        assert result.exit_code == 0
        for option in (
            "--url",
            "--session",
            "--notebook",
            "--file",
            "--token-file",
            "--allow-insecure-http",
            "--code-file",
            "-c",
            "--json-errors",
        ):
            assert option in result.output

    def test_execute_resolves_target_before_reading_code(self) -> None:
        events: list[str] = []
        server = PairServer("server", "direct", "https://example.com", "", "")

        class OrderedClient(FakeExecutionClient):
            def version(self) -> str:
                events.append("read server version")
                return "0.24.0"

            def resolve_session(
                self,
                *,
                session_id: str | None,
                notebook: str | None,
            ) -> SessionInfo:
                del session_id, notebook
                events.append("resolve session")
                return SessionInfo("session", "notebook.py", "/notebook.py")

            def execute(
                self,
                session_id: str,
                code: str,
                *,
                stdout: object,
                stderr: object,
            ) -> ExecutionResult:
                del session_id, code, stdout, stderr
                events.append("submit execution")
                return ExecutionResult(True, "")

        client = OrderedClient()

        def record_token(**kwargs: object) -> None:
            del kwargs
            events.append("resolve token")

        def record_server(**kwargs: object) -> PairServer:
            del kwargs
            events.append("resolve server")
            return server

        def record_version(*args: object, **kwargs: object) -> None:
            del args, kwargs
            events.append("select client version")

        def record_code(*args: object, **kwargs: object) -> str:
            del args, kwargs
            events.append("read code")
            return "1 + 1"

        with (
            patch.object(
                pair_commands,
                "load_token",
                side_effect=record_token,
                create=True,
            ),
            patch.object(
                pair_commands,
                "resolve_server",
                side_effect=record_server,
                create=True,
            ),
            patch.object(
                pair_commands,
                "PairClient",
                return_value=client,
                create=True,
            ),
            patch.object(
                pair_commands,
                "ensure_client_version",
                side_effect=record_version,
                create=True,
            ),
            patch.object(
                pair_commands,
                "_read_code",
                side_effect=record_code,
                create=True,
            ),
        ):
            result = _runner.invoke(
                cli_main,
                [
                    "pair",
                    "execute",
                    "--url",
                    "https://example.com",
                    "--session",
                    "session",
                    "-c",
                    "1 + 1",
                ],
            )

        assert result.exit_code == 0
        assert events == [
            "resolve token",
            "resolve server",
            "read server version",
            "select client version",
            "resolve session",
            "read code",
            "submit execution",
        ]

    def test_execute_does_not_read_stdin_when_version_selection_fails(
        self,
    ) -> None:
        with (
            patch.object(
                pair_commands,
                "PairClient",
                create=True,
            ) as client_type,
            patch.object(
                pair_commands,
                "ensure_client_version",
                side_effect=PairError(
                    "version_unavailable",
                    "The matching version is unavailable.",
                ),
                create=True,
            ),
            patch.object(
                pair_commands,
                "_read_code",
                side_effect=AssertionError("stdin was read"),
                create=True,
            ) as read_code,
        ):
            client_type.return_value.version.return_value = "0.25.0"
            result = _runner.invoke(
                cli_main,
                ["pair", "execute", "--url", "https://example.com"],
                input="must remain unread\n",
            )

        assert result.exit_code == 1
        assert "unavailable" in result.stderr
        read_code.assert_not_called()

    def test_execute_preserves_inline_code(self) -> None:
        result, client, _ensure = _invoke_pair_execute(
            ["--url", "https://example.com", "-c", "print(1)\n"]
        )

        assert result.exit_code == 0
        assert client.executed == ("resolved-session", "print(1)\n")

    def test_execute_preserves_code_file_final_newline(
        self,
        tmp_path: Path,
    ) -> None:
        code_file = tmp_path / "code.py"
        code_file.write_text("print(2)\n", encoding="utf-8")

        result, client, _ensure = _invoke_pair_execute(
            [
                "--url",
                "https://example.com",
                "--code-file",
                str(code_file),
            ]
        )

        assert result.exit_code == 0
        assert client.executed == ("resolved-session", "print(2)\n")

    def test_execute_preserves_stdin_final_newline(self) -> None:
        result, client, _ensure = _invoke_pair_execute(
            ["--url", "https://example.com"],
            input_text="print(3)\n",
        )

        assert result.exit_code == 0
        assert client.executed == ("resolved-session", "print(3)\n")

    def test_execute_rejects_conflicting_code_sources(
        self,
        tmp_path: Path,
    ) -> None:
        code_file = tmp_path / "code.py"
        code_file.write_text("print(2)", encoding="utf-8")

        result, client, _ensure = _invoke_pair_execute(
            [
                "--url",
                "https://example.com",
                "-c",
                "print(1)",
                "--code-file",
                str(code_file),
            ]
        )

        assert result.exit_code == 2
        assert "use either -c or --code-file" in result.stderr.lower()
        assert client.executed is None

    def test_execute_rejects_missing_code(self) -> None:
        result, client, _ensure = _invoke_pair_execute(
            ["--url", "https://example.com"],
            input_text="",
        )

        assert result.exit_code == 2
        assert "no code was provided" in result.stderr.lower()
        assert client.executed is None

    @pytest.mark.parametrize(
        ("selector", "expected"),
        [
            (["--session", "session-one"], ("session-one", None)),
            (["--notebook", "opaque/key.py"], (None, "opaque/key.py")),
            (
                ["--file", r"C:\work\notebook.py"],
                (None, r"C:\work\notebook.py"),
            ),
        ],
    )
    def test_execute_passes_session_selectors(
        self,
        selector: list[str],
        expected: tuple[str | None, str | None],
    ) -> None:
        result, client, _ensure = _invoke_pair_execute(
            ["--url", "https://example.com", *selector, "-c", "1 + 1"]
        )

        assert result.exit_code == 0
        assert client.session_selector == expected

    def test_execute_rejects_conflicting_session_selectors(self) -> None:
        result, client, _ensure = _invoke_pair_execute(
            [
                "--url",
                "https://example.com",
                "--session",
                "session-one",
                "--notebook",
                "notebook.py",
                "-c",
                "1 + 1",
            ]
        )

        assert result.exit_code == 2
        assert "use either --session or --notebook" in result.stderr.lower()
        assert client.session_selector is None

    def test_execute_uses_environment_token_without_rendering_it(self) -> None:
        result, client, ensure = _invoke_pair_execute(
            ["--url", "https://example.com", "-c", "1 + 1"],
            environment={"MARIMO_TOKEN": "secret-token"},
        )

        assert result.exit_code == 0
        assert client.token == "secret-token"
        assert "secret-token" not in result.output
        assert "secret-token" not in repr(ensure.call_args)

    def test_execute_token_file_overrides_environment(
        self,
        tmp_path: Path,
    ) -> None:
        token_file = tmp_path / "token.txt"
        token_file.write_text("file-token\n", encoding="utf-8")

        result, client, _ensure = _invoke_pair_execute(
            [
                "--url",
                "https://example.com",
                "--token-file",
                str(token_file),
                "-c",
                "1 + 1",
            ],
            environment={"MARIMO_TOKEN": "environment-token"},
        )

        assert result.exit_code == 0
        assert client.token == "file-token"
        assert "file-token" not in result.output
        assert "environment-token" not in result.output

    def test_execute_requires_override_for_remote_http(self) -> None:
        blocked, _client, _ensure = _invoke_pair_execute(
            ["--url", "http://example.com", "-c", "1 + 1"]
        )
        allowed, client, _ensure = _invoke_pair_execute(
            [
                "--url",
                "http://example.com",
                "--allow-insecure-http",
                "-c",
                "1 + 1",
            ]
        )

        assert blocked.exit_code == 1
        assert allowed.exit_code == 0
        assert client.executed == ("resolved-session", "1 + 1")

    def test_execute_discovers_server_when_url_is_omitted(self) -> None:
        discovered = PairServer(
            "server",
            "local",
            "http://127.0.0.1:2718",
            "",
            "0.24.0",
        )

        with patch.object(
            pair_commands,
            "discover_servers",
            return_value=DiscoveryResult((discovered,), ()),
        ):
            result, client, _ensure = _invoke_pair_execute(["-c", "1 + 1"])

        assert result.exit_code == 0
        assert client.executed == ("resolved-session", "1 + 1")

    @pytest.mark.parametrize(
        ("execution_result", "execution_error", "expected_exit"),
        [
            (ExecutionResult(True, ""), None, 0),
            (ExecutionResult(False, ""), None, 1),
            (ExecutionResult(True, ""), KeyboardInterrupt(), 130),
            (ExecutionResult(True, ""), BrokenPipeError(), 1),
            (
                ExecutionResult(True, ""),
                PairError("kernel_failure", "Kernel failed."),
                1,
            ),
        ],
    )
    def test_execute_maps_exit_statuses(
        self,
        execution_result: ExecutionResult,
        execution_error: BaseException | None,
        expected_exit: int,
    ) -> None:
        client = FakeExecutionClient(
            result=execution_result,
            execution_error=execution_error,
        )

        result, _client, _ensure = _invoke_pair_execute(
            ["--url", "https://example.com", "-c", "1 + 1"],
            client=client,
        )

        assert result.exit_code == expected_exit

    def test_execute_renders_json_errors(self) -> None:
        client = FakeExecutionClient(
            version_error=PairError("connection_failed", "No connection."),
        )

        result, _client, _ensure = _invoke_pair_execute(
            [
                "--url",
                "https://example.com",
                "--json-errors",
                "-c",
                "1 + 1",
            ],
            client=client,
        )

        assert result.exit_code == 1
        assert result.stderr == (
            '{"kind": "connection_failed", "message": "No connection."}\n'
        )
