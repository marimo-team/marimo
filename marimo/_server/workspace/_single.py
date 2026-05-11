# Copyright 2026 Marimo. All rights reserved.
"""Workspace for a single notebook (``marimo edit nb.py``)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from marimo._server.models.home import MarimoFile
from marimo._server.workspace._base import (
    NEW_FILE,
    MarimoFileKey,
    NotebookWorkspace,
    file_not_found,
    normalize_allowlist_entry,
)
from marimo._utils.marimo_path import MarimoPath
from marimo._utils.paths import normalize_path

if TYPE_CHECKING:
    from marimo._server.models.files import FileInfo


class SingleFileWorkspace(NotebookWorkspace):
    """A workspace pointing at a single notebook.

    Used by ``marimo edit nb.py`` and ``marimo run nb.py``. In edit mode the
    allowlist can grow at runtime (via ``register_allowed_path``) to support
    notebooks created during the session.
    """

    def __init__(self, file: MarimoFile) -> None:
        self._file = file
        self._allowed_paths = {normalize_allowlist_entry(file.path)}

    @staticmethod
    def from_path(file: MarimoPath) -> SingleFileWorkspace:
        """Build a workspace from a validated marimo path."""
        return SingleFileWorkspace(
            MarimoFile(
                name=file.relative_name,
                path=file.absolute_name,
                last_modified=file.last_modified,
            )
        )

    @property
    def files(self) -> list[FileInfo]:
        from marimo._server.models.files import FileInfo

        return [
            FileInfo(
                id=self._file.path,
                name=self._file.name,
                path=self._file.path,
                last_modified=self._file.last_modified,
                is_directory=False,
                is_marimo_file=True,
            )
        ]

    def single_file(self) -> MarimoFile | None:
        return self._file

    def get_unique_file_key(self) -> MarimoFileKey | None:
        return self._file.path

    def resolve(self, key: MarimoFileKey) -> str | None:
        if key.startswith(NEW_FILE):
            return None

        filepath = Path(key)
        normalized_path = normalize_path(filepath)
        absolute_path = str(normalized_path)
        if absolute_path not in self._allowed_paths:
            raise file_not_found(key)

        if normalized_path.exists():
            return absolute_path

        raise file_not_found(key)

    def register_allowed_path(self, path: str) -> None:
        """Extend the allowlist for files created at runtime.

        Always extends, unconditionally — ``SingleFileWorkspace`` represents
        single-file edit mode, where the user can branch off into new
        notebooks created by the kernel. The fixed-allowlist behavior of
        :class:`FixedFilesWorkspace` is the read-only counterpart.
        """
        self._allowed_paths.add(normalize_allowlist_entry(path))
