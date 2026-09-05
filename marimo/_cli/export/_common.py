# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

from marimo._server.files.directory_scanner import DirectoryScanner
from marimo._server.workspace import flatten_files
from marimo._utils.http import HTTPException, HTTPStatus
from marimo._utils.marimo_path import MarimoPath

if TYPE_CHECKING:
    from collections.abc import Iterable

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
        from marimo._environments.backends import sync_notebook
        from marimo._environments.uv import UvMissingScriptMetadataError

        key = str(Path(notebook_path).resolve())
        existing = self._targets.get(key)
        if existing is not None:
            return existing

        try:
            target = SandboxTarget(
                environment=sync_notebook(key, backend="uv")
            )
        except UvMissingScriptMetadataError:
            target = SandboxTarget(environment=None)
        self._targets[key] = target
        return target

    def close(self) -> None:
        # uv owns the environments; there is nothing to remove.
        self._targets.clear()


def run_python_subprocess(
    *,
    sandbox: SandboxTarget,
    script: str,
    payload: dict[str, Any],
    action: str,
) -> str:
    from marimo._environments.backends import launch_fallback
    from marimo._environments.environment import launch
    from marimo._environments.overlay import runtime_overlay

    args = ["-c", script, json.dumps(payload)]
    if sandbox.environment is not None:
        plan = launch(sandbox.environment, args, overlay=runtime_overlay())
    else:
        plan = launch_fallback(args)
    result = subprocess.run(
        list(plan.argv),
        env=plan.env,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise click.ClickException(
            f"Failed to {action} in sandbox.\n\n"
            f"Command:\n\n  python -c <script>\n\n"
            f"Stderr:\n\n{stderr}"
        )
    return result.stdout
