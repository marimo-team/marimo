# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import click
import pytest
from click.testing import CliRunner

import marimo._cli.export.session as session_module
from marimo._cli.sandbox import SandboxMode
from marimo._server.utils import asyncio_run
from marimo._session.state.serialize import get_session_cache_file

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


def test_session_sandbox_single_skips_before_sandbox_when_fresh(
    tmp_path: Path,
) -> None:
    notebook = tmp_path / "notebook.py"
    _write_notebook(notebook)
    session_file = get_session_cache_file(notebook)
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text("{}", encoding="utf-8")
    runner = CliRunner()

    with (
        patch(
            "marimo._cli.sandbox.resolve_sandbox_mode",
            return_value=SandboxMode.SINGLE,
        ),
        patch.object(
            session_module,
            "is_session_snapshot_stale",
            return_value=False,
        ) as is_stale,
        patch("marimo._cli.sandbox.run_in_sandbox") as run_in_sandbox,
    ):
        result = runner.invoke(
            session_module.session,
            [str(notebook), "--sandbox"],
        )

    assert result.exit_code == 0, result.output
    is_stale.assert_called_once()
    run_in_sandbox.assert_not_called()
    assert "skip:" in result.output


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


def test_export_sessions_continue_on_error_processes_remaining(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    third = tmp_path / "third.py"
    _write_notebook(first)
    _write_notebook(second)
    _write_notebook(third)
    notebooks = [
        session_module.MarimoPath(str(p)) for p in [first, second, third]
    ]

    called: list[str] = []

    async def fake_export(
        marimo_path: session_module.MarimoPath,
        *,
        notebook_args: tuple[str, ...],
        venv_python: str | None = None,
    ) -> tuple[dict[str, str], bool]:
        del notebook_args, venv_python
        called.append(marimo_path.short_name)
        if marimo_path.short_name == "second.py":
            raise click.ClickException("boom")
        return {"name": marimo_path.short_name}, False

    with (
        patch.object(
            session_module,
            "_export_session_snapshot",
            new=AsyncMock(side_effect=fake_export),
        ),
        pytest.raises(
            click.ClickException,
            match="Failed to export sessions for 1 notebooks",
        ),
    ):
        asyncio_run(
            session_module._export_sessions(
                notebooks=notebooks,
                force_overwrite=True,
                notebook_args=(),
                continue_on_error=True,
                sandbox_mode=None,
            )
        )

    assert called == ["first.py", "second.py", "third.py"]
    assert get_session_cache_file(first).exists()
    assert not get_session_cache_file(second).exists()
    assert get_session_cache_file(third).exists()


def test_export_sessions_no_continue_on_error_stops_at_first_error(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    third = tmp_path / "third.py"
    _write_notebook(first)
    _write_notebook(second)
    _write_notebook(third)
    notebooks = [
        session_module.MarimoPath(str(p)) for p in [first, second, third]
    ]

    called: list[str] = []

    async def fake_export(
        marimo_path: session_module.MarimoPath,
        *,
        notebook_args: tuple[str, ...],
        venv_python: str | None = None,
    ) -> tuple[dict[str, str], bool]:
        del notebook_args, venv_python
        called.append(marimo_path.short_name)
        if marimo_path.short_name == "first.py":
            raise click.ClickException("first failed")
        return {"name": marimo_path.short_name}, False

    with (
        patch.object(
            session_module,
            "_export_session_snapshot",
            new=AsyncMock(side_effect=fake_export),
        ),
        pytest.raises(click.ClickException, match="first failed"),
    ):
        asyncio_run(
            session_module._export_sessions(
                notebooks=notebooks,
                force_overwrite=True,
                notebook_args=(),
                continue_on_error=False,
                sandbox_mode=None,
            )
        )

    assert called == ["first.py"]
    assert not get_session_cache_file(first).exists()
    assert not get_session_cache_file(second).exists()
    assert not get_session_cache_file(third).exists()


def test_export_session_snapshot_subprocess_invalid_json() -> None:
    with (
        patch.object(
            session_module, "run_python_subprocess", return_value="not json"
        ),
        pytest.raises(
            click.ClickException,
            match="Failed to parse sandbox session export output",
        ),
    ):
        session_module._export_session_snapshot_in_subprocess(
            "python",
            {"path": "notebook.py", "args": []},
        )
