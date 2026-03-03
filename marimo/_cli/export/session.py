# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, cast

import click

from marimo._cli.errors import MarimoCLIMissingDependencyError
from marimo._cli.export._common import (
    SandboxVenvPool,
    collect_notebooks,
    is_multi_target,
    run_python_subprocess,
)
from marimo._cli.parse_args import parse_args
from marimo._cli.print import echo, green, red, yellow
from marimo._dependencies.dependencies import DependencyManager
from marimo._schemas.session import NotebookSessionV1
from marimo._server.export import run_app_until_completion
from marimo._server.file_router import AppFileRouter
from marimo._server.utils import asyncio_run
from marimo._session.state.serialize import (
    get_session_cache_file,
    serialize_session_view,
)
from marimo._utils.code import hash_code
from marimo._utils.marimo_path import MarimoPath
from marimo._utils.paths import maybe_make_dirs

if TYPE_CHECKING:
    from marimo._cli.sandbox import SandboxMode

_sandbox_message = (
    "Run the command in an isolated virtual environment using "
    "`uv run --isolated`. Requires `uv`."
)


def _resolve_session_sandbox_mode(
    *,
    sandbox: bool | None,
    path_targets: list[Path],
    first_target: str,
) -> SandboxMode | None:
    from marimo._cli.sandbox import SandboxMode, resolve_sandbox_mode

    if is_multi_target(path_targets):
        if sandbox is None:
            return None
        return SandboxMode.MULTI if sandbox else None

    return resolve_sandbox_mode(sandbox=sandbox, name=first_target)


async def _export_session_snapshot(
    marimo_path: MarimoPath,
    *,
    notebook_args: tuple[str, ...],
    venv_python: str | None = None,
) -> tuple[NotebookSessionV1, bool]:
    if venv_python is None:
        cli_args = parse_args(notebook_args) if notebook_args else {}

        file_router = AppFileRouter.from_filename(marimo_path)
        file_key = file_router.get_unique_file_key()
        if file_key is None:
            raise RuntimeError(
                "Expected a unique file key when exporting a single "
                f"notebook: {marimo_path.absolute_name}"
            )
        file_manager = file_router.get_file_manager(file_key)

        session_view, did_error = await run_app_until_completion(
            file_manager,
            cli_args=cli_args,
            argv=list(notebook_args),
            quiet=True,
        )
        session_snapshot = serialize_session_view(
            session_view,
            cell_ids=list(file_manager.app.cell_manager.cell_ids()),
        )
        return session_snapshot, did_error

    payload = {
        "path": marimo_path.absolute_name,
        "args": list(notebook_args),
    }
    return await asyncio.to_thread(
        _export_session_snapshot_in_subprocess,
        venv_python,
        payload,
    )


