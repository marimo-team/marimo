# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

import marimo._cli.export.session as session_module
from marimo._cli.sandbox import SandboxMode

if TYPE_CHECKING:
    from pathlib import Path


def _write_notebook(path: Path) -> None:
    path.write_text(
        """
import marimo

app = marimo.App()

@app.cell
def _():
    return

if __name__ == "__main__":
    app.run()
""",
        encoding="utf-8",
    )


def test_session_sandbox_single_runs_in_sandbox(tmp_path: Path) -> None:
    notebook = tmp_path / "notebook.py"
    _write_notebook(notebook)
    runner = CliRunner()
    export_sessions = AsyncMock()

    with (
        patch(
            "marimo._cli.sandbox.run_in_sandbox",
            return_value=0,
        ) as run_in_sandbox,
        patch(
            "marimo._cli.sandbox.resolve_sandbox_mode",
            return_value=SandboxMode.SINGLE,
        ) as resolve_sandbox_mode,
        patch.object(session_module, "_export_sessions", new=export_sessions),
    ):
        result = runner.invoke(
            session_module.session,
            [str(notebook), "--sandbox"],
        )

    assert result.exit_code == 0, result.output
    run_in_sandbox.assert_called_once()
    resolve_sandbox_mode.assert_called_once()
    assert run_in_sandbox.call_args.kwargs["name"] == str(notebook)
    export_sessions.assert_not_called()


def test_session_sandbox_multi_uses_in_process_export(tmp_path: Path) -> None:
    notebook_dir = tmp_path / "notebooks"
    notebook_dir.mkdir()
    first = notebook_dir / "first.py"
    second = notebook_dir / "second.py"
    _write_notebook(first)
    _write_notebook(second)
    runner = CliRunner()
    export_sessions = AsyncMock()

    with (
        patch("marimo._cli.sandbox.run_in_sandbox") as run_in_sandbox,
        patch("marimo._cli.sandbox.resolve_sandbox_mode") as resolve_mode,
        patch.object(session_module, "_export_sessions", new=export_sessions),
    ):
        result = runner.invoke(
            session_module.session,
            [str(notebook_dir), "--sandbox"],
        )

    assert result.exit_code == 0, result.output
    run_in_sandbox.assert_not_called()
    resolve_mode.assert_not_called()
    export_sessions.assert_called_once()
    assert (
        export_sessions.call_args.kwargs["sandbox_mode"] is SandboxMode.MULTI
    )


def test_session_no_sandbox_uses_in_process_export(tmp_path: Path) -> None:
    notebook = tmp_path / "notebook.py"
    _write_notebook(notebook)
    runner = CliRunner()
    export_sessions = AsyncMock()

    with (
        patch("marimo._cli.sandbox.run_in_sandbox") as run_in_sandbox,
        patch(
            "marimo._cli.sandbox.resolve_sandbox_mode", return_value=None
        ) as resolve_mode,
        patch.object(session_module, "_export_sessions", new=export_sessions),
    ):
        result = runner.invoke(
            session_module.session,
            [str(notebook), "--no-sandbox"],
        )

    assert result.exit_code == 0, result.output
    run_in_sandbox.assert_not_called()
    resolve_mode.assert_called_once()
    export_sessions.assert_called_once()
    assert export_sessions.call_args.kwargs["sandbox_mode"] is None
