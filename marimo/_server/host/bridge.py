# Copyright 2026 Marimo. All rights reserved.
"""Workspace notebooks and session updates for the host API."""

from __future__ import annotations

import asyncio
import copy
from typing import TYPE_CHECKING, Any

from marimo import _loggers
from marimo._config.manager import ScriptConfigReader
from marimo._core import protocol
from marimo._core.document import CellSource, Document, revision
from marimo._core.errors import Conflict, EditConflict, NotFound
from marimo._core.executions import Executions
from marimo._core.host import Host
from marimo._core.notebook import Notebook
from marimo._runtime.commands import RenameNotebookCommand
from marimo._server.host import OPERATIONS, document as documents
from marimo._server.host.analysis import HostAnalyzer
from marimo._server.host.backend import SessionBackend
from marimo._server.host.index import WorkspaceIndex
from marimo._session.events import SessionEventListener
from marimo._session.notebook.storage import rename_no_replace

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from marimo._config.manager import MarimoConfigManager
    from marimo._core.backend import Message
    from marimo._core.document import Policy
    from marimo._core.stream import Event, Sink
    from marimo._messaging.notebook import NotebookCell
    from marimo._server.session_manager import SessionManager
    from marimo._session.notebook import AppFileManager
    from marimo._session.session import Session

LOGGER = _loggers.marimo_logger()


def _running_loop() -> asyncio.AbstractEventLoop | None:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None


