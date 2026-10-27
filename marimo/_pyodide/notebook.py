# Copyright 2026 Marimo. All rights reserved.
"""The worker's host document, commands, and event subscriptions."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import msgspec

from marimo._core import protocol
from marimo._core.calls import OperationCall, dispatch
from marimo._core.document import Document
from marimo._core.errors import Conflict, Forbidden, Invalid
from marimo._core.executions import Executions
from marimo._core.host import Host
from marimo._core.ids import mint
from marimo._core.notebook import Notebook
from marimo._core.operations import Mutations, problem
from marimo._messaging.notebook import NotebookDocument, Transaction
from marimo._messaging.notebook.reconcile import reconcile_transaction
from marimo._messaging.notification import (
    NotebookDocumentTransactionNotification,
)
from marimo._messaging.serde import (
    deserialize_kernel_message,
    serialize_kernel_message,
)
from marimo._pyodide.kernel_ready import kernel_ready
from marimo._runtime.layout.layout import (
    LayoutConfig,
    layout_config_to_data_uri,
)
from marimo._server.host import document as documents
from marimo._server.host.events import notification_event, serialize_event
from marimo._server.models.models import NotebookDocumentTransactionRequest
from marimo._session.model import SessionMode
from marimo._session.notebook.writer import NotebookWriter, cells_to_ir

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping, Sequence
    from typing import Any

    from marimo._core.stream import Sink
    from marimo._messaging.notification import NotificationMessage
    from marimo._messaging.types import KernelMessage
    from marimo._pyodide.pyodide_session import PyodideSession


class _DocumentRuntime:
    """Runtime operations are not exposed by the worker host yet."""

    def start(self, runtime_id: protocol.RuntimeId) -> None:
        raise NotImplementedError("Worker runtime operations are not exposed")

    def stop(self, runtime_id: protocol.RuntimeId) -> None:
        raise NotImplementedError("Worker runtime operations are not exposed")

    def run(self, run_id: protocol.RunId, code: str) -> None:
        raise NotImplementedError("Worker runtime operations are not exposed")

    def run_cells(
        self,
        run_id: protocol.RunId,
        document: Document,
        cell_ids: Sequence[protocol.CellId],
    ) -> None:
        raise NotImplementedError("Worker runtime operations are not exposed")

    def interrupt(self, run_id: protocol.RunId) -> None:
        raise NotImplementedError("Worker runtime operations are not exposed")

    def forget(self, run_id: protocol.RunId) -> None:
        pass


class PyodideNotebook:
    """One session's notebook, independent of the worker RPC and React."""

    def __init__(self, session: PyodideSession) -> None:
        self._session = session
        self._subscriptions: dict[str, Callable[[], None]] = {}
        self._closed = False
        self._save_lock = asyncio.Lock()
        self._persist: Callable[[str, str], Awaitable[None]] | None = None
        self.host = Host(operations=("notebook.edit", "notebook.save"))
        project_id = mint(protocol.ProjectId, "p")
        self.id = mint(protocol.NotebookId, "n")
        self.host.update_project(
            protocol.Project(
                id=project_id,
                name="WASM",
                root=None,
                operations=(),
                status="indexed",
                message=None,
            )
        )
        filename = session.app_manager.filename
        self.host.add_notebook(
            protocol.Notebook(
                id=self.id,
                project_id=project_id,
                name=Path(filename).name if filename else "Untitled",
                path=None,
                updated_at=None,
                operations=("notebook.edit", "notebook.save")
                if session.mode is SessionMode.EDIT
                else (),
            ),
            self._initialize,
        )

        self.mutations = Mutations(self.host)

    def _initialize(self, record: protocol.Notebook, sink: Sink) -> Notebook:
        cells, config = documents.from_file_manager(self._session.app_manager)
        document = Document(cells, config)
        return Notebook(
            record.id,
            document,
            Executions(),
            _DocumentRuntime(),
            sink,
            saved_etag=document.etag,
        )

    def refresh(self) -> None:
        """Observe changes from session operations not yet exposed by the host."""
        if self._closed:
            return
        notebook = self.host.peek_notebook(self.id)
        if notebook is not None:
            cells, config = documents.from_file_manager(
                self._session.app_manager
            )
            notebook.replace(cells, config)

    async def subscribe(
        self,
        subscription_id: str,
        cursor: str | None,
        emit: Callable[[str], None],
    ) -> None:
        if self._closed:
            raise RuntimeError("The notebook is closed")
        await self.host.notebook(self.id)
        if self._closed:
            raise RuntimeError("The notebook is closed")
        self.refresh()
        self.unsubscribe(subscription_id)

        def notify(notification: NotificationMessage) -> None:
            emit(serialize_event(notification_event(self.id, notification)))

        def consume(message: KernelMessage) -> None:
            notify(deserialize_kernel_message(message))

        # Snapshot and subscriptions are established in the same event-loop turn.
        initial = self.host.events(cursor, notebook_id=self.id)
        unsubscribe = self.host.subscribe(
            lambda event: emit(serialize_event(event)),
            notebook_id=self.id,
        )
        session = self._session
        session.consumers.append(consume)

        def close() -> None:
            unsubscribe()
            session.consumers.remove(consume)

        self._subscriptions[subscription_id] = close
        try:
            for event in initial:
                emit(serialize_event(event))
            # As on a server connection, kernel-ready and the session's
            # retained notifications follow the snapshot.
            view = session.session_view
            notify(
                kernel_ready(
                    session.app_manager, view if session.instantiated else None
                )
            )
            for notification in view.snapshot_notifications():
                notify(notification)
        except BaseException:
            self.unsubscribe(subscription_id)
            raise

    def unsubscribe(self, subscription_id: str) -> None:
        unsubscribe = self._subscriptions.pop(subscription_id, None)
        if unsubscribe is not None:
            unsubscribe()

    async def call(self, raw: str) -> str:
        """Serve an operation call and reply with its status and body."""
        self.mutations.expire()
        body: msgspec.Struct | None
        try:
            call = msgspec.json.decode(raw, type=OperationCall)
        except msgspec.DecodeError as e:
            failure = problem(400, "invalid-request", str(e))
            status, body = failure.status, failure
        else:
            status, body = await dispatch(self.mutations, self, call)
        return msgspec.json.encode({"status": status, "body": body}).decode()

    async def edit(
        self,
        notebook_id: str,
        changes: Sequence[protocol.Change],
        *,
        request_id: str,
    ) -> protocol.EditResponse:
        notebook = await self.host.notebook(notebook_id)
        self.refresh()
        result = notebook.edit(changes, request_id=request_id)
        self._apply_to_session(notebook, notify=True)
        return result

    def _apply_to_session(self, notebook: Notebook, *, notify: bool) -> None:
        transaction, update = documents.apply_to_document(
            self._session.app_manager.app.cell_manager.document,
            notebook.document,
        )
        if transaction is not None and notify:
            self._session._on_message(
                serialize_kernel_message(
                    NotebookDocumentTransactionNotification(
                        transaction=transaction
                    )
                )
            )
        # Before instantiation the kernel receives the latest app cells.
        if update is not None and self._session.instantiated:
            self._session.put_control_request(update)

    async def transaction(self, raw: str) -> None:
        """Apply the editor's incremental transactions to the host document."""
        if self._session.mode is not SessionMode.EDIT:
            raise Forbidden("The notebook is read-only")
        request = msgspec.json.decode(
            raw, type=NotebookDocumentTransactionRequest
        )
        notebook = await self.host.notebook(self.id)
        self.refresh()
        staged = NotebookDocument(
            documents.to_notebook_cell(cell) for cell in notebook.document
        )
        changes = reconcile_transaction(tuple(request.changes), staged)
        staged.apply(Transaction(changes=changes, source="frontend"))
        notebook.replace(
            documents.sources(staged.cells), notebook.document.app_config
        )
        # Echoing an acknowledged edit could overwrite newer local typing.
        self._apply_to_session(notebook, notify=False)

    async def update_config(self, config: dict[str, Any]) -> None:
        notebook = await self.host.notebook(self.id)
        self._session.app_manager.app.update_config(config)
        notebook.replace(
            list(notebook.document),
            self._session.app_manager.app.config.asdict_difference(),
        )

    async def set_layout(self, raw: str) -> None:
        layout = msgspec.json.decode(raw, type=LayoutConfig | None)
        # Inline layouts survive URL/local-storage reloads along with the source.
        await self.update_config(
            {
                "layout_file": layout_config_to_data_uri(layout)
                if layout
                else None,
            }
        )

    def set_persistence(
        self, persist: Callable[[str, str], Awaitable[None]]
    ) -> None:
        self._persist = persist

    async def save(
        self,
        notebook_id: str,
        *,
        if_match: Sequence[str] | None,
        decisions: Mapping[str, str],
        request_id: str,
    ) -> protocol.EditResponse:
        notebook = await self.host.notebook(notebook_id)
        async with self._save_lock:
            if decisions:
                raise Invalid("Worker saves do not require decisions")
            if self._persist is None:
                raise Conflict("Notebook persistence is unavailable")
            if if_match is not None:
                notebook.require_revision(if_match)
            revision = notebook.document
            manager = self._session.app_manager
            path = Path(manager.filename or "notebook.py")
            ir = cells_to_ir(
                (documents.to_notebook_cell(cell) for cell in revision),
                revision.app_config,
                header=manager.app._app._header,
            )
            try:
                contents = NotebookWriter().write_ir(
                    path, notebook=ir, persist=False
                )
                await self._persist(contents, str(path))
            except Exception as e:
                raise Conflict(f"The notebook cannot be saved: {e}") from e
            document = notebook.mark_saved(
                revision.etag, request_id=request_id
            )
            return protocol.EditResponse(document=document, cells={})

    def close(self) -> None:
        self._closed = True
        for subscription_id in list(self._subscriptions):
            self.unsubscribe(subscription_id)
        self.mutations.replies.clear()
        self.host.remove_notebook(self.id)