def _export_session_snapshot_in_subprocess(
    venv_python: str, payload: dict[str, Any]
) -> tuple[NotebookSessionV1, bool]:
    script = r"""
import asyncio
import json
import sys

from marimo._cli.parse_args import parse_args
from marimo._server.export import run_app_until_completion
from marimo._server.file_router import AppFileRouter
from marimo._session.state.serialize import serialize_session_view
from marimo._utils.marimo_path import MarimoPath

payload = json.loads(sys.argv[1])
path = MarimoPath(payload["path"])
args = payload.get("args") or []

file_router = AppFileRouter.from_filename(path)
file_key = file_router.get_unique_file_key()
if file_key is None:
    raise RuntimeError("Expected a unique file key for session export.")
file_manager = file_router.get_file_manager(file_key)

cli_args = parse_args(tuple(args)) if args else {}
session_view, did_error = asyncio.run(
    run_app_until_completion(
        file_manager,
        cli_args=cli_args,
        argv=list(args),
        quiet=True,
    )
)
session_snapshot = serialize_session_view(
    session_view,
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

    output = run_python_subprocess(
        venv_python=venv_python,
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
    sandbox_pool: SandboxVenvPool | None,
) -> None:
    output = get_session_cache_file(notebook.path)
    if _maybe_skip_fresh_snapshot(notebook, force_overwrite=force_overwrite):
        return

    echo(f"Running {notebook.short_name}...")
    venv_python = (
        sandbox_pool.get_python(str(notebook.path))
        if sandbox_pool is not None
        else None
    )

    session_snapshot, did_error = await _export_session_snapshot(
        notebook,
        notebook_args=notebook_args,
        venv_python=venv_python,
    )

    maybe_make_dirs(output)
    output.write_text(json.dumps(session_snapshot, indent=2), encoding="utf-8")

    if did_error:
        raise click.ClickException(
            "Session export succeeded, but some cells failed to execute."
        )

    echo(green("ok") + f": {output}")


def _hash_code_for_session_compare(code: str | None) -> str | None:
    if code is None or code == "":
        return None
    return hash_code(code)


def _current_notebook_code_hashes(
    notebook: MarimoPath,
) -> tuple[str | None, ...]:
    file_router = AppFileRouter.from_filename(notebook)
    file_key = file_router.get_unique_file_key()
    if file_key is None:
        raise RuntimeError(
            "Expected a unique file key when checking staleness for "
            f"{notebook.absolute_name}"
        )
    file_manager = file_router.get_file_manager(file_key)
    return tuple(
        _hash_code_for_session_compare(cell_data.code)
        for cell_data in file_manager.app.cell_manager.cell_data()
    )


def _is_session_snapshot_stale(output: Path, notebook: MarimoPath) -> bool:
    """Return True when a saved session should be regenerated.

    We treat a snapshot as stale if we cannot read it, if it is malformed, or
    if the notebook's current cell code-hash multiset does not match the snapshot.
    Code hashes are compared order-independently because notebook and
    session cell ordering can differ across code paths.
    """
    try:
        snapshot = cast(
            dict[str, Any], json.loads(output.read_text(encoding="utf-8"))
        )
    except (OSError, json.JSONDecodeError):
        return True

    metadata = snapshot.get("metadata")
    if not isinstance(metadata, dict):
        return True

    cells = snapshot.get("cells")
    if not isinstance(cells, list):
        return True

    try:
        current_hashes = _current_notebook_code_hashes(notebook)
    except (RuntimeError, ValueError, OSError, SyntaxError):
        return True

    notebook_hashes = Counter(current_hashes)

    session_hashes: Counter[str | None] = Counter()
    for cell in cells:
        if not isinstance(cell, dict):
            return True
        if "code_hash" not in cell:
            return True
        code_hash = cell["code_hash"]
        if code_hash is not None and not isinstance(code_hash, str):
            return True
        session_hashes[code_hash] += 1

    return notebook_hashes != session_hashes


def _maybe_skip_fresh_snapshot(
    notebook: MarimoPath, *, force_overwrite: bool
) -> bool:
    output = get_session_cache_file(notebook.path)
    if force_overwrite or not output.exists():
        return False
    if _is_session_snapshot_stale(output, notebook):
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
    sandbox_mode: SandboxMode | None,
) -> None:
    from marimo._cli.sandbox import SandboxMode

    failures: list[tuple[MarimoPath, Exception]] = []
    use_per_notebook_sandbox = sandbox_mode is SandboxMode.MULTI

    if use_per_notebook_sandbox and not DependencyManager.which("uv"):
        raise MarimoCLIMissingDependencyError(
            "uv is required for --sandbox session export.",
            "uv",
            additional_tip="Install uv from https://github.com/astral-sh/uv",
        )

    sandbox_pool: SandboxVenvPool | None = (
        SandboxVenvPool() if use_per_notebook_sandbox else None
    )

    try:
        for notebook in notebooks:
            try:
                await _export_session_for_notebook(
                    notebook,
                    force_overwrite=force_overwrite,
                    notebook_args=notebook_args,
                    sandbox_pool=sandbox_pool,
                )
            except Exception as error:
                failures.append((notebook, error))
                echo(red("error") + f": {notebook.short_name}: {error}")
                if not continue_on_error:
                    raise
    finally:
        if sandbox_pool is not None:
            sandbox_pool.close()

    if failures:
        raise click.ClickException(
            f"Failed to export sessions for {len(failures)} notebooks."
        )


@click.command(
    "session",
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
    "--sandbox/--no-sandbox",
    is_flag=True,
    default=None,
    type=bool,
    help=_sandbox_message,
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
    sandbox: Optional[bool],
    force_overwrite: bool,
    continue_on_error: bool,
    args: tuple[str, ...],
) -> None:
    """Execute notebooks and export their session snapshots."""
    path_targets = [name]
    notebooks = collect_notebooks(path_targets)
    if not notebooks:
        raise click.ClickException("No marimo notebooks found.")

    sandbox_mode = _resolve_session_sandbox_mode(
        sandbox=sandbox,
        path_targets=path_targets,
        first_target=str(name),
    )

    from marimo._cli.sandbox import SandboxMode, run_in_sandbox

    if sandbox_mode is SandboxMode.SINGLE:
        notebook = notebooks[0]
        if _maybe_skip_fresh_snapshot(
            notebook, force_overwrite=force_overwrite
        ):
            return
        run_in_sandbox(sys.argv[1:], name=str(name))
        return

    asyncio_run(
        _export_sessions(
            notebooks=notebooks,
            force_overwrite=force_overwrite,
            notebook_args=args,
            continue_on_error=continue_on_error,
            sandbox_mode=sandbox_mode,
        )
    )
