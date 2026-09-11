# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import contextlib
import json
import signal
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

from marimo._server.files.directory_scanner import DirectoryScanner
from marimo._server.workspace import flatten_files
from marimo._utils.http import HTTPException, HTTPStatus
from marimo._utils.marimo_path import MarimoPath
from marimo._utils.subprocess import kill_subprocess

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from marimo._environments.environment import Environment


def is_multi_target(paths: list[Path]) -> bool:
    return len(paths) > 1 or any(path.is_dir() for path in paths)


def collect_notebooks(paths: Iterable[Path]) -> list[MarimoPath]:
    notebooks: dict[str, MarimoPath] = {}

    for path in paths:
        if path.is_dir():
            scanner = DirectoryScanner(str(path), include_markdown=True)
            try:
                file_infos = scanner.scan()
            except HTTPException as e:
                if e.status_code != HTTPStatus.REQUEST_TIMEOUT:
                    raise
                file_infos = scanner.partial_results

            for file_info in flatten_files(file_infos):
                if not file_info.is_marimo_file or file_info.is_directory:
                    continue
                absolute_path = str(Path(path) / file_info.path)
                notebooks[absolute_path] = MarimoPath(absolute_path)
        else:
            notebooks[str(path)] = MarimoPath(str(path))

    return [notebooks[k] for k in sorted(notebooks)]


@dataclass(frozen=True)
class SandboxTarget:
    """Where a sandboxed export runs.

    `environment` is the notebook's script environment, or None for a
    notebook without a metadata block, which runs ephemerally.
    """

    environment: Environment | None


class SandboxVenvPool:
    """Caches synchronized script environments by notebook path."""

    def __init__(self) -> None:
        self._targets: dict[str, SandboxTarget] = {}

    def get_target(self, notebook_path: str) -> SandboxTarget:
        from marimo._environments.environment import sync_notebook
        from marimo._environments.uv import UvMissingScriptMetadataError

        key = str(Path(notebook_path).resolve())
        existing = self._targets.get(key)
        if existing is not None:
            return existing

        try:
            target = SandboxTarget(environment=sync_notebook(key))
        except UvMissingScriptMetadataError:
            target = SandboxTarget(environment=None)
        self._targets[key] = target
        return target

    def close(self) -> None:
        # uv owns the environments; there is nothing to remove.
        self._targets.clear()


@contextlib.contextmanager
def _export_termination_signals() -> Iterator[None]:
    """Let termination unwind the runner so its isolated child is reaped."""
    previous = {}

    def terminate(signum: int, _frame: object) -> None:
        raise SystemExit(128 + signum)

    try:
        if threading.current_thread() is threading.main_thread():
            for name in ("SIGTERM", "SIGHUP"):
                signum = getattr(signal, name, None)
                if (
                    signum is not None
                    and signal.getsignal(signum) == signal.SIG_DFL
                ):
                    previous[signum] = signal.signal(signum, terminate)
        yield
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def run_python_subprocess(
    *,
    sandbox: SandboxTarget,
    script: str,
    payload: dict[str, Any],
    action: str,
) -> str:
    import platform

    from marimo._environments.environment import launch, launch_isolated
    from marimo._environments.overlay import runtime_overlay

    args = ["-c", script, json.dumps(payload)]
    overlay = runtime_overlay()
    if sandbox.environment is not None:
        plan = launch(sandbox.environment, args, overlay=overlay)
    else:
        plan = launch_isolated(
            args, overlay=overlay, python=platform.python_version()
        )
    with (
        _export_termination_signals(),
        subprocess.Popen(
            list(plan.argv),
            env=plan.env,
            start_new_session=plan.start_new_session,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ) as process,
    ):
        try:
            stdout, stderr = process.communicate()
        except BaseException:
            kill_subprocess(process, start_new_session=plan.start_new_session)
            raise
    if process.returncode != 0:
        # Identify the real launcher without exposing requirement URLs,
        # credentials, notebook code, or the serialized request payload.
        launcher = Path(plan.argv[0]).name
        command = f"{launcher} <sandbox arguments> -c <script> <payload>"
        raise click.ClickException(
            f"Failed to {action} in sandbox.\n\n"
            f"Command:\n\n  {command}\n\n"
            f"Stderr:\n\n{stderr.strip()}"
        )
    return stdout
