# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from marimo._server.file_router import flatten_files
from marimo._server.files.directory_scanner import DirectoryScanner
from marimo._utils.http import HTTPException, HTTPStatus
from marimo._utils.marimo_path import MarimoPath

if TYPE_CHECKING:
    from collections.abc import Iterable


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


class SandboxVenvPool:
    def __init__(self) -> None:
        self._envs: dict[tuple[str, ...], tuple[str, str]] = {}

    def get_python(self, notebook_path: str) -> str:
        from marimo._cli.sandbox import (
            build_sandbox_venv,
            get_sandbox_requirements,
        )

        requirements = tuple(get_sandbox_requirements(notebook_path))
        existing = self._envs.get(requirements)
        if existing is not None:
            return existing[1]

        sandbox_dir, venv_python = build_sandbox_venv(notebook_path)
        self._envs[requirements] = (sandbox_dir, venv_python)
        return venv_python

    def close(self) -> None:
        from marimo._cli.sandbox import cleanup_sandbox_dir

        for sandbox_dir, _ in self._envs.values():
            cleanup_sandbox_dir(sandbox_dir)
        self._envs.clear()
