# Copyright 2026 Marimo. All rights reserved.
"""Abstract base class for server-side notebook workspaces."""

from __future__ import annotations

import abc
from pathlib import Path
from typing import TYPE_CHECKING

from marimo._server.app_defaults import AppDefaults
from marimo._session.notebook import AppFileManager
from marimo._utils.http import HTTPException, HTTPStatus
from marimo._utils.marimo_path import MarimoPath
from marimo._utils.paths import normalize_path

if TYPE_CHECKING:
    from collections.abc import Iterator

    from marimo._server.models.files import FileInfo
    from marimo._server.models.home import MarimoFile

# Wire-format key for an untitled notebook. The string boundary is preserved
# for HTTP query params and session initialization IDs.
NEW_FILE: str = "__new__"

# Some unique identifier for a file. Phase 3 will replace this with a tagged
# union (NewFileKey | PathFileKey).
MarimoFileKey = str


class NotebookWorkspace(abc.ABC):
    """A server-side abstraction for the set of notebooks a server is hosting.

    Owned by ``SessionManager``. Handles workspace browsing, allowlisting, lazy
    directory scanning, and security validation.
    """

    @property
    def directory(self) -> str | None:
        """The root directory of this workspace, if any."""
        return None

    @property
    @abc.abstractmethod
    def files(self) -> list[FileInfo]:
        """All files in this workspace as a recursive tree."""

    @abc.abstractmethod
    def single_file(self) -> MarimoFile | None:
        """If this workspace represents a single notebook, return it."""

    @abc.abstractmethod
    def get_unique_file_key(self) -> MarimoFileKey | None:
        """The unique file key for this workspace, if any."""

    @abc.abstractmethod
    def resolve(self, key: MarimoFileKey) -> str | None:
        """Resolve a key to an absolute path; ``None`` for new files.

        Useful for endpoints that need file-backed resources (e.g. thumbnails)
        without the overhead of parsing/loading a notebook.
        """

    def load(
        self,
        key: MarimoFileKey,
        defaults: AppDefaults | None = None,
    ) -> AppFileManager:
        """Load the notebook for the given key into an ``AppFileManager``.

        Built on top of :meth:`resolve` — subclasses customize ``resolve`` and
        inherit the right ``load`` semantics for free.
        """
        defaults = defaults or AppDefaults()
        resolved = self.resolve(key)
        if resolved is None:
            return AppFileManager(None, defaults=defaults)
        return AppFileManager(resolved, defaults=defaults)

    def get_single_app_file_manager(
        self,
        defaults: AppDefaults | None = None,
    ) -> AppFileManager:
        """Convenience for workspaces with a unique single file."""
        key = self.get_unique_file_key()
        assert key is not None, "Expected a single file"
        return self.load(key, defaults)

    # Optional capabilities — subclasses override only when supported.

    def register_allowed_path(self, path: str) -> None:
        """Allow a file path that wasn't part of the original collection.

        No-op by default. ``SingleFileWorkspace`` overrides to extend its
        allowlist for files created at runtime.
        """
        del path

    def register_temp_dir(self, temp_dir: str) -> None:
        """Register a temp directory as allowed for file access.

        No-op by default. ``DirectoryWorkspace`` overrides for tutorial
        support.
        """
        del temp_dir

    def is_in_allowed_temp_dir(self, path: str) -> bool:
        """Whether ``path`` lives inside an allowed temp directory.

        Returns ``False`` by default. ``DirectoryWorkspace`` overrides.
        """
        del path
        return False

    def invalidate(self) -> None:  # noqa: B027 — intentional no-op default
        """Invalidate any cached listing.

        No-op by default. ``DirectoryWorkspace`` overrides.
        """

    def set_include_markdown(self, include_markdown: bool) -> None:
        """Toggle markdown inclusion in directory listings.

        No-op by default. ``DirectoryWorkspace`` overrides — mutates in
        place.
        """
        del include_markdown


def file_not_found(key: MarimoFileKey) -> HTTPException:
    """Build the standard 404 response for an unresolvable file key."""
    return HTTPException(
        status_code=HTTPStatus.NOT_FOUND,
        detail=f"File {key} not found",
    )


def normalize_allowlist_entry(path: str) -> str:
    """Canonicalize a path for storage in or lookup against an allowlist.

    Resolves the path to absolute form (validating it as a marimo source file)
    and applies our standard normalization. Allowlist entries and lookup keys
    must run through this same pipeline to match.
    """
    return str(normalize_path(Path(MarimoPath(path).absolute_name)))


def count_files(file_list: list[FileInfo]) -> int:
    """Count notebook files (not directories) in a recursive tree."""
    count = 0
    for item in file_list:
        if not item.is_directory:
            count += 1
        if item.children:
            count += count_files(item.children)
    return count


def flatten_files(files: list[FileInfo]) -> Iterator[FileInfo]:
    """Iterate over files, skipping directories."""
    stack = files.copy()
    while stack:
        file = stack.pop()
        if file.is_directory:
            stack.extend(file.children)
        else:
            yield file
