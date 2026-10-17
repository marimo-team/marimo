# Copyright 2026 Marimo. All rights reserved.
"""Workspace notebooks and session updates for the host API."""

from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from marimo import _loggers
from marimo._core import protocol
from marimo._core.document import Document, DocumentCell
from marimo._core.errors import (
    Conflict,
    DecisionRequired,
    Invalid,
    NotFound,
)
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
from marimo._utils.generated_with import (
    contents_differ_excluding_generated_with,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from marimo._config.manager import MarimoConfigManager
    from marimo._core.backend import Message
    from marimo._core.stream import Event, Sink
    from marimo._messaging.notebook import NotebookCell
    from marimo._server.session_manager import SessionManager
    from marimo._session.notebook import AppFileManager
    from marimo._session.session import Session

LOGGER = _loggers.marimo_logger()

_FILE_CHANGED = protocol.Decision(
    id="file",
    prompt="The notebook file changed outside marimo. Overwrite it with the document, or reload the document from it?",
    options=(
        protocol.DecisionOption(id="overwrite", label="Overwrite the file"),
        protocol.DecisionOption(id="reload", label="Reload from the file"),
    ),
)


@dataclass(frozen=True)
class _FileContents:
    """A notebook file as read: its text and the document it parses to."""

    text: str
    cells: list[DocumentCell]
    app_config: dict[str, Any]


def _read_text(file: Path) -> str:
    return file.read_text(encoding="utf-8")


def _texts_differ(text: str, baseline: str) -> bool:
    """Whether two notebook texts differ, as the editor's watcher judges it."""
    if text.strip() == baseline.strip():
        return False
    return contents_differ_excluding_generated_with(text, baseline)


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
        # TODO(MO-8005): The writer owns this baseline once there is one
        # per notebook file; the host keeps it only while it owns the file.
        self._file_texts: dict[protocol.NotebookId, str] = {}
        """Each file's text as the host last read or wrote it, without a session."""
        self._rebaselining: dict[protocol.NotebookId, asyncio.Task[None]] = {}
        self._adopting: dict[protocol.NotebookId, Session] = {}
        # TODO(MO-8005): The response to the session's latest mirror of its
        # app config, for the edit that caused it. Ends with the mirror.
        self._mirrored: dict[protocol.NotebookId, protocol.EditResponse] = {}
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
                cells, app_config = loaded.cells, loaded.app_config
                self._file_texts[record.id] = loaded.text
            document = Document(cells, app_config)
            # Without a session the file is what was read. With one, the
            # editor's document may have moved on from the file.
            saved_etag = document.etag if session is None else None
            if session is not None and loaded is not None:
                saved_etag = Document(loaded.cells, loaded.app_config).etag
            backend = self._make_backend(record.id)
            return Notebook(
                record.id,
                document,
                Executions(),
                backend,
                sink,
                saved_etag=saved_etag,
                analyzer=HostAnalyzer(),
            )

    async def _load(self, file: Path) -> _FileContents | None:
        """Read a notebook file, or return `None` if it cannot be loaded."""
        try:
            return await asyncio.to_thread(self._read, file)
        except Exception as e:
            LOGGER.warning("Could not load %s: %s", file, e)
            return None

    def _read(self, file: Path) -> _FileContents:
        # The text is read first, so that a change landing between the
        # two reads makes the next save ask rather than overwrite.
        text = _read_text(file)
        cells, app_config = documents.from_file_manager(
            self._file_manager(str(file))
        )
        return _FileContents(text, cells, app_config)

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
        decisions: Mapping[str, str] | None = None,
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

        Without a session, the host owns the file and keeps its text as
        last read or written. A file whose text differs from that is
        not overwritten until the client decides to, or asks to reload
        the document from it instead. With a session, the editor owns
        the file and watches it itself.

        Raises:
            Conflict: If the notebook has no file or the write fails.
            EditConflict: If `if_match` does not name the document's etag,
                or the document changed while the file was being read
                for a reload.
            DecisionRequired: If the file changed and `decisions` has no
                answer for it.
            Invalid: If `decisions` has an answer this host does not offer.
        """
        notebook = await self.host.notebook(notebook_id)
        async with self._files_lock:
            if self.host.peek_notebook(notebook_id) is not notebook:
                raise NotFound(f"no notebook {notebook_id}")
            file = self.index.file_of(notebook.id)
            if file is None:
                raise Conflict("The notebook has no file to save to")
            # Check and snapshot only after waiting for the file lock.
            if if_match is not None:
                notebook.require_revision(if_match)
            revision = notebook.document
            session = self._session_of(notebook.id)
            if session is None and await self._file_changed(notebook.id, file):
                answer = (decisions or {}).get(_FILE_CHANGED.id)
                if answer is None:
                    raise DecisionRequired(
                        "The file changed outside marimo",
                        decisions=(_FILE_CHANGED,),
                    )
                if answer == "reload":
                    return await self._reload(
                        notebook, file, revision.etag, request_id
                    )
                if answer != "overwrite":
                    raise Invalid(
                        f"{answer!r} is not an option for {_FILE_CHANGED.id}"
                    )
            # TODO(MO-8005): Move persistence to the notebook, with sessions
            # consuming its events. Until then, save_from_cells on an attached
            # session can replace a concurrent edit with this older snapshot.
            # The notebook's writer must persist snapshots without mutating
            # the live document; cover attached-session edits during a save.
            if session is None:
                cells = [documents.to_notebook_cell(c) for c in revision]
                manager = None
            else:
                cells = copy.deepcopy(session.document.cells)
                manager = session.app_file_manager
            self._saving.add(notebook.id)
            try:
                etag, text = await asyncio.to_thread(
                    self._write, str(file), cells, manager
                )
            except Exception as e:
                raise Conflict(f"The notebook cannot be saved: {e}") from e
            finally:
                self._saving.discard(notebook.id)
            if session is None:
                self._file_texts[notebook.id] = text
            document = notebook.mark_saved(etag, request_id=request_id)
            return protocol.EditResponse(document=document, cells={})

    def _write(
        self,
        path: str,
        cells: Sequence[NotebookCell],
        manager: AppFileManager | None,
    ) -> tuple[protocol.Etag, str]:
        """Write `cells` to the file; return the revision and text written.

        The revision covers the cells as passed and the app config the
        manager wrote, not the manager's live cells, which another
        thread may change while the file is written.
        """
        if manager is None:
            manager = self._file_manager(path)
        text = manager.save_from_cells(cells)
        etag = Document(
            documents.sources(cells), manager.app.config.asdict_difference()
        ).etag
        return etag, text

    async def _file_changed(
        self, notebook_id: protocol.NotebookId, file: Path
    ) -> bool:
        """Whether the file's text differs from what the host last read or wrote.

        Without a baseline, require a decision. A failed read cannot
        establish that overwriting the file is safe, so refuse the save.
        """
        pending = self._rebaselining.get(notebook_id)
        if pending is not None:
            await pending
            self._rebaselining.pop(notebook_id, None)
        baseline = self._file_texts.get(notebook_id)
        if baseline is None:
            return True
        try:
            text = await asyncio.to_thread(_read_text, file)
        except (OSError, UnicodeError) as e:
            raise Conflict("The notebook file could not be read") from e
        return _texts_differ(text, baseline)

    async def _reload(
        self,
        notebook: Notebook,
        file: Path,
        before: protocol.Etag,
        request_id: str,
    ) -> protocol.EditResponse:
        """Replace the document with the file's contents as the saved revision."""
        loaded = await self._load(file)
        if loaded is None:
            raise Conflict("The notebook file could not be loaded")
        # An edit may have landed while the file was read. Replacing the
        # document now would lose it.
        notebook.require_revision([before])
        self._file_texts[notebook.id] = loaded.text
        return notebook.replace(
            loaded.cells, loaded.app_config, saved=True, request_id=request_id
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
        self._mirrored.pop(notebook.id, None)
        documents.apply_to_session(session, notebook.document)
        mirrored = self._mirrored.pop(notebook.id, None)
        if mirrored is None:
            return response
        return protocol.EditResponse(
            cells=response.cells, document=mirrored.document
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
        # The editor owns the file now; a baseline being read for the
        # host is no longer wanted.
        self._rebaselining.pop(notebook_id, None)
        self._follow_saves(notebook_id, session)
        if notebook.saved_etag != notebook.document.etag:
            documents.apply_to_session(session, notebook.document)
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
            etag = Document(documents.sources(cells), app_config).etag
            if _running_loop() is loop:
                self._saved(notebook_id, etag)
            else:
                loop.call_soon_threadsafe(self._saved, notebook_id, etag)

        session.app_file_manager.on_persisted = persisted

    def _detach_document(
        self, notebook_id: protocol.NotebookId, session: Session
    ) -> None:
        """Stop following the editor's writes; the host owns the file again.

        Its baseline for external changes is the file as the editor
        left it, read off the event loop before the next save compares.
        """
        session.app_file_manager.on_persisted = None
        self._rebaselining[notebook_id] = (
            asyncio.get_running_loop().create_task(
                self._rebaseline(notebook_id)
            )
        )

    async def _rebaseline(self, notebook_id: protocol.NotebookId) -> None:
        file = self.index.file_of(notebook_id)
        try:
            text = (
                None
                if file is None
                else await asyncio.to_thread(_read_text, file)
            )
        except OSError:
            text = None
        # A session that attached meanwhile owns the file again and has
        # dropped this task from the pending ones.
        if self._rebaselining.get(notebook_id) is not asyncio.current_task():
            return
        if text is None:
            self._file_texts.pop(notebook_id, None)
        else:
            self._file_texts[notebook_id] = text

    def _saved(
        self, notebook_id: protocol.NotebookId, etag: protocol.Etag
    ) -> None:
        """Record a write the editor made.

        A write the host asked for is recorded by `save`, under its
        request, so it is not recorded here as well.
        """
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
        self._mirrored[notebook_id] = notebook.replace(cells, app_config)

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
            self._file_texts.pop(event.notebook_id, None)
            self._rebaselining.pop(event.notebook_id, None)
            self._mirrored.pop(event.notebook_id, None)

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
