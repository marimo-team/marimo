# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import hashlib
import json
import re
import shlex
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from inline_snapshot import snapshot

from marimo._cli.cli import main as cli_main
from marimo._cli.pair import commands
from marimo._cli.pair.client import (
    AmbiguousSessionError,
    ExecutionResult,
    NoSessionError,
    PairError,
    PairInputError,
    StaleSessionError,
)
from marimo._cli.pair.commands import (
    AgentConfig,
    _codex_repository_skill_dirs,
    _codex_skill_dirs,
    _opencode_skill_dirs,
    _plugin_skill_dirs,
    pair_agents,
)

_runner = CliRunner()

TEST_URL = "https://localhost:8000?auth=tok123"


@pytest.fixture(autouse=True)
def _isolate_pair_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MARIMO_PAIR_NEXT", raising=False)


class TestPairGroup:
    def test_pair_help(self) -> None:
        result = _runner.invoke(cli_main, ["pair", "--help"])

        assert result.exit_code == 0
        assert "ctx.packages.add" in result.output
        assert result.output == snapshot("""\
Usage: main pair [OPTIONS] COMMAND [ARGS]...

  Pair with a live marimo notebook.

  Workflow:
    If you do not have the server URL or notebook file:
      marimo pair notebook list
    marimo pair execute --url <URL> --file <FILE> --code-file - <<'PY'
    import marimo._code_mode as cm
    async with cm.get_context() as ctx:
        ctx.packages.add("pandas")
        cid = ctx.create_cell("import pandas as pd")
        ctx.run_cell(cid)
    PY
    marimo pair execute --url <URL> --file <FILE> --code-file - <<'PY'
    import marimo._code_mode as cm
    async with cm.get_context() as ctx:
        cell = ctx.cells["<CELL_ID>"]
        print(cell.status, cell.errors, [o.data for o in cell.console_outputs])
    PY

  Target selection:
    If the notebook file is known, use --file <FILE> without --session.
    This resolves the notebook's current session after a page reload.
    If no file is known, use the supplied --session <SESSION>.
    If --file matches multiple sessions, use the supplied session for the intended notebook.
    If the intended session is unclear, run marimo pair notebook list again.
    Session IDs change when the page reloads. If execute reports a stale
    session, run marimo pair notebook list again.
    If both options are supplied, --session takes precedence over --file.
    Do not switch sessions after authentication or connection errors,
    or when execution is unconfirmed.

  Rules:
    Cells are the unit of work. The scratchpad is temporary; only code mode edits persist.
    Cells do not run on creation. Call run_cell after create_cell or edit_cell.
    Use async with. Do not await ctx methods.
    Install packages with ctx.packages.add, not uv add or pip. Installs change
    the project; confirm when the user did not ask.
    If an empty cell exists, edit_cell it instead of creating one.
    delete_cell drops the cell's variables. Ask before deleting.

  Code-mode API:
    Prefer marimo._code_mode to inspect, create, edit, run, and delete notebook cells.
    ctx.cells                 # each has .id .code .status .errors .console_outputs
    ctx.create_cell(code)     # returns the new cell id
    ctx.edit_cell(cid, code)
    ctx.run_cell(cid)
    ctx.delete_cell(cid)
    ctx.packages.add("pandas>=2")  # queued, installs on exit
    If a cm call fails, run help(cm):
      marimo pair execute --url <URL> --file <FILE> -c 'import marimo._code_mode as cm; help(cm)'

Options:
  -h, --help  Show this message and exit.

Commands:
  docs      Read notebook guidance on demand.
  execute   Run Python in a live notebook session.
  notebook  Find active notebooks and their sessions.
  prompt    Generate a prompt for pair programming on...
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
  --session ID       Current session ID. Resolved from --file when omitted.
  --file PATH        Notebook path or file key. Used to resolve --session when
                     omitted.
  --token-file PATH  Read the server token from a local file. Otherwise use
                     MARIMO_TOKEN, if set.
  -c TEXT            Inline Python.
  --code-file PATH   Read Python from a UTF-8 file, or from stdin when PATH is
                     '-'. Supply exactly one input option.
  --stream           Write stdout and stderr as they arrive. Default: print one
                     JSON result.
  -h, --help         Show this message and exit.
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
            return ExecutionResult(
                success=True, output=None, stdout="", stderr=""
            )

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

    def test_execute_reads_code_from_stdin(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[dict[str, Any]] = []

        def fake_execute(**kwargs: Any) -> ExecutionResult:
            calls.append(kwargs)
            return ExecutionResult(
                success=True, output=None, stdout="", stderr=""
            )

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
                "-",
            ],
            input='x = 1\nprint("Hi")\n',
        )

        assert result.exit_code == 0
        assert calls[0]["code"] == 'x = 1\nprint("Hi")\n'

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
            return ExecutionResult(
                success=True,
                output={"mimetype": "text/plain", "data": "done"},
                stdout="",
                stderr="",
            )

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
        assert calls[0]["stream"] is False
        assert json.loads(result.output) == {
            "success": True,
            "output": {"mimetype": "text/plain", "data": "done"},
            "stdout": "",
            "stderr": "",
            "session": {"id": "s_ab12cd"},
        }

    def test_execute_failure_exits_one(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fail_execution(**kwargs: Any) -> ExecutionResult:
            del kwargs
            return ExecutionResult(
                success=False,
                output=None,
                stdout="",
                stderr="failed",
            )

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
        assert json.loads(result.output) == {
            "success": False,
            "output": None,
            "stdout": "",
            "stderr": "failed",
            "session": {"id": "s_ab12cd"},
        }

    @pytest.mark.parametrize(
        ("stderr", "expected"),
        [
            (
                (
                    "RuntimeError: asyncio.run() cannot be called from a "
                    "running event loop"
                ),
                "Write the block at top level",
            ),
            (
                "KeyError: \"Cell 'KBiG' not found. Available cell IDs: [Hbol]\"",
                "cell = ctx.cells['KBiG']",
            ),
            (
                "AttributeError: '_CellsView' object has no attribute 'get'",
                "help(cm)",
            ),
        ],
    )
    def test_execute_kernel_failure_adds_next(
        self, monkeypatch: pytest.MonkeyPatch, stderr: str, expected: str
    ) -> None:
        def fail_execution(**kwargs: Any) -> ExecutionResult:
            del kwargs
            return ExecutionResult(
                success=False, output=None, stdout="", stderr=stderr
            )

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
                "x",
            ],
        )

        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["success"] is False
        assert payload["stderr"] == stderr
        assert expected in payload["next"]
        assert (
            "--session s_ab12cd" in payload["next"]
            or "top level" in (payload["next"])
        )

    def test_execute_next_quotes_shell_arguments(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fail_execution(**kwargs: Any) -> ExecutionResult:
            del kwargs
            return ExecutionResult(
                success=False,
                output=None,
                stdout="",
                stderr='KeyError: "Cell \'a"b\' not found"',
            )

        monkeypatch.setattr(commands, "execute_code", fail_execution)
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "execute",
                "--url",
                "http://one/a b",
                "--session",
                "s'1",
                "-c",
                "x",
            ],
        )

        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert "--url 'http://one/a b'" in payload["next"]
        assert "--session 's'\"'\"'1'" in payload["next"]
        assert "ctx.cells['a\"b']" in payload["next"]

    def test_execute_stream_failure_prints_next_lines(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fail_execute(**kwargs: Any) -> ExecutionResult:
            del kwargs
            raise StaleSessionError("Invalid session id: s_old")

        monkeypatch.setattr(commands, "execute_code", fail_execute)
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "execute",
                "--url",
                "http://one",
                "--session",
                "s_old",
                "--stream",
                "-c",
                "print(1)",
            ],
        )

        assert result.exit_code == 2
        assert result.stdout == ""
        assert result.stderr == (
            "error: The session is stale.\n"
            "  next: Sessions change when the page reloads. List them again:\n"
            "  marimo pair notebook list --url http://one\n"
        )

    def test_execute_auth_failure_has_token_next(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fail_execute(**kwargs: Any) -> ExecutionResult:
            del kwargs
            raise PairError("Authentication failed.")

        monkeypatch.setattr(commands, "execute_code", fail_execute)
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "execute",
                "--url",
                "http://one",
                "--session",
                "s",
                "-c",
                "1",
            ],
        )

        assert result.exit_code == 2
        payload = json.loads(result.output)
        assert payload["error"] == "Authentication failed."
        assert "MARIMO_TOKEN" in payload["next"]
        assert "Never print the token" in payload["next"]

    def test_execute_invalid_url_has_list_next(self) -> None:
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "execute",
                "--url",
                "ftp://x",
                "--session",
                "s",
                "-c",
                "1",
            ],
        )

        assert result.exit_code == 2
        payload = json.loads(result.output)
        assert payload["error"] == "The server URL must use http or https."
        assert payload["next"].endswith("marimo pair notebook list")

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

        assert result.exit_code == 2
        assert json.loads(result.output) == {
            "success": False,
            "error": "Could not execute code.",
            "output": None,
            "stdout": None,
            "stderr": None,
            "session": {"id": "s_ab12cd"},
        }

    def test_execute_reports_internal_resolution_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fail_execute(**kwargs: Any) -> ExecutionResult:
            del kwargs
            raise PairError("Internal: should not happen after resolution.")

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

        assert result.exit_code == 2
        payload = json.loads(result.output)
        assert payload["success"] is False
        assert (
            payload["error"] == "Internal: should not happen after resolution."
        )
        assert "next" not in payload

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
            return ExecutionResult(
                success=True, output=None, stdout="", stderr=""
            )

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
                "--stream",
                "-c",
                "print(1)",
            ],
        )

        assert result.exit_code == 0
        assert token_calls == [token_file]
        assert execute_calls[0]["token"] == "secret"
        assert execute_calls[0]["stream"] is True
        assert result.output == ""

    def test_execute_resolves_one_session_from_file(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        resolve_calls: list[dict[str, Any]] = []
        execute_calls: list[dict[str, Any]] = []

        def fake_resolve(**kwargs: Any) -> str:
            resolve_calls.append(kwargs)
            return "s_one"

        def fake_execute(**kwargs: Any) -> ExecutionResult:
            execute_calls.append(kwargs)
            return ExecutionResult(
                success=True, output=None, stdout="", stderr=""
            )

        monkeypatch.setattr(commands, "resolve_session", fake_resolve)
        monkeypatch.setattr(commands, "execute_code", fake_execute)
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "execute",
                "--url",
                "http://one",
                "--file",
                "analysis.py",
                "-c",
                "print(1)",
            ],
        )

        assert result.exit_code == 0
        assert resolve_calls == [
            {"url": "http://one", "token": None, "file": "analysis.py"}
        ]
        assert execute_calls[0]["session_id"] == "s_one"

    def test_execute_no_match_exits_two_with_list_next(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_resolve(**kwargs: Any) -> str:
            del kwargs
            raise NoSessionError(
                "No running session for notebook 'gone.py' on http://one.",
                url="http://user:password@one?access_token=secret",
            )

        monkeypatch.setattr(commands, "resolve_session", fake_resolve)
        monkeypatch.setattr(
            commands,
            "execute_code",
            lambda **_kwargs: pytest.fail("execute must not run"),
        )
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "execute",
                "--url",
                "http://one",
                "--file",
                "gone.py",
                "-c",
                "print(1)",
            ],
        )

        assert result.exit_code == 2
        payload = json.loads(result.output)
        assert payload["success"] is False
        assert "No running session for notebook 'gone.py'" in payload["error"]
        assert payload["next"].endswith(
            "marimo pair notebook list --url http://one"
        )
        assert payload["session"] == {"id": None}
        assert "password" not in result.output
        assert "secret" not in result.output

    def test_execute_two_matches_exits_two_with_candidates(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_resolve(**kwargs: Any) -> str:
            del kwargs
            raise AmbiguousSessionError(
                "Notebook 'analysis.py' has 2 running sessions on http://one.",
                url="http://user:password@one?access_token=secret",
                candidates=("s_a", "s_b"),
            )

        monkeypatch.setattr(commands, "resolve_session", fake_resolve)
        monkeypatch.setattr(
            commands,
            "execute_code",
            lambda **_kwargs: pytest.fail("execute must not run"),
        )
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "execute",
                "--url",
                "http://one",
                "--file",
                "analysis.py",
                "-c",
                "print(1)",
            ],
        )

        assert result.exit_code == 2
        payload = json.loads(result.output)
        assert "has 2 running sessions" in payload["error"]
        assert (
            "s_a: marimo pair execute --url http://one --session s_a"
            in (payload["next"])
        )
        assert (
            "s_b: marimo pair execute --url http://one --session s_b"
            in (payload["next"])
        )
        assert "password" not in result.output
        assert "secret" not in result.output

    def test_execute_session_skips_resolve(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        execute_calls: list[dict[str, Any]] = []

        def fake_execute(**kwargs: Any) -> ExecutionResult:
            execute_calls.append(kwargs)
            return ExecutionResult(
                success=True, output=None, stdout="", stderr=""
            )

        monkeypatch.setattr(
            commands,
            "resolve_session",
            lambda **_kwargs: pytest.fail("resolve must not run"),
        )
        monkeypatch.setattr(commands, "execute_code", fake_execute)
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "execute",
                "--url",
                "http://user:password@one?access_token=secret",
                "--session",
                "s_given",
                "-c",
                "print(1)",
            ],
        )

        assert result.exit_code == 0
        assert execute_calls[0]["session_id"] == "s_given"

    def test_execute_stale_session_maps_to_targeted_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fail_execute(**kwargs: Any) -> ExecutionResult:
            del kwargs
            raise StaleSessionError("Invalid session id: s_old")

        monkeypatch.setattr(commands, "execute_code", fail_execute)
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "execute",
                "--url",
                "http://user:password@one?access_token=secret",
                "--session",
                "s_old",
                "-c",
                "print(1)",
            ],
        )

        assert result.exit_code == 2
        payload = json.loads(result.output)
        assert payload["error"] == "The session is stale."
        assert payload["next"].endswith(
            "marimo pair notebook list --url http://one"
        )
        assert "password" not in result.output
        assert "secret" not in result.output


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
    def test_notebook_help(self) -> None:
        result = _runner.invoke(cli_main, ["pair", "notebook", "--help"])

        assert result.exit_code == 0
        assert result.output == snapshot("""\
Usage: main pair notebook [OPTIONS] COMMAND [ARGS]...

  Find active notebooks and their sessions.

Options:
  -h, --help  Show this message and exit.

Commands:
  list  List active notebooks and their session IDs.
""")

    def test_notebook_list_help(self) -> None:
        result = _runner.invoke(
            cli_main, ["pair", "notebook", "list", "--help"]
        )

        assert result.exit_code == 0
        assert result.output == snapshot("""\
Usage: main pair notebook list [OPTIONS]

  List active notebooks and their session IDs.

Options:
  --url URL          Server URL. Repeat to list more than one server.
  --token-file PATH  Read the server token from a local file. Otherwise use
                     MARIMO_TOKEN, if set.
  -h, --help         Show this message and exit.
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
            ["pair", "notebook", "list", "--url", "http://one"],
        )

        assert result.exit_code == 0
        assert json.loads(result.output) == {
            "notebooks": [
                {
                    "server": {"url": "http://one"},
                    "name": "analysis.py",
                    "path": "/work/analysis.py",
                    "sessions": [
                        {"id": "session-1"},
                        {"id": "session-2"},
                    ],
                }
            ],
            "warnings": [],
        }

    def test_list_rejects_missing_token_file(self, tmp_path: Path) -> None:
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "notebook",
                "list",
                "--url",
                "http://one",
                "--token-file",
                str(tmp_path / "missing-token"),
            ],
        )

        assert result.exit_code == 2
        assert "error: could not read the token file" in result.stderr
        assert "Traceback" not in result.stderr

    def test_list_rejects_empty_token_file(self, tmp_path: Path) -> None:
        token_file = tmp_path / "token"
        token_file.write_text("\n", encoding="utf-8")

        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "notebook",
                "list",
                "--url",
                "http://one",
                "--token-file",
                str(token_file),
            ],
        )

        assert result.exit_code == 2
        assert "error: the token file is empty" in result.stderr
        assert "Traceback" not in result.stderr

    def test_list_rejects_invalid_explicit_url(self) -> None:
        result = _runner.invoke(
            cli_main,
            ["pair", "notebook", "list", "--url", "ftp://invalid"],
        )

        assert result.exit_code == 2
        assert "error: the server URL must use http or https" in (
            result.stderr
        )

    def test_list_keeps_same_basename_on_two_urls_separate(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("MARIMO_TOKEN", raising=False)

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
                "notebook",
                "list",
                "--url",
                "http://two",
                "--url",
                "http://one",
            ],
        )

        assert result.exit_code == 0
        notebooks = json.loads(result.output)["notebooks"]
        assert [notebook["server"]["url"] for notebook in notebooks] == [
            "http://one",
            "http://two",
        ]
        assert len(notebooks) == 2

    def test_list_sorts_same_basename_by_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            commands,
            "list_sessions",
            lambda **_kwargs: {
                "session-b": {
                    "filename": "analysis.py",
                    "path": "/work/b/analysis.py",
                },
                "session-a": {
                    "filename": "analysis.py",
                    "path": "/work/a/analysis.py",
                },
            },
        )

        result = _runner.invoke(
            cli_main,
            ["pair", "notebook", "list", "--url", "http://one"],
        )

        assert result.exit_code == 0
        notebooks = json.loads(result.output)["notebooks"]
        assert [notebook["path"] for notebook in notebooks] == [
            "/work/a/analysis.py",
            "/work/b/analysis.py",
        ]

    def test_list_preserves_results_when_one_url_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("MARIMO_TOKEN", raising=False)

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
                "notebook",
                "list",
                "--url",
                "http://bad",
                "--url",
                "http://good",
            ],
        )

        assert result.exit_code == 0
        assert json.loads(result.output) == {
            "notebooks": [
                {
                    "server": {"url": "http://good"},
                    "name": "analysis.py",
                    "path": "/work/analysis.py",
                    "sessions": [{"id": "session-1"}],
                }
            ],
            "warnings": [
                "Server http://bad could not be read: Could not connect to http://bad."
            ],
        }

    def test_list_redacts_displayed_server_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        raw_url = "http://user:password@one/base?access_token=secret#fragment"
        calls: list[str] = []

        def fake_list_sessions(
            *, url: str, token: str | None
        ) -> dict[str, dict[str, str | None]]:
            assert token is None
            calls.append(url)
            return {
                "session-1": {
                    "filename": "analysis.py",
                    "path": "/work/analysis.py",
                }
            }

        monkeypatch.setattr(commands, "list_sessions", fake_list_sessions)
        result = _runner.invoke(
            cli_main,
            ["pair", "notebook", "list", "--url", raw_url],
        )

        assert result.exit_code == 0
        assert calls == [raw_url]
        assert json.loads(result.output)["notebooks"][0]["server"] == {
            "url": "http://one/base"
        }
        assert "password" not in result.output
        assert "secret" not in result.output

    def test_list_warns_for_invalid_discovered_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fail_list_sessions(**_kwargs: Any) -> None:
            raise PairInputError("The server URL must use http or https.")

        monkeypatch.setattr(commands, "registry_urls", lambda: ["ftp://bad"])
        monkeypatch.setattr(commands, "list_sessions", fail_list_sessions)

        result = _runner.invoke(cli_main, ["pair", "notebook", "list"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["notebooks"] == []
        assert payload["warnings"] == [
            (
                "Server ftp://bad could not be read: "
                "The server URL must use http or https."
            )
        ]
        assert payload["next"].startswith("No sessions found.")

    def test_list_empty_registry_succeeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(commands, "registry_urls", list)
        monkeypatch.setattr(
            commands,
            "list_sessions",
            lambda **_kwargs: pytest.fail("No server should be queried"),
        )

        result = _runner.invoke(cli_main, ["pair", "notebook", "list"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["notebooks"] == []
        assert payload["warnings"] == []
        assert payload["next"].startswith("No sessions found.")

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
                "notebook",
                "list",
                "--token-file",
                str(token_file),
            ],
        )
        explicit = _runner.invoke(
            cli_main,
            [
                "pair",
                "notebook",
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
        result = _runner.invoke(cli_main, ["pair", "prompt"])
        assert result.exit_code != 0

    @pytest.mark.parametrize("flag", [None, "0", "false", ""])
    def test_prompt_outputs_url(self, flag: str | None) -> None:
        result = _runner.invoke(
            cli_main,
            ["pair", "prompt", "--url", TEST_URL],
            env={"MARIMO_PAIR_NEXT": flag},
        )
        assert result.exit_code == 0
        assert result.output == snapshot("""\
Use the /marimo-pair skill to pair-program on a running marimo notebook.

Connect to the notebook at: https://localhost:8000?auth=tok123

Use `execute-code.sh --url 'https://localhost:8000?auth=tok123'` from the marimo-pair skill to execute code in the notebook.

Once you are connected, send a fun toast (mo.status.toast(...)) to the user inside marimo letting them know you're ready to pair.
""")

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

    def test_prompt_with_session(self) -> None:
        result = _runner.invoke(
            cli_main,
            ["pair", "prompt", "--url", TEST_URL, "--session", "s_ab12cd"],
        )
        assert result.exit_code == 0
        assert result.output == snapshot("""\
Use the /marimo-pair skill to pair-program on a running marimo notebook.

Connect to the notebook at: https://localhost:8000?auth=tok123

Use `execute-code.sh --url 'https://localhost:8000?auth=tok123' --session s_ab12cd` from the marimo-pair skill to execute code in the notebook.

Once you are connected, send a fun toast (mo.status.toast(...)) to the user inside marimo letting them know you're ready to pair.
""")

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

    def test_prompt_handles_skill_permission_error(self) -> None:
        with patch.object(Path, "exists", side_effect=PermissionError):
            result = _runner.invoke(
                cli_main,
                ["pair", "prompt", "--url", TEST_URL, "--codex"],
            )

        assert result.exit_code == 0
        assert "could not be found" in result.output
        assert TEST_URL in result.output

    def test_prompt_finds_codex_user_skill(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        cwd = tmp_path / "project"
        skill = home / ".agents" / "skills" / "marimo-pair" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("test")
        cwd.mkdir()

        with (
            patch.object(Path, "home", return_value=home),
            patch.object(Path, "cwd", return_value=cwd),
        ):
            result = _runner.invoke(
                cli_main,
                ["pair", "prompt", "--url", TEST_URL, "--codex"],
            )

        assert result.exit_code == 0
        assert "could not be found" not in result.output


class TestPairPromptPreview:
    def test_with_token_uses_private_file(self, tmp_path: Path) -> None:
        token_dir = tmp_path / "tokens ' {command}"
        with patch.object(commands, "_token_dir", return_value=token_dir):
            result = _runner.invoke(
                cli_main,
                [
                    "pair",
                    "prompt",
                    "--url",
                    "http://localhost:2718",
                    "--session",
                    "s_ab12cd",
                    "--with-token",
                ],
                env={"MARIMO_PAIR_NEXT": "1"},
                input="my-secret-token\n",
            )

        assert result.exit_code == 0
        assert "Auth token:" in result.stderr
        assert "my-secret-token" not in result.output
        token_file = next(token_dir.iterdir())
        assert token_file.read_text() == "my-secret-token"
        if sys.platform != "win32":
            assert token_file.stat().st_mode & 0o777 == 0o600

        token_command = re.search(r"`(--token-file .+)`", result.stdout)
        assert token_command is not None
        assert shlex.split(token_command.group(1)) == [
            "--token-file",
            str(token_file),
        ]
        assert result.stdout.replace(
            shlex.quote(str(token_file)), "<TOKEN_FILE>"
        ) == snapshot("""\
Pair with me on this running marimo notebook.

URL: http://localhost:2718
Session: s_ab12cd

Run `uv run marimo pair --help` first.
Use `uv run marimo` for all marimo commands.

Once connected, send a fun toast using `mo.status.toast(...)` (`import marimo as mo`).

For authenticated Pair commands, pass `--token-file <TOKEN_FILE>`.
""")

    @pytest.mark.parametrize("agent", ["--claude", "--codex", "--opencode"])
    def test_prompt_needs_no_skill(
        self,
        agent: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        result = _runner.invoke(
            cli_main,
            ["pair", "prompt", "--url", "http://localhost:2718", agent],
            env={"MARIMO_PAIR_NEXT": "1"},
        )

        assert result.exit_code == 0
        assert result.output == snapshot("""\
Pair with me on this running marimo notebook.

URL: http://localhost:2718

Run `uv run marimo pair --help` first.
Use `uv run marimo` for all marimo commands.

Once connected, send a fun toast using `mo.status.toast(...)` (`import marimo as mo`).
""")

    def test_prompt_preserves_connection_details(self) -> None:
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "prompt",
                "--url",
                "http://localhost:2718/{session}",
                "--file",
                "{command}/it's notebook.py",
                "--session",
                "{file}",
            ],
            env={"MARIMO_PAIR_NEXT": "1"},
        )

        assert result.exit_code == 0
        assert result.output == snapshot("""\
Pair with me on this running marimo notebook.

URL: http://localhost:2718/{session}
File: {command}/it's notebook.py
Session: {file}

Run `uv run marimo pair --help` first.
Use `uv run marimo` for all marimo commands.

Once connected, send a fun toast using `mo.status.toast(...)` (`import marimo as mo`).
""")

    @pytest.mark.parametrize("flag", ["1", "true", " TRUE "])
    def test_prompt_uses_cli(self, flag: str) -> None:
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "prompt",
                "--url",
                "http://localhost:2718",
                "--file",
                "notebook.py",
            ],
            env={"MARIMO_PAIR_NEXT": flag},
        )

        assert result.exit_code == 0
        assert result.output == snapshot("""\
Pair with me on this running marimo notebook.

URL: http://localhost:2718
File: notebook.py

Run `uv run marimo pair --help` first.
Use `uv run marimo` for all marimo commands.

Once connected, send a fun toast using `mo.status.toast(...)` (`import marimo as mo`).
""")


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


class TestCodexSkillDirs:
    def test_codex_skill_dirs_include_supported_global_locations(
        self, tmp_path: Path
    ) -> None:
        home = tmp_path / "home"
        cwd = tmp_path / "project"
        cwd.mkdir()

        with (
            patch.object(Path, "home", return_value=home),
            patch.object(Path, "cwd", return_value=cwd),
        ):
            skill_dirs = _codex_skill_dirs()

        assert home / ".agents" / "skills" in skill_dirs
        assert Path("/etc/codex/skills") in skill_dirs

    def test_codex_repository_skill_dirs_stop_at_repository_root(
        self, tmp_path: Path
    ) -> None:
        repository = tmp_path / "repository"
        cwd = repository / "packages" / "notebooks"
        cwd.mkdir(parents=True)
        (repository / ".git").mkdir()

        assert _codex_repository_skill_dirs(cwd) == [
            cwd / ".agents" / "skills",
            cwd.parent / ".agents" / "skills",
            repository / ".agents" / "skills",
        ]

    def test_codex_repository_skill_dirs_only_check_cwd_without_repository(
        self, tmp_path: Path
    ) -> None:
        cwd = tmp_path / "notebooks"
        cwd.mkdir()

        assert _codex_repository_skill_dirs(cwd) == [
            cwd / ".agents" / "skills"
        ]

    def test_codex_repository_skill_dirs_stop_on_permission_error(
        self, tmp_path: Path
    ) -> None:
        cwd = tmp_path / "repository" / "notebooks"
        cwd.mkdir(parents=True)

        with patch.object(Path, "exists", side_effect=PermissionError):
            assert _codex_repository_skill_dirs(cwd) == [
                cwd / ".agents" / "skills"
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

    def test_has_skill_skips_permission_error(self, tmp_path: Path) -> None:
        agent = AgentConfig(
            name="test",
            skill_dirs=[tmp_path / "inaccessible", tmp_path / "installed"],
        )

        with patch.object(Path, "exists", side_effect=[PermissionError, True]):
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
