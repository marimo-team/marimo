# Copyright 2026 Marimo. All rights reserved.
"""Workspace notebooks and session updates for the host API."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from marimo import _loggers
from marimo._config.manager import ScriptConfigReader
from marimo._core import protocol
from marimo._core.document import CellSource, Document, revision
from marimo._core.errors import Conflict, NotFound
from marimo._core.executions import Executions
from marimo._core.host import Host
from marimo._core.notebook import Notebook
from marimo._runtime.commands import RenameNotebookCommand
from marimo._server.host import OPERATIONS
from marimo._server.host.analysis import HostAnalyzer
from marimo._server.host.backend import SessionBackend
from marimo._server.host.index import WorkspaceIndex
from marimo._session.events import SessionEventListener
from marimo._session.notebook.storage import rename_no_replace

if TYPE_CHECKING:
    from pathlib import Path

    from marimo._ast.cell import CellConfig
    from marimo._config.manager import MarimoConfigManager
    from marimo._core.backend import Message
    from marimo._core.document import Policy
    from marimo._core.stream import Event, Sink
    from marimo._server.session_manager import SessionManager
    from marimo._session.notebook import AppFileManager
    from marimo._session.session import Session

LOGGER = _loggers.marimo_logger()


# TODO: Remove once sessions consume host-owned notebooks.
class SessionBridge(SessionEventListener):
    """Connect a host's notebook catalog to a session manager."""

    def __init__(
        self,
        manager: SessionManager,
        config_manager: MarimoConfigManager | None = None,
    ) -> None:
        self._manager = manager
        self._config_manager = config_manager
        self._files_lock = asyncio.Lock()
        self._adopting: dict[protocol.NotebookId, Session] = {}
        self.host = Host(operations=OPERATIONS)
        self._backends: dict[protocol.NotebookId, SessionBackend] = {}
        self.index = WorkspaceIndex(
            self.host, manager.workspace, self._initialize_notebook
        )
        self._unsubscribe = self.host.subscribe(
            self._forget_backend, types={"notebook"}
        )

    async def open(self) -> None:
        """Index notebooks, adopt sessions, and subscribe to session events."""
        self.index.refresh()
        self._manager.event_bus.subscribe(self)
        for session in list(self._manager.sessions.values()):
            await self._adopt(session)

    def close(self) -> None:
        self._manager.event_bus.unsubscribe(self)
        self._unsubscribe()

    async def refresh(self) -> None:
        """Refresh the catalog without observing a half-finished file move."""
        async with self._files_lock:
            await self.index.refresh_async()

    async def _initialize_notebook(
        self, record: protocol.Notebook, sink: Sink
    ) -> Notebook:
        """Read the document and construct its notebook."""
        async with self._files_lock:
            file = self.index.file_of(record.id)
            loaded = None if file is None else await self._load(file)
            session = self._adopting.get(record.id)
            if session is None:
                for candidate in self._manager.sessions.values():
                    candidate_record = self.index.notebook_for(
                        candidate.app_file_manager.path
                    )
                    if (
                        candidate_record is not None
                        and candidate_record.id == record.id
                    ):
                        session = candidate
                        break
            if session is not None:
                cells, app_config = _from_session(session)
            else:
                if loaded is None:
                    raise Conflict("The notebook document could not be loaded")
                cells, app_config = loaded
            document = Document(
                record.id,
                cells,
                app_config,
                policy=self._policy(file, session),
                saved=session is None,
            )
            if session is not None and loaded is not None:
                document.mark_saved(revision(*loaded))
            backend = self._make_backend(record.id)
            return Notebook(
                document,
                Executions(),
                backend,
                sink,
                analyzer=HostAnalyzer(),
            )

    async def _load(
        self, file: Path
    ) -> tuple[list[CellSource], dict[str, Any]] | None:
        """Read a notebook file, or return `None` if it cannot be loaded."""
        try:
            return await asyncio.to_thread(self._read, str(file))
        except Exception as e:
            LOGGER.warning("Could not load %s: %s", file, e)
            return None

    def _read(self, path: str) -> tuple[list[CellSource], dict[str, Any]]:
        from marimo._server.app_defaults import AppDefaults
        from marimo._session.notebook import AppFileManager

        defaults = (
            None
            if self._config_manager is None
            else AppDefaults.from_config_manager(self._config_manager)
        )
        return _from_file_manager(AppFileManager(path, defaults=defaults))

    def _policy(self, file: Path | None, session: Session | None) -> Policy:
        config_manager = (
            session.config_manager
            if session is not None
            else self._config_manager
        )
        if config_manager is None:
            return "autorun"
        if session is None:
            config_manager = config_manager.with_partial(
                ScriptConfigReader(None if file is None else str(file))
            )
        policy = config_manager.get_config()["runtime"]["on_cell_change"]
        return "lazy" if policy == "lazy" else "autorun"

    def _project_path(self, path: Path) -> Path:
        root = self.index.root
        if root is None:
            raise Conflict("The project has no directory")
        resolved = path.resolve()
        if not resolved.is_relative_to(root.resolve()):
            raise Conflict("The path must stay in the project")
        return resolved

    async def create(
        self, target: Path, *, name: str | None, request_id: str
    ) -> protocol.Notebook:
        """Create a notebook only after validating its destination."""
        from marimo._convert.converters import MarimoConvert
        from marimo._session.notebook import AppFileManager

        def write() -> None:
            file = self._project_path(target)
            if target.is_symlink():
                raise Conflict(f"{target.name} already exists")
            file.parent.mkdir(parents=True, exist_ok=True)
            content = MarimoConvert.from_ir(
                AppFileManager(None).app.to_ir()
            ).to_py()
            with file.open("x", encoding="utf-8") as output:
                output.write(content)

        async with self._files_lock:
            try:
                await asyncio.to_thread(write)
            except OSError as e:
                raise Conflict(f"The notebook cannot be created: {e}") from e
            notebook = self.index.ensure(str(target), request_id=request_id)
            assert notebook is not None
            if name is not None:
                self.index.rename(notebook.id, name, request_id=request_id)
            return self.host.notebooks[notebook.id]

    async def update(
        self,
        notebook_id: protocol.NotebookId,
        *,
        target: Path | None = None,
        name: str | None = None,
        request_id: str,
    ) -> protocol.Notebook:
        """Update a notebook's file and label, preserving its runtime."""
        async with self._files_lock:
            self.host.peek_notebook(notebook_id)
            if target is not None:
                await self._move(notebook_id, target, request_id=request_id)
            if name is not None:
                self.index.rename(notebook_id, name, request_id=request_id)
            return self.host.notebooks[notebook_id]

    async def delete(
        self, notebook_id: protocol.NotebookId, *, request_id: str
    ) -> None:
        """Remove a notebook without a runtime and its backing file."""
        async with self._files_lock:
            notebook = self.host.peek_notebook(notebook_id)
            if notebook_id in self._adopting or (
                notebook is not None and notebook.runtime is not None
            ):
                raise Conflict("The notebook has a runtime")
            file = self.index.file_of(notebook_id)
            if file is not None:
                try:
                    self._project_path(file)
                    file.unlink(missing_ok=True)
                except OSError as e:
                    raise Conflict(f"The file cannot be removed: {e}") from e
            self.index.forget(notebook_id, request_id=request_id)

    async def _move(
        self,
        notebook_id: protocol.NotebookId,
        target: Path,
        *,
        request_id: str,
    ) -> None:
        source = self.index.file_of(notebook_id)
        if source is None:
            raise Conflict("The notebook has no file to move")
        target = await asyncio.to_thread(self._project_path, target)
        if await asyncio.to_thread(target.exists):
            raise Conflict(f"{target.name} already exists")
        backend = self._backends.get(notebook_id)
        session = None if backend is None else backend.session
        session_id = next(
            (
                sid
                for sid, candidate in self._manager.sessions.items()
                if candidate is session
            ),
            None,
        )
        try:
            await asyncio.to_thread(
                target.parent.mkdir, parents=True, exist_ok=True
            )
            if session_id is None:
                await asyncio.to_thread(rename_no_replace, source, target)
            else:
                ok, error = await self._manager.rename_session(
                    session_id, str(target)
                )
                if not ok:
                    raise Conflict(error or "The notebook cannot be moved")
                assert session is not None
                session.put_control_request(
                    RenameNotebookCommand(filename=str(target)),
                    from_consumer_id=None,
                )
        except OSError as e:
            raise Conflict(f"The notebook cannot be moved: {e}") from e
        self.index.moved(notebook_id, str(target), request_id=request_id)

    def _make_backend(
        self, notebook_id: protocol.NotebookId
    ) -> SessionBackend:
        def file() -> str | None:
            path = self.index.file_of(notebook_id)
            return None if path is None else str(path)

        def observe(message: Message) -> None:
            try:
                notebook = self.host.peek_notebook(notebook_id)
            except NotFound:
                # Sessions can report shutdown after their catalog removal.
                return
            if notebook is not None:
                notebook.observe(message)

        backend = SessionBackend(
            notebook_id,
            file,
            self._manager,
            observe,
        )
        self._backends[notebook_id] = backend
        return backend

    def _forget_backend(self, event: Event) -> None:
        if event.name == "notebook.removed" and event.notebook_id is not None:
            self._backends.pop(event.notebook_id, None)

    async def _adopt(self, session: Session) -> None:
        path = session.app_file_manager.path
        notebook = self.index.notebook_for(path)
        if notebook is None and path is not None:
            notebook = self.index.ensure(path)
        if notebook is None:
            LOGGER.debug("Not publishing session for %s", path)
            return
        if self._adopting.setdefault(notebook.id, session) is not session:
            return
        try:
            loaded = await self.host.notebook(notebook.id)
        finally:
            self._adopting.pop(notebook.id, None)
        backend = self._backends[notebook.id]
        if backend.session is not None:
            return
        try:
            loaded.adopt(lambda runtime_id: backend.adopt(runtime_id, session))
        except Conflict:
            LOGGER.debug("Not publishing a second session for %s", path)
            return

    # Session events

    async def on_session_created(self, session: Session) -> None:
        await self._adopt(session)

    async def on_session_notebook_renamed(
        self, session: Session, old_path: str | None
    ) -> None:
        notebook = self.index.notebook_for(old_path)
        path = session.app_file_manager.path
        if path is None:
            return
        if notebook is None:
            # Add notebooks to the catalog when first saved.
            await self._adopt(session)
            return
        self.index.moved(notebook.id, path)


def _from_session(session: Session) -> tuple[list[CellSource], dict[str, Any]]:
    cells = [
        CellSource(cell.id, cell.code, cell.name, _config(cell.config))
        for cell in session.document.cells
    ]
    return cells, session.app_file_manager.app.config.asdict_difference()


def _from_file_manager(
    manager: AppFileManager,
) -> tuple[list[CellSource], dict[str, Any]]:
    cells = [
        CellSource(data.cell_id, data.code, data.name, _config(data.config))
        for data in manager.app.cell_manager.cell_data()
    ]
    return cells, manager.app.config.asdict_difference()


def _config(config: CellConfig) -> protocol.CellConfig:
    return protocol.CellConfig(
        column=config.column,
        disabled=config.disabled,
        hide_code=config.hide_code,
        expand_output=config.expand_output,
    )
