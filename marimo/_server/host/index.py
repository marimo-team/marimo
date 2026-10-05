# Copyright 2026 Marimo. All rights reserved.
"""The workspace as the host's one project.

A scan of the workspace is reported to the host as observations, and
the host works out what changed. Ids are minted here and kept for the
life of the process, so a rescan finds the same notebook under the
same id.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from marimo._host.model import Indexed, Notebook, Partial, Project
from marimo._host.transitions import IndexProject, NotebookGone, NotebookSeen
from marimo._types.ids import NotebookId, ProjectId
from marimo._utils.ids import new_id

if TYPE_CHECKING:
    from collections.abc import Iterator

    from marimo._host.host import Host
    from marimo._server.models.files import FileInfo
    from marimo._server.workspace import NotebookWorkspace

_TRUNCATED = "The scan stopped at its depth, file count, or time limit"


class WorkspaceIndex:
    """Publishes a workspace's notebooks into a host as one project."""

    def __init__(self, host: Host, workspace: NotebookWorkspace) -> None:
        self._host = host
        self._workspace = workspace
        self._root = _root_of(workspace)
        self._project_id = ProjectId(new_id("proj"))
        self._ids: dict[Path, NotebookId] = {}

    @property
    def project_id(self) -> ProjectId:
        return self._project_id

    @property
    def root(self) -> Path | None:
        """The project's directory, or `None` when the workspace has none."""
        return self._root

    def refresh(self) -> None:
        """Rescans the workspace and reports every difference to the host.

        A notebook the scan no longer lists is reported gone only if its
        file is missing, since a scan can omit a file `ensure` admitted.
        """
        self._report(self._scan())

    async def refresh_in_thread(self) -> None:
        """Like `refresh`, with the scan itself off the event loop."""
        self._report(await asyncio.to_thread(self._scan))

    def _scan(self) -> tuple[list[FileInfo], bool]:
        self._workspace.invalidate()
        return (
            list(_marimo_files(self._workspace.files)),
            self._workspace.is_truncated,
        )

    def _report(self, scan: tuple[list[FileInfo], bool]) -> None:
        files, truncated = scan
        index = Partial(_TRUNCATED) if truncated else Indexed()
        project = Project(
            self._project_id,
            "workspace" if self._root is None else self._root.name,
            self._root,
            index,
        )
        self._host.observe(IndexProject(project))

        seen: set[NotebookId] = set()
        for file in files:
            notebook = self._notebook(Path(file.path), file.last_modified)
            if notebook is None:
                continue
            seen.add(notebook.id)
            self._host.observe(NotebookSeen(notebook))

        for notebook in list(self._host.state.notebooks.values()):
            if notebook.project_id != self._project_id or notebook.id in seen:
                continue
            if notebook.path is not None and self._root is not None:
                if (self._root / notebook.path).exists():
                    continue
            self._host.observe(NotebookGone(notebook.id))

    def ensure(
        self, path: str, *, request_id: str | None = None
    ) -> NotebookId | None:
        """Admits a file under the root that the listing may not include.

        Returns its notebook id, or `None` for a file outside the project or
        no longer there.
        """
        file = Path(path)
        try:
            modified = file.stat().st_mtime
        except OSError:
            # Missing, or gone between the caller's look and ours.
            return None
        notebook = self._notebook(file, modified)
        if notebook is None:
            return None
        self._host.observe(NotebookSeen(notebook), request_id=request_id)
        return notebook.id

    def moved(
        self, notebook_id: NotebookId, path: Path, *, request_id: str | None
    ) -> Notebook | None:
        """Records that a notebook's file now lives at `path`, which may be absolute.

        The notebook keeps its id. Returns `None` for a path outside the project.
        """
        relative = self._relative(path)
        if relative is None:
            return None
        for old, known in list(self._ids.items()):
            if known == notebook_id:
                del self._ids[old]
        self._ids[relative] = notebook_id
        assert self._root is not None
        file = self._root / relative
        try:
            modified: float | None = file.stat().st_mtime
        except OSError:
            modified = None
        notebook = self._notebook(file, modified)
        assert notebook is not None
        self._host.observe(NotebookSeen(notebook), request_id=request_id)
        return notebook

    def _relative(self, file: Path) -> Path | None:
        """The root-relative form of `file`, or `None` if it lies outside."""
        if self._root is None:
            return None
        if not file.is_absolute():
            file = self._root / file
        try:
            return file.resolve().relative_to(self._root.resolve())
        except ValueError:
            return None

    def _notebook(self, file: Path, modified: float | None) -> Notebook | None:
        relative = self._relative(file)
        if relative is None:
            return None
        if relative not in self._ids:
            self._ids[relative] = NotebookId(new_id("nb"))
        return Notebook(
            id=self._ids[relative],
            project_id=self._project_id,
            title=relative.stem,
            path=relative,
            updated_at=(
                None
                if modified is None
                else datetime.fromtimestamp(modified, tz=timezone.utc)
            ),
        )


def _root_of(workspace: NotebookWorkspace) -> Path | None:
    if workspace.directory is not None:
        return Path(workspace.directory)
    single = workspace.single_file()
    if single is not None:
        return Path(single.path).parent
    return None


def _marimo_files(files: list[FileInfo]) -> Iterator[FileInfo]:
    for file in files:
        if file.is_directory:
            yield from _marimo_files(file.children)
        elif file.is_marimo_file:
            yield file
