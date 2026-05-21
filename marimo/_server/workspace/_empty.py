# Copyright 2026 Marimo. All rights reserved.
"""Workspace for an untitled (new) notebook."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from marimo._server.workspace._base import (
    NotebookWorkspace,
    file_not_found,
)
from marimo._server.workspace._keys import (
    FileKey,
    NewFileKey,
)
from marimo._utils.paths import normalize_path

if TYPE_CHECKING:
    from marimo._server.models.files import FileInfo
    from marimo._server.models.home import MarimoFile


class EmptyWorkspace(NotebookWorkspace):
    """An empty (untitled) workspace, used by `marimo new`.

    The workspace key is the `__new__` sentinel; concrete file paths are
    accepted as a fallback so that callers which bootstrap with
    `EmptyWorkspace` and later open a real file (e.g. via the homepage)
    continue to work.
    """

    def get_unique_file_key(self) -> FileKey | None:
        return NewFileKey()

    def single_file(self) -> MarimoFile | None:
        return None

    @property
    def files(self) -> list[FileInfo]:
        return []

    def resolve(self, key: FileKey) -> str | None:
        if isinstance(key, NewFileKey):
            return None
        if os.path.exists(key.path):
            # Match sibling workspaces: return an absolute normalized path so
            # downstream comparisons (e.g. session lookups) don't trip on
            # relative-vs-absolute mismatches.
            return str(normalize_path(Path(key.path)))
        raise file_not_found(key)
