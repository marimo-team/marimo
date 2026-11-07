# Copyright 2026 Marimo. All rights reserved.
"""Workspace files and explicitly opened notebooks in the host catalog.

Notebook IDs persist across rescans and recorded file moves.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from msgspec.structs import replace

from marimo._core import protocol
from marimo._core.ids import mint
from marimo._server.host import OPERATIONS
from marimo._server.workspace import flatten_files

if TYPE_CHECKING:
    from marimo._core.host import Host, NotebookInitializer
    from marimo._server.models.files import FileInfo
    from marimo._server.workspace import NotebookWorkspace

_TRUNCATED = "The scan stopped at its depth, file count, or time limit"


class WorkspaceIndex:
    """Workspace files and explicitly opened files exposed as host notebooks."""

    def __init__(
        self,
        host: Host,
        workspace: NotebookWorkspace,
        initialize: NotebookInitializer,
    ) -> None:
        self._host = host
        self._initialize = initialize
        self._workspace = workspace
        self._root = _root_of(workspace)
        self.project_id = mint(protocol.ProjectId, "proj")
        self._ids: dict[Path, protocol.NotebookId] = {}
        self._open_project_id: protocol.ProjectId | None = None
        self._open_files: dict[protocol.NotebookId, Path] = {}
        self._names: dict[protocol.NotebookId, str] = {}
        """Client-selected names preserved across rescans."""
        self._refresh_lock = asyncio.Lock()

    @property
    def root(self) -> Path | None:
        """The project directory, if the workspace has one."""
        return self._root

    def refresh(self) -> None:
        """Rescan notebook files and publish catalog changes.

        Keep unlisted notebooks while their files still exist, since scans
        may be incomplete.
        """
        self._apply_scan(*self._scan())

    async def refresh_async(self) -> None:
        """Scan off-thread, then apply catalog changes on the event loop."""
        async with self._refresh_lock:
            files, truncated = await asyncio.to_thread(self._scan)
            self._apply_scan(files, truncated)

    def _scan(self) -> tuple[list[FileInfo], bool]:
        self._workspace.invalidate()
        files = [
            f for f in flatten_files(self._workspace.files) if f.is_marimo_file
        ]
        return files, self._workspace.is_truncated

    def _apply_scan(self, files: list[FileInfo], truncated: bool) -> None:
        self._host.update_project(
            protocol.Project(
                id=self.project_id,
                name="workspace" if self._root is None else self._root.name,
                root=None if self._root is None else str(self._root),
                status="partial" if truncated else "indexed",
                message=_TRUNCATED if truncated else None,
                operations=tuple(OPERATIONS),
            )
        )
        seen: set[protocol.NotebookId] = set()
        for file in files:
            notebook = self._publish(Path(file.path), file.last_modified)
            if notebook is not None:
                seen.add(notebook.id)
        for notebook in list(self._host.notebooks.values()):
            if notebook.project_id != self.project_id:
                continue
            if notebook.id in seen or self._exists(notebook):
                continue
            loaded = self._host.peek_notebook(notebook.id)
            if loaded is not None and loaded.runtime is not None:
                self._host.update_notebook(
                    replace(notebook, path=None, updated_at=None)
                )
            else:
                self.forget(notebook.id)

    def ensure(
        self, path: str, *, request_id: str | None = None
    ) -> protocol.Notebook | None:
        """Add or update a notebook file under the project root.

        Return `None` if the file is missing or outside the project.
        """
        file = Path(path)
        try:
            modified: float | None = file.stat().st_mtime
        except OSError:
            return None
        return self._publish(file, modified, request_id=request_id)

    def register_open_notebook(self, path: str) -> protocol.Notebook:
        """Register an authorized file, including files outside the workspace."""
        resolved = self._workspace.resolve(path)
        if resolved is None:
            raise RuntimeError("Notebook path could not be resolved")
        existing = self.notebook_for(resolved) or self.ensure(resolved)
        if existing is not None:
            return existing
        return self._publish_open_notebook(
            mint(protocol.NotebookId, "nb"), Path(resolved)
        )

    def _publish_open_notebook(
        self,
        notebook_id: protocol.NotebookId,
        file: Path,
        *,
        request_id: str | None = None,
    ) -> protocol.Notebook:
        if self._open_project_id is None:
            self._open_project_id = mint(protocol.ProjectId, "proj")
            self._host.update_project(
                protocol.Project(
                    id=self._open_project_id,
                    name="Open notebooks",
                    root=None,
                    status="indexed",
                    message=None,
                    operations=(),
                )
            )
        record = protocol.Notebook(
            id=notebook_id,
            project_id=self._open_project_id,
            path=None,
            name=self._names.get(notebook_id, file.stem),
            operations=tuple(
                op
                for op in OPERATIONS
                if op
                not in {
                    "notebook.create",
                    "notebook.update",
                    "notebook.delete",
                }
            ),
            updated_at=None,
        )
        self._open_files[record.id] = file
        if notebook_id in self._host.notebooks:
            self._host.update_notebook(record, request_id=request_id)
        else:
            self._host.add_notebook(record, self._initialize)
        return record

    def untitled(self) -> protocol.Notebook:
        """Register an editor document before it has a file."""
        record = protocol.Notebook(
            id=mint(protocol.NotebookId, "nb"),
            project_id=self.project_id,
            path=None,
            name="Untitled",
            operations=("notebook.edit",),
            updated_at=None,
        )
        self._host.add_notebook(record, self._initialize)
        return record

    def moved(
        self,
        notebook_id: protocol.NotebookId,
        path: str,
        *,
        request_id: str | None = None,
    ) -> protocol.Notebook:
        """Update a notebook's file path, keeping its ID.

        Files outside the workspace belong to the Open notebooks project.
        """
        relative = self._relative(Path(path))
        for old, known in list(self._ids.items()):
            if known == notebook_id:
                del self._ids[old]
        if relative is None:
            return self._publish_open_notebook(
                notebook_id, Path(path).resolve(), request_id=request_id
            )
        self._open_files.pop(notebook_id, None)
        self._ids[relative] = notebook_id
        if self._root is None:
            raise RuntimeError("Workspace root is not initialized")
        file = self._root / relative
        try:
            modified: float | None = file.stat().st_mtime
        except OSError:
            modified = None
        record = self._publish(file, modified, request_id=request_id)
        if record is None:
            raise RuntimeError("Notebook record could not be published")
        return record

    def rename(
        self,
        notebook_id: protocol.NotebookId,
        name: str,
        *,
        request_id: str | None = None,
    ) -> None:
        """Set a notebook's display name independently of its filename."""
        record = self._host.notebooks[notebook_id]
        self._names[notebook_id] = name
        self._host.update_notebook(
            replace(record, name=name), request_id=request_id
        )

    def forget(
        self,
        notebook_id: protocol.NotebookId,
        *,
        request_id: str | None = None,
    ) -> None:
        """Discard a notebook's catalog entry, stored ID, and display name."""
        for path, known in list(self._ids.items()):
            if known == notebook_id:
                del self._ids[path]
        self._names.pop(notebook_id, None)
        self._open_files.pop(notebook_id, None)
        self._host.remove_notebook(notebook_id, request_id=request_id)

    def notebook_for(self, path: str | None) -> protocol.Notebook | None:
        """Look up a cataloged notebook by file path."""
        if path is None:
            return None
        for notebook_id, file in self._open_files.items():
            if file.resolve() == Path(path).resolve():
                return self._host.notebooks[notebook_id]
        relative = self._relative(Path(path))
        if relative is None or relative not in self._ids:
            return None
        return self._host.notebooks.get(self._ids[relative])

    def file_of(self, notebook_id: protocol.NotebookId) -> Path | None:
        """Return a notebook's absolute file path, if available."""
        if notebook_id in self._open_files:
            return self._open_files[notebook_id]
        record = self._host.notebooks.get(notebook_id)
        if record is None or record.path is None or self._root is None:
            return None
        return self._root / record.path

    def _publish(
        self,
        file: Path,
        modified: float | None,
        *,
        request_id: str | None = None,
    ) -> protocol.Notebook | None:
        relative = self._relative(file)
        if relative is None:
            return None
        notebook_id = self._ids.get(relative)
        if notebook_id is None:
            notebook_id = mint(protocol.NotebookId, "nb")
            self._ids[relative] = notebook_id
        record = protocol.Notebook(
            id=notebook_id,
            project_id=self.project_id,
            path=str(relative),
            name=self._names.get(notebook_id, relative.stem),
            operations=tuple(
                op for op in OPERATIONS if op != "notebook.create"
            ),
            updated_at=None
            if modified is None
            else datetime.fromtimestamp(modified, tz=UTC),
        )
        if notebook_id in self._host.notebooks:
            self._host.update_notebook(record, request_id=request_id)
        else:
            self._host.add_notebook(
                record, self._initialize, request_id=request_id
            )
        return record

    def _exists(self, notebook: protocol.Notebook) -> bool:
        file = self.file_of(notebook.id)
        return file is not None and file.exists()

    def _relative(self, file: Path) -> Path | None:
        """Return the root-relative path, or `None` outside the project."""
        if self._root is None:
            return None
        if not file.is_absolute():
            file = self._root / file
        try:
            return file.resolve().relative_to(self._root.resolve())
        except ValueError:
            return None


def _root_of(workspace: NotebookWorkspace) -> Path | None:
    if workspace.directory is not None:
        return Path(workspace.directory)
    single = workspace.single_file()
    if single is not None:
        return Path(single.path).parent
    return None
