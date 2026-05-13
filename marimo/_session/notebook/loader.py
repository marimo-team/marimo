# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._session.notebook.file_manager import AppFileManager
from marimo._utils.marimo_path import MarimoPath

if TYPE_CHECKING:
    from pathlib import Path

    from marimo._server.app_defaults import AppDefaults


def load_notebook(
    path: str | Path,
    *,
    defaults: AppDefaults | None = None,
) -> AppFileManager:
    """Load a notebook from a path into an ``AppFileManager``.

    The path is validated as a marimo source file (``.py`` / ``.md`` / ``.qmd``)
    and resolved to an absolute path before being handed to the file manager,
    so a later ``chdir`` cannot change which file the manager points at.
    """
    marimo_path = MarimoPath(path)
    return AppFileManager(marimo_path.absolute_name, defaults=defaults)


def new_notebook(
    *,
    defaults: AppDefaults | None = None,
) -> AppFileManager:
    """Create an unbacked ``AppFileManager`` for an untitled notebook."""
    return AppFileManager(None, defaults=defaults)
