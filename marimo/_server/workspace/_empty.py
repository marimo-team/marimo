# Copyright 2026 Marimo. All rights reserved.
"""Workspace for an untitled (new) notebook."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from marimo._server.workspace._base import (
    NEW_FILE,
    MarimoFileKey,
    NotebookWorkspace,
    file_not_found,
)

if TYPE_CHECKING:
    from marimo._server.models.files import FileInfo
    from marimo._server.models.home import MarimoFile


class EmptyWorkspace(NotebookWorkspace):
    """An empty (untitled) workspace, used by ``marimo new``.

    The workspace key is the ``__new__`` sentinel; concrete file paths are
    accepted as a fallback so that callers which bootstrap with
    ``EmptyWorkspace`` and later open a real file (e.g. via the homepage)
    continue to work.
    """

    def get_unique_file_key(self) -> MarimoFileKey | None:
        return NEW_FILE

    def single_file(self) -> MarimoFile | None:
        return None

    @property
    def files(self) -> list[FileInfo]:
        return []

    def resolve(self, key: MarimoFileKey) -> str | None:
        if key.startswith(NEW_FILE):
            return None
        if os.path.exists(key):
            return key
        raise file_not_found(key)
