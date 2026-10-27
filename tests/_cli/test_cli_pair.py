# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import urlsplit

import pytest
from click.testing import CliRunner
from inline_snapshot import snapshot

from marimo._cli.cli import main as cli_main
from marimo._cli.pair import client, commands
from marimo._cli.pair.client import (
    AmbiguousNotebookError,
    ExecutionResult,
    HostEndpoint,
    NoNotebookError,
    NotebookUnsupportedError,
    PairError,
    PairInputError,
    SandboxGoneError,
    StaleNotebookError,
)

_runner = CliRunner()

TEST_URL = "https://localhost:8000?auth=tok123"


@pytest.fixture(autouse=True)
def _isolate_pair_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        commands,
        "resolve_host",
        lambda url: HostEndpoint(
            urlsplit(url)
            ._replace(path=urlsplit(url).path.rstrip("/") + "/api/marimo/v1")
            .geturl(),
            "host-secret",
        ),
    )
    monkeypatch.setattr(
        "marimo._cli.pair.prompts.is_editable", lambda _: False
    )


class TestPairGroup:
    def test_pair_help(self) -> None:
        result = _runner.invoke(cli_main, ["pair", "--help"])

        assert result.exit_code == 0
        assert "ctx.packages.add" in result.output
        assert result.output == snapshot("""\
Usage: main pair [OPTIONS] COMMAND [ARGS]...

  Pair with a live marimo notebook.

  Authentication:
    Notebook discovery uses the editor token. Pass --token-file <PATH> to
    notebook list or execute without --notebook when a token is required.
    Host commands read their token from the private local host record.

  Workflow:
    If no server is running, start one in the background:
      marimo edit <notebook.py> --no-token
    If you do not have the server URL or notebook ID:
      marimo pair notebook list
    Connect to the notebook before waiting for work.
    Run marimo pair connect --help to check supported harnesses.
    If your harness is supported, run:
      marimo pair connect --url <URL> --notebook <NOTEBOOK>
    Otherwise, work with the notebook using pair execute:
    marimo pair execute --url <URL> --session <SESSION> --code-file - <<'PY'
    import marimo._code_mode as cm
    async with cm.get_context() as ctx:
        ctx.packages.add("pandas")
        cid = ctx.create_cell("import pandas as pd")
        ctx.run_cell(cid)
    PY
    marimo pair execute --url <URL> --notebook <NOTEBOOK> --code-file - <<'PY'
    import marimo._code_mode as cm
    async with cm.get_context() as ctx:
        cell = ctx.cells["<CELL_ID>"]
        print(cell.status, cell.errors, [o.data for o in cell.console_outputs])
    PY

  Target selection:
    --session takes a stable session_id for editor execution.
    --notebook takes notebook_id for host execution. It survives
    kernel restarts and page reloads. Only saved notebooks inside the project
    root have a host notebook ID. Host commands need a local edit server.
    If several notebooks are open, ask the user which one.
    Do not switch notebooks after authentication or connection errors,
    or when execution is unconfirmed.

  Agent messages (preview):
    Inside Codex, Claude Code, or OpenCode, run:
      marimo pair connect --url <URL> --notebook <NOTEBOOK>.
    Codex must use its shared daemon and support codex queue.
    Claude Code requires its native inbox on macOS or Linux.
    OpenCode 2.x requires its registered local service.
    Inbound message settings still apply; messages can be held or refused.
    Notebook agent messages arrive here as messages from marimo.
    Oversized agent messages include a complete JSON file on this machine.
    Files remain after detach. Cleanup removes owned files older than 24 hours.
    Use pair detach --notebook <NOTEBOOK> to stop the inbox.

  Rules:
    Cells are the unit of work. The scratchpad is temporary; only code mode edits persist.
    Cells do not run on creation. Call run_cell after create_cell or edit_cell.
    Use async with. Do not await ctx methods.
    Install packages with ctx.packages.add, not uv add or pip. Installs change
    the project; confirm when the user did not ask.
    If an empty cell exists, edit_cell it instead of creating one.
    delete_cell drops the cell's variables. Ask before deleting.
    Do not edit the notebook file directly. Code mode is the only write path.

  Code-mode API:
    Prefer marimo._code_mode to inspect, create, edit, run, and delete notebook cells.
    ctx.cells                 # each has .id .code .status .errors .console_outputs
    ctx.create_cell(code)     # returns the new cell id
    ctx.edit_cell(cid, code)
    ctx.run_cell(cid)
    ctx.delete_cell(cid)
    ctx.packages.add("pandas>=2")  # queued, installs on exit
    If a cm call fails, run help(cm):
      marimo pair execute --url <URL> --notebook <NOTEBOOK> -c 'import marimo._code_mode as cm; help(cm)'

Options:
  -h, --help  Show this message and exit.

Commands:
  connect   Connect this harness inbox to a live...
  detach    Stop the forwarder and detach its notebook...
  docs      Read notebook guidance on demand.
  execute   Run Python in a live notebook.
  notebook  Find active notebooks and their IDs.
  prompt    Generate a prompt for pair programming on...
""")

    def test_prompt_help(self) -> None:
        result = _runner.invoke(cli_main, ["pair", "prompt", "--help"])
        assert result.exit_code == 0
        assert "--url" in result.output
        assert "--session" in result.output
        assert "--claude" not in result.output
        assert "--file" not in result.output
        assert "--notebook" in result.output


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
  --notebook ID      Host notebook_id from marimo pair notebook list.
  --session TEXT     Stable Session ID from notebook list. Host execution is
                     preferred when available.
  --token-file PATH  Read the server token from a local file.
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
                "--notebook",
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
                "--notebook",
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
                "--notebook",
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
                "--notebook",
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
                "--notebook",
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
                "--notebook",
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
                "--notebook",
                "s_ab12cd",
                "-c",
                "print(1)",
            ],
        )

        assert result.exit_code == 0
        assert (
            calls[0]["url"]
            == "https://localhost:8000/api/marimo/v1?auth=tok123"
        )
        assert calls[0]["notebook_id"] == "s_ab12cd"
        assert calls[0]["code"] == "print(1)"
        assert calls[0]["token"] == "host-secret"
        assert calls[0]["stream"] is False
        assert json.loads(result.output) == {
            "success": True,
            "outcome": "succeeded",
            "output": {"mimetype": "text/plain", "data": "done"},
            "stdout": "",
            "stderr": "",
            "notebook": {"id": "s_ab12cd"},
        }

    def test_execute_failure_exits_one(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fail_execution(**kwargs: Any) -> ExecutionResult:
            del kwargs
            return ExecutionResult(
                success=False,
                outcome="failed",
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
                "--notebook",
                "s_ab12cd",
                "-c",
                "raise ValueError",
            ],
        )

        assert result.exit_code == 1
        assert json.loads(result.output) == {
            "success": False,
            "outcome": "failed",
            "output": None,
            "stdout": "",
            "stderr": "failed",
            "notebook": {"id": "s_ab12cd"},
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
                "--notebook",
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
            "--notebook s_ab12cd" in payload["next"]
            or "top level" in (payload["next"])
        )

    def test_execute_next_quotes_shell_arguments(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fail_execution(**kwargs: Any) -> ExecutionResult:
            del kwargs
            return ExecutionResult(
                success=False,
                outcome="failed",
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
                "--notebook",
                "s'1",
                "-c",
                "x",
            ],
        )

        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert "--url 'http://one/a b'" in payload["next"]
        assert "--notebook 's'\"'\"'1'" in payload["next"]
        assert "ctx.cells['a\"b']" in payload["next"]

    def test_execute_stream_failure_prints_next_lines(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fail_execute(**kwargs: Any) -> ExecutionResult:
            del kwargs
            raise StaleNotebookError("Invalid session id: s_old")

        monkeypatch.setattr(commands, "execute_code", fail_execute)
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "execute",
                "--url",
                "http://one",
                "--notebook",
                "s_old",
                "--stream",
                "-c",
                "print(1)",
            ],
        )

        assert result.exit_code == 2
        assert result.stdout == ""
        assert result.stderr == (
            "error: No notebook s_old on http://one. "
            "Run notebook list to find the current host notebook.\n"
            "  next: marimo pair notebook list --url http://one\n"
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
                "--notebook",
                "s",
                "-c",
                "1",
            ],
        )

        assert result.exit_code == 2
        payload = json.loads(result.output)
        assert payload["error"] == "Authentication failed."
        assert "host discovery" in payload["next"]

    def test_execute_invalid_url_has_list_next(self) -> None:
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "execute",
                "--url",
                "ftp://x",
                "--notebook",
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
                "--notebook",
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
            "notebook": {"id": "s_ab12cd"},
        }

    def test_execute_reports_server_without_stable_sessions(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fail_execute(**kwargs: Any) -> ExecutionResult:
            del kwargs
            raise NotebookUnsupportedError

        monkeypatch.setattr(commands, "execute_code", fail_execute)
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "execute",
                "--url",
                TEST_URL,
                "--notebook",
                "s_ab12cd",
                "-c",
                "print(1)",
            ],
        )

        assert result.exit_code == 2
        payload = json.loads(result.output)
        assert payload == {
            "success": False,
            "error": (
                "Server https://localhost:8000 runs a marimo version "
                "without notebook_id. Upgrade marimo on the server."
            ),
            "output": None,
            "stdout": None,
            "stderr": None,
            "notebook": {"id": "s_ab12cd"},
        }
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
                "--notebook",
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
                "--notebook",
                "s_ab12cd",
                "--token-file",
                str(token_file),
                "--stream",
                "-c",
                "print(1)",
            ],
        )

        assert result.exit_code == 0
        assert token_calls == []
        assert execute_calls[0]["token"] == "host-secret"
        assert execute_calls[0]["stream"] is True
        assert result.output == ""

    def test_execute_resolves_one_session_when_omitted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        resolve_calls: list[dict[str, Any]] = []
        execute_calls: list[dict[str, Any]] = []

        def fake_resolve(**kwargs: Any) -> tuple[str | None, str]:
            resolve_calls.append(kwargs)
            return "s_one", "sess-one"

        def fake_execute(**kwargs: Any) -> ExecutionResult:
            execute_calls.append(kwargs)
            return ExecutionResult(
                success=True, output=None, stdout="", stderr=""
            )

        monkeypatch.setattr(commands, "resolve_execution_target", fake_resolve)
        monkeypatch.setattr(commands, "execute_code", fake_execute)
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "execute",
                "--url",
                "http://one",
                "-c",
                "print(1)",
            ],
        )

        assert result.exit_code == 0
        assert resolve_calls == [
            {"url": "http://one", "token": None, "session_id": None}
        ]
        assert execute_calls[0]["notebook_id"] == "s_one"

    def test_execute_rejects_file_selector(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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
        assert "unexpected argument '--file'" in result.output

    def test_execute_no_match_exits_two_with_list_next(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_resolve(**kwargs: Any) -> str:
            del kwargs
            raise NoNotebookError(
                "No running session on http://one.",
                url="http://user:password@one?access_token=secret",
            )

        monkeypatch.setattr(commands, "resolve_execution_target", fake_resolve)
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
                "-c",
                "print(1)",
            ],
        )

        assert result.exit_code == 2
        payload = json.loads(result.output)
        assert payload["success"] is False
        assert payload["error"] == "No running session on http://one."
        assert payload["next"].endswith(
            "marimo pair notebook list --url http://one"
        )
        assert payload["notebook"] == {"id": None}
        assert "password" not in result.output
        assert "secret" not in result.output

    def test_execute_two_matches_exits_two_with_candidates(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_resolve(**kwargs: Any) -> str:
            del kwargs
            raise AmbiguousNotebookError(
                "Server http://one has 2 running sessions.",
                url="http://user:password@one?access_token=secret",
                candidates=("sess-a", "sess-b"),
            )

        monkeypatch.setattr(commands, "resolve_execution_target", fake_resolve)
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
                "-c",
                "print(1)",
            ],
        )

        assert result.exit_code == 2
        payload = json.loads(result.output)
        assert "has 2 running sessions" in payload["error"]
        assert (
            "sess-a: marimo pair execute --url http://one --session sess-a"
            in (payload["next"])
        )
        assert (
            "sess-b: marimo pair execute --url http://one --session sess-b"
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
            "resolve_execution_target",
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
                "--notebook",
                "s_given",
                "-c",
                "print(1)",
            ],
        )

        assert result.exit_code == 0
        assert execute_calls[0]["notebook_id"] == "s_given"

    def test_execute_stale_session_maps_to_targeted_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fail_execute(**kwargs: Any) -> ExecutionResult:
            del kwargs
            raise StaleNotebookError("Invalid stable session id: sess-old")

        monkeypatch.setattr(commands, "execute_code", fail_execute)
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "execute",
                "--url",
                "http://user:password@one?access_token=secret",
                "--notebook",
                "sess-old",
                "-c",
                "print(1)",
            ],
        )

        assert result.exit_code == 2
        payload = json.loads(result.output)
        assert payload["error"] == (
            "No notebook sess-old on http://one. "
            "Run notebook list to find the current host notebook."
        )
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

  Find active notebooks and their IDs.

