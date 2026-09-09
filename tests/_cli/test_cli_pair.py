# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from inline_snapshot import snapshot

from marimo._cli.cli import main as cli_main
from marimo._cli.pair import commands
from marimo._cli.pair.client import ExecutionResult, PairError
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
        assert result.output == snapshot("""\
Usage: main pair [OPTIONS] COMMAND [ARGS]...

  Pair with a live marimo notebook.

  Read a command's --help before first use.

Options:
  -h, --help  Show this message and exit.

Commands:
  docs       Read notebook guidance on demand. Run: uv run marimo pair docs
             --help
  execute    Run Python in a live notebook session. Run: uv run marimo pair
             execute --help
  notebooks  Find active notebooks and their sessions. Run: uv run marimo pair
             notebooks --help
  prompt     Generate pairing instructions. Run: uv run marimo pair prompt
             --help
""")

    def test_prompt_help(self) -> None:
        result = _runner.invoke(cli_main, ["pair", "prompt", "--help"])
        assert result.exit_code == 0
        assert "--url" in result.output
        assert "--claude" in result.output
        assert "--codex" in result.output
        assert "--opencode" in result.output
        assert "--file" in result.output
        assert "--session" in result.output


class TestPairExecute:
    def test_execute_help_is_offline(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fail_execute(**kwargs: Any) -> ExecutionResult:
            del kwargs
            raise AssertionError("execute must not run while showing help")

        monkeypatch.setattr(commands, "execute_code", fail_execute)
        result = _runner.invoke(
            cli_main,
            ["pair", "execute", "--help"],
            input="print(1)\n",
        )

        assert result.exit_code == 0
        assert result.output == snapshot("""\
Usage: main pair execute [OPTIONS]

  Run Python in the selected live notebook kernel's scratchpad.

Options:
  --url URL          Server URL.  [required]
  --session ID       Current session ID. Required on every execution.
                     [required]
  --token-file PATH  Read the server token from a local file. Otherwise use
                     MARIMO_TOKEN, if set.
  -c TEXT            Inline Python.
  --code-file PATH   Read Python from a UTF-8 file. Supply exactly one input
                     option. No implicit stdin input.
  --no-stream        Buffer output until execution ends. Default: stream stdout
                     and stderr as they arrive.
  -h, --help         Show this message and exit.

  If you have not already inspected cm in this kernel, execute this call
  by itself before task-specific code:
    import marimo._code_mode as cm
    help(cm)

  The live kernel is the source of truth for state and available cm APIs.
  Scratchpad bindings are temporary. Make durable notebook edits through cm.
  Import cm in the scratchpad, not into a notebook cell.

  If a session is stale, rediscover it. Never silently switch sessions. Ctrl-C
  closes the request; the server interrupts the session kernel. If the
  connection ends before completion is confirmed, do not retry execution
  automatically. Inspect notebook state before deciding what to do.

  For name-redefinition traps: marimo pair docs gotchas
  For custom visual output: marimo pair docs rich-representations
  For notebook cleanup: marimo pair docs notebook-improvements

  First inspection template:
    uv run marimo pair execute --url '<server-url>' --session '<session-id>' --token-file '<token-file>' -c 'import marimo._code_mode as cm; help(cm)'
""")

    @pytest.mark.parametrize(
        "arguments",
        [
            [],
            ["-c", "print(1)", "--code-file", "code.py"],
        ],
    )
    def test_execute_requires_exactly_one_input(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        arguments: list[str],
    ) -> None:
        code_file = tmp_path / "code.py"
        code_file.write_text("print(2)", encoding="utf-8")
        resolved_arguments = [
            str(code_file) if value == "code.py" else value
            for value in arguments
        ]
        calls: list[dict[str, Any]] = []
        monkeypatch.setattr(
            commands,
            "execute_code",
            lambda **kwargs: calls.append(kwargs),
        )

        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "execute",
                "--url",
                TEST_URL,
                "--session",
                "s_ab12cd",
                *resolved_arguments,
            ],
            input="print('ignored')\n",
        )

        assert result.exit_code == 2
        assert "specify -c or --code-file" in result.output
        assert calls == []

    def test_execute_rejects_empty_code(self) -> None:
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "execute",
                "--url",
                TEST_URL,
                "--session",
                "s_ab12cd",
                "-c",
                "",
            ],
        )

        assert result.exit_code == 2
        assert "code must not be empty" in result.output

    def test_execute_reads_code_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        code_file = tmp_path / "code.py"
        code_file.write_text("print('from file')", encoding="utf-8")
        calls: list[dict[str, Any]] = []

        def fake_execute(**kwargs: Any) -> ExecutionResult:
            calls.append(kwargs)
            return ExecutionResult(success=True, output="")

        monkeypatch.setattr(commands, "execute_code", fake_execute)
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "execute",
                "--url",
                TEST_URL,
                "--session",
                "s_ab12cd",
                "--code-file",
                str(code_file),
            ],
        )

        assert result.exit_code == 0
        assert calls[0]["code"] == "print('from file')"

    def test_execute_rejects_invalid_utf8_code_file(
        self, tmp_path: Path
    ) -> None:
        code_file = tmp_path / "code.py"
        code_file.write_bytes(b"\xff")

        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "execute",
                "--url",
                TEST_URL,
                "--session",
                "s_ab12cd",
                "--code-file",
                str(code_file),
            ],
        )

        assert result.exit_code == 2
        assert "error: could not read the code file" in result.output

    def test_execute_rejects_unreadable_code_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        code_file = tmp_path / "code.py"
        code_file.write_text("print(1)", encoding="utf-8")

        def fail_read_text(self: Path, *, encoding: str) -> str:
            del self, encoding
            raise OSError("permission denied")

        monkeypatch.setattr(Path, "read_text", fail_read_text)
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "execute",
                "--url",
                TEST_URL,
                "--session",
                "s_ab12cd",
                "--code-file",
                str(code_file),
            ],
        )

        assert result.exit_code == 2
        assert "error: could not read the code file" in result.output

    def test_execute_success_and_default_streaming(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[dict[str, Any]] = []

        def fake_execute(**kwargs: Any) -> ExecutionResult:
            calls.append(kwargs)
            return ExecutionResult(success=True, output="done")

        monkeypatch.setattr(commands, "execute_code", fake_execute)
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "execute",
                "--url",
                TEST_URL,
                "--session",
                "s_ab12cd",
                "-c",
                "print(1)",
            ],
        )

        assert result.exit_code == 0
        assert calls[0]["url"] == TEST_URL
        assert calls[0]["session_id"] == "s_ab12cd"
        assert calls[0]["code"] == "print(1)"
        assert calls[0]["token"] is None
        assert calls[0]["stream"] is True

    def test_execute_failure_exits_one(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fail_execution(**kwargs: Any) -> ExecutionResult:
            del kwargs
            return ExecutionResult(success=False, output="failed")

        monkeypatch.setattr(commands, "execute_code", fail_execution)

        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "execute",
                "--url",
                TEST_URL,
                "--session",
                "s_ab12cd",
                "-c",
                "raise ValueError",
            ],
        )

        assert result.exit_code == 1

    def test_execute_reports_pair_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fail_execute(**kwargs: Any) -> ExecutionResult:
            del kwargs
            raise PairError("Could not execute code.")

        monkeypatch.setattr(commands, "execute_code", fail_execute)
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "execute",
                "--url",
                TEST_URL,
                "--session",
                "s_ab12cd",
                "-c",
                "print(1)",
            ],
        )

        assert result.exit_code == 1
        assert result.stderr == "Could not execute code.\n"

    def test_execute_reports_interrupt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def interrupt(**kwargs: Any) -> ExecutionResult:
            del kwargs
            raise KeyboardInterrupt

        monkeypatch.setattr(commands, "execute_code", interrupt)
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "execute",
                "--url",
                TEST_URL,
                "--session",
                "s_ab12cd",
                "-c",
                "print(1)",
            ],
        )

        assert result.exit_code == 1
        assert result.stderr == "Interrupted.\n"

    def test_execute_no_stream_and_token_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        token_file = tmp_path / "token.txt"
        token_file.write_text("secret", encoding="utf-8")
        token_calls: list[Path | None] = []
        execute_calls: list[dict[str, Any]] = []

        def fake_load_token(path: Path | None, environ: Any) -> str | None:
            del environ
            token_calls.append(path)
            return "secret"

        def fake_execute(**kwargs: Any) -> ExecutionResult:
            execute_calls.append(kwargs)
            return ExecutionResult(success=True, output="")

        monkeypatch.setattr(commands, "load_token", fake_load_token)
        monkeypatch.setattr(commands, "execute_code", fake_execute)
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "execute",
                "--url",
                TEST_URL,
                "--session",
                "s_ab12cd",
                "--token-file",
                str(token_file),
                "--no-stream",
                "-c",
                "print(1)",
            ],
        )

        assert result.exit_code == 0
        assert token_calls == [token_file]
        assert execute_calls[0]["token"] == "secret"
        assert execute_calls[0]["stream"] is False