# NB: The host keeps a separate document to avoid migrating the frontend yet.
# Editor changes are mirrored into it; host edits become session transactions.
# TODO(MO-7927): Remove this adapter when Session consumes the host Notebook.
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
        self._saving: set[protocol.NotebookId] = set()
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
                cells, app_config = documents.from_session(session)
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
        return documents.from_file_manager(self._file_manager(path))

    def _file_manager(self, path: str) -> AppFileManager:
        from marimo._server.app_defaults import AppDefaults
        from marimo._session.notebook import AppFileManager

        defaults = (
            None
            if self._config_manager is None
            else AppDefaults.from_config_manager(self._config_manager)
        )
        return AppFileManager(path, defaults=defaults)

    async def save(
        self,
        notebook_id: str,
        *,
        if_match: Sequence[str] | None,
        request_id: str,
    ) -> protocol.EditResponse:
        """Write the document to its file and record the revision written.

        With a session attached, the session's own file manager writes
        the session's cells, which the document mirrors. Its record of
        the last write then stays true, so its watcher does not take the
        host's write for someone else's and its next write is not
        skipped as unchanged. Without a session, a file manager of the
        host's own writes the document's cells. Either way the file
        keeps its header and app config, and the saved revision is
        computed from the cells and config that were written rather
        than taken from the document, which may have moved on.

        Raises:
            Conflict: If the notebook has no file or the write fails.
            EditConflict: If `if_match` does not name the document's etag.
        """
        notebook = await self.host.notebook(notebook_id)
        async with self._files_lock:
            if self.host.peek_notebook(notebook_id) is not notebook:
                raise NotFound(f"no notebook {notebook_id}")
            file = self.index.file_of(notebook.id)
            if file is None:
                raise Conflict("The notebook has no file to save to")
            # Check and snapshot only after waiting for the file lock.
            snapshot = notebook.document.snapshot()
            if if_match is not None and snapshot.document.etag not in if_match:
                raise EditConflict(
                    "The document has changed since it was read",
                    change=0,
                    cell=None,
                    document=snapshot.document,
                )
            session = self._session_of(notebook.id)
            # TODO(MO-8005): One writer per notebook file, owned by the
            # notebook, replaces the choice of manager here.
            if session is None:
                cells = [documents.to_notebook_cell(c) for c in snapshot.cells]
                manager = None
            else:
                cells = copy.deepcopy(session.document.cells)
                manager = session.app_file_manager
            self._saving.add(notebook.id)
            try:
                etag = await asyncio.to_thread(
                    self._write, str(file), cells, manager
                )
            except Exception as e:
                raise Conflict(f"The notebook cannot be saved: {e}") from e
            finally:
                self._saving.discard(notebook.id)
            document = notebook.mark_saved(etag, request_id=request_id)
            return protocol.EditResponse(document=document, cells={})

    def _write(
        self,
        path: str,
        cells: Sequence[NotebookCell],
        manager: AppFileManager | None,
    ) -> protocol.Etag:
        """Write `cells` to the file and return the revision written.

        The revision covers the cells as passed and the app config the
        manager wrote, not the manager's live cells, which another
        thread may change while the file is written.
        """
        if manager is None:
            manager = self._file_manager(path)
        manager.save_from_cells(cells)
        return revision(
            documents.sources(cells), manager.app.config.asdict_difference()
        )

    async def edit(
        self,
        notebook_id: str,
        changes: Sequence[protocol.Change],
        *,
        request_id: str,
    ) -> protocol.EditResponse:
        """Apply an edit to the document, and to the session when there is one.

        The file is not written. The session mirrors the edit back with
        its own app config, so the response carries the document as it
        stands after that, which is the one the client reads next.

        Raises:
            EditConflict: If a precondition is stale.
            Invalid: If a change could not apply to any state.
        """
        notebook = await self.host.notebook(notebook_id)
        response = notebook.edit(changes, request_id=request_id)
        session = self._session_of(notebook.id)
        if session is None:
            return response
        documents.apply_to_session(session, notebook.document)
        return protocol.EditResponse(
            cells=response.cells, document=notebook.document._record
        )

    def _session_of(self, notebook_id: protocol.NotebookId) -> Session | None:
        backend = self._backends.get(notebook_id)
        return None if backend is None else backend.session

    def _attach_document(self, notebook_id: protocol.NotebookId) -> None:
        """Reconcile the document with a session that just attached.

        Host edits made before the session existed are carried into the
        editor, even when the file changed meanwhile. Without any, the
        session has the file as it is now, so its contents replace the
        host's earlier read and are the saved revision.
        """
        session = self._session_of(notebook_id)
        notebook = self.host.peek_notebook(notebook_id)
        if session is None or notebook is None:
            return
        self._follow_saves(notebook_id, session)
        document = notebook.document
        if document._record.saved_etag != document._record.etag:
            documents.apply_to_session(session, document)
            return
        cells, app_config = documents.from_session(session)
        notebook.replace(cells, app_config, saved=True)

    # TODO(MO-7927): Following the editor's writes ends when the notebook
    # owns persistence and the editor saves through it.
    def _follow_saves(
        self, notebook_id: protocol.NotebookId, session: Session
    ) -> None:
        """Record the editor's writes as the saved revision.

        The file manager reports each write on the writing thread with
        the cells and app config it wrote. The revision is computed
        from those, not from the live document, which may have moved
        on. The editor's save endpoint writes on the event loop and
        autosave on a worker, so the record is made directly in the
        first case and handed to the loop in the second.
        """
        loop = asyncio.get_running_loop()

        def persisted(
            cells: Sequence[NotebookCell], app_config: dict[str, Any]
        ) -> None:
            etag = revision(documents.sources(cells), app_config)
            if _running_loop() is loop:
                self._saved(notebook_id, etag)
            else:
                loop.call_soon_threadsafe(self._saved, notebook_id, etag)

        session.app_file_manager.on_persisted = persisted

    def _detach_document(
        self, notebook_id: protocol.NotebookId, session: Session
    ) -> None:
        del notebook_id
        session.app_file_manager.on_persisted = None

    def _saved(
        self, notebook_id: protocol.NotebookId, etag: protocol.Etag
    ) -> None:
        """Record a write the editor made. A write the host asked for
        is recorded by `save`, under its request."""
        if notebook_id in self._saving:
            return
        try:
            notebook = self.host.peek_notebook(notebook_id)
        except NotFound:
            return
        if notebook is not None:
            notebook.mark_saved(etag)

    def _mirror(self, notebook_id: protocol.NotebookId) -> None:
        """Bring the document up to date with the session's after it changed."""
        session = self._session_of(notebook_id)
        try:
            notebook = self.host.peek_notebook(notebook_id)
        except NotFound:
            return
        if session is None or notebook is None:
            return
        cells, app_config = documents.from_session(session)
        notebook.replace(cells, app_config)

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
            document_changed=lambda: self._mirror(notebook_id),
            session_attached=lambda: self._attach_document(notebook_id),
            session_detached=lambda session: self._detach_document(
                notebook_id, session
            ),
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
