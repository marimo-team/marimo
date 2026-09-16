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
from marimo._cli.pair.client import (
    AmbiguousSessionError,
    ExecutionResult,
    NoSessionError,
    PairError,
    PairInputError,
    StaleSessionError,
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

  Workflow:
    If you do not have the server URL and session id:
      marimo pair notebook list
    marimo pair execute --url <URL> --session <SESSION> --code-file - <<'PY'
    import marimo._code_mode as cm
    async with cm.get_context() as ctx:
        cid = ctx.create_cell("x = 1")
        ctx.run_cell(cid)
    PY
    marimo pair execute --url <URL> --session <SESSION> --code-file - <<'PY'
    import marimo._code_mode as cm
    async with cm.get_context() as ctx:
        cell = ctx.cells["<CELL_ID>"]
        print(cell.status, cell.errors, [o.data for o in cell.console_outputs])
    PY

  Rules:
    Cells are the unit of work. The scratchpad is temporary; only cm edits persist.
    Cells do not run on creation. Call run_cell after create_cell or edit_cell.
    Use async with. Do not await ctx methods.
    Session IDs change when the page reloads. If execute reports a stale
    session, run notebook list again.

  Code-mode API (this marimo version):
    ctx.cells                 # each has .id .code .status .errors .console_outputs
    ctx.create_cell(code)     # returns the new cell id
    ctx.edit_cell(cid, code)
    ctx.run_cell(cid)
    ctx.delete_cell(cid)
    If a cm call fails, run help(cm):
      marimo pair execute --url <URL> --session <SESSION> -c 'import marimo._code_mode as cm; help(cm)'

Options:
  -h, --help  Show this message and exit.

Commands:
  docs      Read notebook guidance on demand.
  execute   Run Python in a live notebook session.
  notebook  Find active notebooks and their sessions.
  prompt    Generate pairing instructions.
""")

    def test_prompt_help(self) -> None:
        result = _runner.invoke(cli_main, ["pair", "prompt", "--help"])
        assert result.exit_code == 0
        assert "--url" in result.output
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
                'cell = ctx.cells["KBiG"]',
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

Start with: marimo pair --help
If marimo is not on your PATH, run it the same way this notebook server was started.

Once connected, run `import marimo as mo; mo.status.toast("Ready to pair")` to let the user know you are ready.
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

    @pytest.mark.parametrize(
        "agent_flag", ["--claude", "--codex", "--opencode"]
    )
    def test_prompt_accepts_legacy_agent_flag_silently(
        self, agent_flag: str
    ) -> None:
        result = _runner.invoke(
            cli_main,
            [
                "pair",
                "prompt",
                "--url",
                TEST_URL,
                "--session",
                "s_ab12cd",
                agent_flag,
            ],
        )

        assert result.exit_code == 0
        assert "could not be found" not in result.output
        assert "install" not in result.output.lower()


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