Options:
  -h, --help  Show this message and exit.

Commands:
  list  List active notebooks and their host IDs.
""")

    def test_notebook_list_help(self) -> None:
        result = _runner.invoke(
            cli_main, ["pair", "notebook", "list", "--help"]
        )

        assert result.exit_code == 0
        assert result.output == snapshot("""\
Usage: main pair notebook list [OPTIONS]

  List active notebooks and their host IDs.

Options:
  --url URL          Server URL. Repeat to list more than one server.
  --token-file PATH  Read the server token from a local file.
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
                    "session_id": "sess-stable-2",
                    "filename": "analysis.py",
                    "path": "/work/analysis.py",
                    "notebook_id": "nb-analysis",
                },
                "session-1": {
                    "session_id": "sess-stable-1",
                    "filename": "analysis.py",
                    "path": "/work/analysis.py",
                    "notebook_id": "nb-analysis",
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
                    "notebook_id": "nb-analysis",
                    "sessions": [
                        {
                            "id": "session-1",
                            "session_id": "sess-stable-1",
                        },
                        {
                            "id": "session-2",
                            "session_id": "sess-stable-2",
                        },
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
                    "session_id": f"sess-{url[-1]}",
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
                    "session_id": "sess-b",
                    "filename": "analysis.py",
                    "path": "/work/b/analysis.py",
                },
                "session-a": {
                    "session_id": "sess-a",
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
                    "session_id": "sess-stable-1",
                    "filename": "analysis.py",
                    "path": "/work/analysis.py",
                    "notebook_id": "nb-analysis",
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
                    "notebook_id": "nb-analysis",
                    "sessions": [
                        {
                            "id": "session-1",
                            "session_id": "sess-stable-1",
                        }
                    ],
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
                    "session_id": "sess-stable-1",
                    "filename": "analysis.py",
                    "path": "/work/analysis.py",
                    "notebook_id": "nb-analysis",
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
        assert "marimo edit <notebook.py> --no-token" in payload["next"]

    def test_list_warns_when_server_has_no_stable_sessions(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fail_list_sessions(**_kwargs: Any) -> None:
            raise NotebookUnsupportedError

        monkeypatch.setattr(commands, "list_sessions", fail_list_sessions)

        result = _runner.invoke(
            cli_main,
            ["pair", "notebook", "list", "--url", "http://one"],
        )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["notebooks"] == []
        assert payload["warnings"] == [
            (
                "Server http://one runs a marimo version without notebook_id. "
                "Upgrade marimo on the server."
            )
        ]

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
        assert "marimo edit <notebook.py> --no-token" in payload["next"]

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
    @pytest.mark.parametrize(
        "selector", [[], ["--session", "sess-one"], ["--notebook", "nb-one"]]
    )
    def test_prompt_is_cli_without_flags(self, selector: list[str]) -> None:
        result = _runner.invoke(
            cli_main, ["pair", "prompt", "--url", TEST_URL, *selector]
        )
        assert result.exit_code == 0
        assert TEST_URL in result.output
        assert "pair --help" in result.output
        assert "skill" not in result.output
        if selector:
            assert selector[1] in result.output

    def test_prompt_rejects_ambiguous_target(self) -> None:
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "prompt",
                "--url",
                TEST_URL,
                "--session",
                "s",
                "--notebook",
                "n",
            ],
        )
        assert result.exit_code == 2

    def test_prompt_requires_url(self) -> None:
        assert _runner.invoke(cli_main, ["pair", "prompt"]).exit_code == 2

    def test_token_is_private_and_shell_quoted(self, tmp_path: Path) -> None:
        with patch.object(commands, "_token_dir", return_value=tmp_path):
            result = _runner.invoke(
                cli_main,
                ["pair", "prompt", "--url", TEST_URL, "--with-token"],
                input="private-token\n",
            )
        assert result.exit_code == 0
        assert "private-token" not in result.output
        token_file = next(tmp_path.iterdir())
        assert token_file.read_text() == "private-token"
        if sys.platform != "win32":
            assert token_file.stat().st_mode & 0o777 == 0o600
        token_option = re.search(r"`(--token-file .+)`", result.stdout)
        assert token_option is not None
        assert shlex.split(token_option.group(1)) == [
            "--token-file",
            str(token_file),
        ]

    def test_empty_token_preserves_existing_file(self, tmp_path: Path) -> None:
        token_file = tmp_path / "existing"
        token_file.write_text("previous")
        with patch.object(commands, "_token_dir", return_value=tmp_path):
            result = _runner.invoke(
                cli_main,
                ["pair", "prompt", "--url", TEST_URL, "--with-token"],
                input="\n",
            )
        assert result.exit_code == 0
        assert token_file.read_text() == "previous"
        assert "--token-file" not in result.stdout

    @pytest.mark.parametrize(
        ("editable", "command"),
        [(True, "uv run marimo"), (False, "uvx marimo@latest")],
    )
    def test_installation_command(
        self, monkeypatch: pytest.MonkeyPatch, editable: bool, command: str
    ) -> None:
        monkeypatch.setattr(
            "marimo._cli.pair.prompts.is_editable", lambda _: editable
        )
        result = _runner.invoke(
            cli_main, ["pair", "prompt", "--url", TEST_URL]
        )
        assert result.exit_code == 0
        assert f"{command} pair --help" in result.output


@pytest.mark.parametrize("agent", ["--claude", "--codex", "--opencode"])
def test_legacy_launcher_flag_still_generates_cli_prompt(agent: str) -> None:
    result = _runner.invoke(
        cli_main, ["pair", "prompt", "--url", TEST_URL, agent]
    )
    assert result.exit_code == 0
    assert "pair --help" in result.output
    assert "skill" not in result.output


class _FakeResponse:
    """Just enough of http.client.HTTPResponse for _raise_for_status."""

    def __init__(
        self, status: int, payload: dict[str, Any] | None = None
    ) -> None:
        self.status = status
        self._body = json.dumps(payload).encode() if payload else b""

    def read(self) -> bytes:
        return self._body

    def close(self) -> None:
        pass


def test_status_410_reports_a_gone_sandbox() -> None:
    """molab answers 410 when it deletes a notebook, filesystem included.

    That is not a bad URL or a bad token, and telling the user to check the URL
    sends them looking in the wrong place.
    """
    with pytest.raises(SandboxGoneError):
        client._raise_for_status(_FakeResponse(410))


def test_status_503_reports_a_restarting_sandbox() -> None:
    with pytest.raises(PairError) as raised:
        client._raise_for_status(_FakeResponse(503))
    assert "503" in str(raised.value)
