# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import click

from marimo._cli.export._common import (
    collect_notebooks,
    run_python_subprocess,
)
from marimo._cli.help_formatter import SandboxCommand
from marimo._cli.parse_args import parse_args
from marimo._cli.print import echo, green, red, yellow
from marimo._cli.sandbox import resolve_sandbox
from marimo._export._session_cache import (
    is_session_snapshot_stale,
    serialize_session_snapshot,
    write_session_snapshot,
)
from marimo._export.file import run_notebook
from marimo._export.requests import (
    NotebookExecutionOptions,
    RunNotebookRequest,
)
from marimo._schemas.session import NotebookSessionV1
from marimo._server.utils import asyncio_run
from marimo._session.notebook import load_notebook
from marimo._session.state.serialize import get_session_cache_file
from marimo._utils.marimo_path import MarimoPath

if TYPE_CHECKING:
    from marimo._environments.sandbox import Backend


_sandbox_message = (
    "Execute each notebook in an isolated environment with its inline "
    "dependencies. Use --sandbox (uv), --sandbox=uv, or --sandbox=pixi."
)


async def _export_session_snapshot(
    marimo_path: MarimoPath,
    *,
    notebook_args: tuple[str, ...],
    sandbox: Backend | None = None,
) -> tuple[NotebookSessionV1, bool]:
    if not sandbox:
        cli_args = parse_args(notebook_args) if notebook_args else {}

        file_manager = load_notebook(marimo_path.absolute_name)

        session_view, did_error = await run_notebook(
            RunNotebookRequest(
                file_manager=file_manager,
                options=NotebookExecutionOptions(
                    cli_args=cli_args,
                    argv=list(notebook_args),
                    quiet=True,
                    persist_session=False,
                ),
            )
        )
        session_snapshot = serialize_session_snapshot(
            session_view,
            notebook_path=marimo_path.absolute_name,
            cell_ids=list(file_manager.app.cell_manager.cell_ids()),
        )
        return session_snapshot, did_error

    payload = {
        "path": marimo_path.absolute_name,
        "args": list(notebook_args),
    }
    return await _export_session_snapshot_in_subprocess(payload, sandbox)


async def _export_session_snapshot_in_subprocess(
    payload: dict[str, Any],
    backend: Backend,
) -> tuple[NotebookSessionV1, bool]:
    script = r"""
import asyncio
import json
import sys

from marimo._cli.parse_args import parse_args
from marimo._export._session_cache import serialize_session_snapshot
from marimo._export.file import run_notebook
from marimo._export.requests import (
    NotebookExecutionOptions,
    RunNotebookRequest,
)
from marimo._session.notebook import load_notebook
from marimo._utils.marimo_path import MarimoPath

payload = json.loads(sys.argv[1])
path = MarimoPath(payload["path"])
args = payload.get("args") or []

file_manager = load_notebook(path.absolute_name)

cli_args = parse_args(tuple(args)) if args else {}
session_view, did_error = asyncio.run(
    run_notebook(
        RunNotebookRequest(
            file_manager=file_manager,
            options=NotebookExecutionOptions(
                cli_args=cli_args,
                argv=list(args),
                quiet=True,
                persist_session=False,
            ),
        )
    )
)
session_snapshot = serialize_session_snapshot(
    session_view,
    notebook_path=path.absolute_name,
    cell_ids=list(file_manager.app.cell_manager.cell_ids()),
)

sys.stdout.write(
    json.dumps(
        {
            "session_snapshot": session_snapshot,
            "did_error": did_error,
        }
    )
)
"""

    output = await run_python_subprocess(
        notebook_path=payload["path"],
        backend=backend,
        script=script,
        payload=payload,
        action="export session",
    )

    try:
        data = cast(dict[str, Any], json.loads(output))
    except json.JSONDecodeError as e:
        raise click.ClickException(
            "Failed to parse sandbox session export output.\n\n"
            f"Stdout:\n\n{output.strip()}"
        ) from e

    session_snapshot = data.get("session_snapshot")
    did_error = bool(data.get("did_error", False))
    if not isinstance(session_snapshot, dict):
        raise click.ClickException(
            "Sandbox session export returned an invalid payload."
        )

    return cast(NotebookSessionV1, session_snapshot), did_error