class TestPairDocs:
    def test_docs_help_lists_bundled_topics(self) -> None:
        result = _runner.invoke(cli_main, ["pair", "docs", "--help"])

        assert result.exit_code == 0
        assert result.output == snapshot("""\
Usage: main pair docs [OPTIONS] [TOPIC]

  Read notebook guidance on demand.

Options:
  -h, --help  Show this message and exit.

Available topics:
  gotchas                Gotchas
  notebook-improvements  Notebook Improvements
  rich-representations   Rich Representations
""")

    def test_docs_prints_topic(self) -> None:
        reference = commands._REFERENCES_DIR / "gotchas.md"

        result = _runner.invoke(cli_main, ["pair", "docs", "gotchas"])

        assert result.exit_code == 0
        assert result.output == reference.read_text(encoding="utf-8")

    def test_docs_lists_topics(self) -> None:
        result = _runner.invoke(cli_main, ["pair", "docs"])

        assert result.exit_code == 0
        assert result.output == snapshot("""\
gotchas  Gotchas
notebook-improvements  Notebook Improvements
rich-representations  Rich Representations
""")

    def test_docs_rejects_unknown_topic(self) -> None:
        result = _runner.invoke(cli_main, ["pair", "docs", "nope"])

        assert result.exit_code == 2
        assert (
            "Valid topics: gotchas, notebook-improvements, "
            "rich-representations" in result.output
        )

    def test_docs_help_discovers_new_topic(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        (tmp_path / "extra.md").write_text(
            "# Extra Guidance\n\nDetails.\n", encoding="utf-8"
        )
        monkeypatch.setattr(commands, "_REFERENCES_DIR", tmp_path)

        result = _runner.invoke(cli_main, ["pair", "docs", "--help"])

        assert result.exit_code == 0
        assert "extra  Extra Guidance" in result.output

    def test_docs_rejects_path_traversal(self) -> None:
        result = _runner.invoke(cli_main, ["pair", "docs", "../x"])

        assert result.exit_code == 2
        assert "Valid topics:" in result.output


class TestPairNotebooks:
    def test_notebooks_help(self) -> None:
        result = _runner.invoke(cli_main, ["pair", "notebooks", "--help"])

        assert result.exit_code == 0
        assert result.output == snapshot("""\
Usage: main pair notebooks [OPTIONS] COMMAND [ARGS]...

  Find active notebooks and their sessions.

Options:
  -h, --help  Show this message and exit.

Commands:
  list  List active notebooks and their session IDs. Run: uv run marimo pair
        notebooks list --help
""")

    def test_notebooks_list_help(self) -> None:
        result = _runner.invoke(
            cli_main, ["pair", "notebooks", "list", "--help"]
        )

        assert result.exit_code == 0
        assert result.output == snapshot("""\
Usage: main pair notebooks list [OPTIONS]

  List active notebooks and their session IDs.

Options:
  --url URL          Server URL. Repeat to list more than one server.
  --token-file PATH  Read the server token from a local file. Otherwise use
                     MARIMO_TOKEN, if set.
  -h, --help         Show this message and exit.

  This backend lists active notebooks only. Without --url, it discovers
  no-token servers from the local registry. For an authenticated server,
  supply its URL and credential source explicitly.

  Use the same URL and credential source for execution. Session IDs can become
  stale; list again instead of silently switching sessions.
""")

    def test_list_groups_sessions_for_one_notebook(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            commands,
            "list_sessions",
            lambda **_kwargs: {
                "session-2": {
                    "filename": "analysis.py",
                    "path": "/work/analysis.py",
                },
                "session-1": {
                    "filename": "analysis.py",
                    "path": "/work/analysis.py",
                },
            },
        )

        result = _runner.invoke(
            cli_main,
            ["pair", "notebooks", "list", "--url", "http://one"],
        )

        assert result.exit_code == 0
        assert json.loads(result.output) == {
            "notebooks": [
                {
                    "url": "http://one",
                    "filename": "analysis.py",
                    "path": "/work/analysis.py",
                    "sessions": [
                        {"session_id": "session-1"},
                        {"session_id": "session-2"},
                    ],
                }
            ],
            "errors": [],
        }

    def test_list_keeps_same_basename_on_two_urls_separate(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_list_sessions(
            *, url: str, token: str | None
        ) -> dict[str, dict[str, str | None]]:
            assert token is None
            return {
                f"session-{url[-1]}": {
                    "filename": "analysis.py",
                    "path": f"/work/{url[-1]}/analysis.py",
                }
            }

        monkeypatch.setattr(commands, "list_sessions", fake_list_sessions)
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "notebooks",
                "list",
                "--url",
                "http://two",
                "--url",
                "http://one",
            ],
        )

        assert result.exit_code == 0
        notebooks = json.loads(result.output)["notebooks"]
        assert [notebook["url"] for notebook in notebooks] == [
            "http://one",
            "http://two",
        ]
        assert len(notebooks) == 2

    def test_list_preserves_results_when_one_url_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_list_sessions(
            *, url: str, token: str | None
        ) -> dict[str, dict[str, str | None]]:
            assert token is None
            if url == "http://bad":
                raise PairError("Could not connect to http://bad.")
            return {
                "session-1": {
                    "filename": "analysis.py",
                    "path": "/work/analysis.py",
                }
            }

        monkeypatch.setattr(commands, "list_sessions", fake_list_sessions)
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "notebooks",
                "list",
                "--url",
                "http://bad",
                "--url",
                "http://good",
            ],
        )

        assert result.exit_code == 1
        assert json.loads(result.output) == {
            "notebooks": [
                {
                    "url": "http://good",
                    "filename": "analysis.py",
                    "path": "/work/analysis.py",
                    "sessions": [{"session_id": "session-1"}],
                }
            ],
            "errors": [
                {
                    "url": "http://bad",
                    "message": "Could not connect to http://bad.",
                }
            ],
        }

    def test_list_empty_registry_succeeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(commands, "registry_urls", list)
        monkeypatch.setattr(
            commands,
            "list_sessions",
            lambda **_kwargs: pytest.fail("No server should be queried"),
        )

        result = _runner.invoke(cli_main, ["pair", "notebooks", "list"])

        assert result.exit_code == 0
        assert json.loads(result.output) == {"notebooks": [], "errors": []}

    def test_list_uses_token_only_for_explicit_urls(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        token_file = tmp_path / "token.txt"
        load_calls: list[Path | None] = []
        session_calls: list[tuple[str, str | None]] = []

        def fake_load_token(path: Path | None, environ: Any) -> str | None:
            del environ
            load_calls.append(path)
            return "secret"

        def fake_list_sessions(
            *, url: str, token: str | None
        ) -> dict[str, dict[str, str | None]]:
            session_calls.append((url, token))
            return {}

        monkeypatch.setattr(commands, "load_token", fake_load_token)
        monkeypatch.setattr(commands, "list_sessions", fake_list_sessions)
        monkeypatch.setattr(
            commands, "registry_urls", lambda: ["http://discovered"]
        )

        discovered = _runner.invoke(
            cli_main,
            [
                "pair",
                "notebooks",
                "list",
                "--token-file",
                str(token_file),
            ],
        )
        explicit = _runner.invoke(
            cli_main,
            [
                "pair",
                "notebooks",
                "list",
                "--url",
                "http://explicit",
                "--token-file",
                str(token_file),
            ],
        )

        assert discovered.exit_code == 0
        assert explicit.exit_code == 0
        assert load_calls == [token_file]
        assert session_calls == [
            ("http://discovered", None),
            ("http://explicit", "secret"),
        ]


class TestPairPrompt:
    def test_prompt_requires_url(self) -> None:
        result = _runner.invoke(
            cli_main, ["pair", "prompt", "--session", "s_ab12cd"]
        )
        assert result.exit_code != 0

    def test_prompt_requires_session(self) -> None:
        result = _runner.invoke(
            cli_main, ["pair", "prompt", "--url", TEST_URL]
        )
        assert result.exit_code != 0
        assert "--session" in result.output

    def test_prompt_outputs_cli_bootstrap(self) -> None:
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "prompt",
                "--url",
                TEST_URL,
                "--session",
                "s_ab12cd",
                "--file",
                "notebooks/example.py",
            ],
        )
        assert result.exit_code == 0
        assert result.output == snapshot(f"""\
Pair with the live marimo notebook at this target:
  Server: {TEST_URL}
  Session: s_ab12cd
  Notebook: notebooks/example.py

Start with: uvx marimo@latest pair --help

Once you are connected, send a fun toast (mo.status.toast(...)) to the user inside marimo letting them know you're ready to pair.
""")

    def test_prompt_without_file_omits_notebook(self) -> None:
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "prompt",
                "--url",
                TEST_URL,
                "--session",
                "s_ab12cd",
            ],
        )
        assert result.exit_code == 0
        assert "Notebook:" not in result.output

    def test_prompt_can_use_current_uv_project(self) -> None:
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "prompt",
                "--url",
                TEST_URL,
                "--session",
                "s_ab12cd",
                "--uv-project",
            ],
        )

        assert result.exit_code == 0
        assert "Start with: uv run marimo pair --help" in result.output

    def test_prompt_skill_missing(self) -> None:
        with patch.object(AgentConfig, "has_skill", return_value=False):
            for flag in ("--claude", "--codex", "--opencode"):
                result = _runner.invoke(
                    cli_main,
                    [
                        "pair",
                        "prompt",
                        "--url",
                        TEST_URL,
                        "--session",
                        "s_ab12cd",
                        flag,
                    ],
                )
                assert result.exit_code == 0, flag
                assert "could not be found" in result.output, flag

    def test_prompt_skill_installed(self) -> None:
        with patch.object(AgentConfig, "has_skill", return_value=True):
            for flag in ("--claude", "--codex", "--opencode"):
                result = _runner.invoke(
                    cli_main,
                    [
                        "pair",
                        "prompt",
                        "--url",
                        TEST_URL,
                        "--session",
                        "s_ab12cd",
                        flag,
                    ],
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
                [
                    "pair",
                    "prompt",
                    "--url",
                    TEST_URL,
                    "--session",
                    "s_ab12cd",
                    "--with-token",
                ],
                input="my-secret-token\n",
            )
        assert result.exit_code == 0
        assert TEST_URL in result.output
        assert "Token file:" in result.output
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
                    "--session",
                    "s_ab12cd",
                    "--file",
                    "notebooks/my notebook.py",
                    "--with-token",
                ],
                input="my-secret-token\n",
            )
        assert result.exit_code == 0
        assert "Notebook: notebooks/my notebook.py" in result.output
        assert "Token file:" in result.output
        assert "my-secret-token" not in result.output

    def test_with_token_still_requires_url(self) -> None:
        result = _runner.invoke(
            cli_main,
            ["pair", "prompt", "--session", "s_ab12cd", "--with-token"],
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
                    "--session",
                    "s_ab12cd",
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
                    "--session",
                    "s_ab12cd",
                    "--claude",
                    "--with-token",
                ],
                input="secret\n",
            )
        assert result.exit_code == 0
        assert "could not be found" in result.output

    def test_without_token_no_token_hint(self) -> None:
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "prompt",
                "--url",
                TEST_URL,
                "--session",
                "s_ab12cd",
            ],
        )
        assert result.exit_code == 0
        assert "Token file:" not in result.output


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
