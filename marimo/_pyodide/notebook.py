# Copyright 2026 Marimo. All rights reserved.
"""The worker's host document, commands, and event subscriptions."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import msgspec

from marimo._core import protocol
from marimo._core.calls import OperationCall, dispatch
from marimo._core.document import Document
from marimo._core.executions import Executions
from marimo._core.host import Host
from marimo._core.ids import mint
from marimo._core.notebook import Notebook
from marimo._core.operations import Mutations, problem
from marimo._messaging.notification import (
    NotebookDocumentTransactionNotification,
)
from marimo._messaging.serde import serialize_kernel_message
from marimo._server.host import document as documents
from marimo._server.host.events import serialize_event
from marimo._session.model import SessionMode

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from marimo._core.stream import Sink
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
        self.host = Host(operations=("notebook.edit",))
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
                operations=("notebook.edit",)
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

    def refresh(self, *, saved: bool = False) -> None:
        """Observe writes through the existing session while it still owns saves."""
        if self._closed:
            return
        notebook = self.host.peek_notebook(self.id)
        if notebook is not None:
            cells, config = documents.from_file_manager(
                self._session.app_manager
            )
            notebook.replace(cells, config, saved=saved)

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
        # Snapshot and subscription are established in the same event-loop turn.
        initial = self.host.events(cursor, notebook_id=self.id)
        self._subscriptions[subscription_id] = self.host.subscribe(
            lambda event: emit(serialize_event(event)),
            notebook_id=self.id,
        )
        try:
            for event in initial:
                emit(serialize_event(event))
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
        transaction, update = documents.apply_to_document(
            self._session.app_manager.app.cell_manager.document,
            notebook.document,
        )
        if transaction is not None:
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
        return result

    async def save(
        self,
        notebook_id: str,
        *,
        if_match: Sequence[str] | None,
        decisions: Mapping[str, str],
        request_id: str,
    ) -> protocol.EditResponse:
        raise NotImplementedError("Worker saves are not exposed yet")

    def close(self) -> None:
        self._closed = True
        for subscription_id in list(self._subscriptions):
            self.unsubscribe(subscription_id)
        self.mutations.replies.clear()
        self.host.remove_notebook(self.id)