async def _export_session_for_notebook(
    notebook: MarimoPath,
    *,
    force_overwrite: bool,
    notebook_args: tuple[str, ...],
    sandbox: Backend | None,
) -> None:
    if _maybe_skip_fresh_snapshot(notebook, force_overwrite=force_overwrite):
        return

    echo(f"Running {notebook.short_name}...")

    session_snapshot, did_error = await _export_session_snapshot(
        notebook,
        notebook_args=notebook_args,
        sandbox=sandbox,
    )

    output = write_session_snapshot(
        notebook_path=notebook.path,
        snapshot=session_snapshot,
    )

    if did_error:
        raise click.ClickException(
            "Session export succeeded, but some cells failed to execute."
        )

    echo(green("ok") + f": {output}")


def _maybe_skip_fresh_snapshot(
    notebook: MarimoPath, *, force_overwrite: bool
) -> bool:
    output = get_session_cache_file(notebook.path)
    if force_overwrite or not output.exists():
        return False
    if is_session_snapshot_stale(output, notebook):
        return False

    echo(
        yellow("skip") + f": {notebook.short_name} "
        "(up-to-date, use --force-overwrite if you want to re-export anyway)"
    )
    return True


async def _export_sessions(
    *,
    notebooks: list[MarimoPath],
    force_overwrite: bool,
    notebook_args: tuple[str, ...],
    continue_on_error: bool,
    sandbox: Backend | None,
) -> None:
    failures: list[tuple[MarimoPath, Exception]] = []

    for notebook in notebooks:
        try:
            await _export_session_for_notebook(
                notebook,
                force_overwrite=force_overwrite,
                notebook_args=notebook_args,
                sandbox=sandbox,
            )
        except Exception as error:
            failures.append((notebook, error))
            echo(red("error") + f": {notebook.short_name}: {error}")
            if not continue_on_error:
                raise

    if failures:
        raise click.ClickException(
            f"Failed to export sessions for {len(failures)} notebooks."
        )


@click.command(
    "session",
    cls=SandboxCommand,
    help=(
        "Execute a notebook or directory of notebooks and export session snapshots."
    ),
)
@click.argument(
    "name",
    type=click.Path(
        exists=True, file_okay=True, dir_okay=True, path_type=Path
    ),
)
@click.option(
    "--sandbox",
    default=None,
    type=click.Choice(["uv", "pixi"]),
    help=_sandbox_message,
)
@click.option(
    "--no-sandbox",
    is_flag=True,
    default=False,
    help="Never run in a sandbox, and never prompt to.",
)
@click.option(
    "--force-overwrite/--no-force-overwrite",
    default=False,
    help=(
        "Overwrite all existing session snapshots, even if they are "
        "already up-to-date."
    ),
)
@click.option(
    "--continue-on-error/--no-continue-on-error",
    default=True,
    help="Continue processing other notebooks if one notebook fails.",
)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def session(
    name: Path,
    sandbox: str | None,
    no_sandbox: bool,
    force_overwrite: bool,
    continue_on_error: bool,
    args: tuple[str, ...],
) -> None:
    """Execute notebooks and export their session snapshots."""
    path_targets = [name]
    notebooks = collect_notebooks(path_targets)
    if not notebooks:
        raise click.ClickException("No marimo notebooks found.")

    asyncio_run(
        _export_sessions(
            notebooks=notebooks,
            force_overwrite=force_overwrite,
            notebook_args=args,
            continue_on_error=continue_on_error,
            sandbox=resolve_sandbox(sandbox, no_sandbox, str(name)),
        )
    )
