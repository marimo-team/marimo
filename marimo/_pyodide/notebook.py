# Copyright 2026 Marimo. All rights reserved.
"""The worker's host document, commands, and event subscriptions."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import msgspec

from marimo import _loggers
from marimo._core import backend as be, protocol
from marimo._core.calls import OperationCall, dispatch
from marimo._core.document import Document
from marimo._core.errors import Conflict, Invalid, NotFound
from marimo._core.executions import Executions
from marimo._core.host import Host
from marimo._core.ids import mint
from marimo._core.notebook import Notebook
from marimo._core.operations import Mutations, problem
from marimo._messaging.input import InputReply
from marimo._messaging.notebook.outputs import scratchpad_snapshot
from marimo._messaging.notification import (
    NotebookDocumentTransactionNotification,
)
from marimo._messaging.serde import (
    deserialize_kernel_message,
    serialize_kernel_message,
)
from marimo._pyodide.kernel_ready import kernel_ready
from marimo._runtime.commands import (
    CancelRunCommand,
    ExecuteCellCommand,
    ExecuteCellsCommand,
    ExecuteScratchpadCommand,
)
from marimo._runtime.context.kernel_context import KernelRuntimeContext
from marimo._runtime.context.types import safe_get_context
from marimo._runtime.layout.layout import (
    LayoutConfig,
    layout_config_to_data_uri,
)
from marimo._server.host import document as documents
from marimo._server.host.events import notification_event, serialize_event
from marimo._server.host.handover import Handover, Turn
from marimo._server.host.translate import (
    RunTranslator,
    RunTranslators,
    variable_messages,
)
from marimo._session.model import SessionMode
from marimo._session.notebook.writer import NotebookWriter, cells_to_ir
from marimo._types.ids import CellId_t
from marimo._version import __version__

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping, Sequence
    from typing import Any

    from marimo._core.stream import Sink
    from marimo._messaging.notification import NotificationMessage
    from marimo._messaging.types import KernelMessage
    from marimo._pyodide.pyodide_session import PyodideSession
    from marimo._runtime.commands import CommandMessage
    from marimo._runtime.runner.scheduler import Scheduler

LOGGER = _loggers.marimo_logger()

_OPERATIONS = (
    "notebook.edit",
    "notebook.save",
    "runtime.run",
    "runtime.interrupt",
)


def _active_scheduler() -> Scheduler | None:
    """The scheduler of the run the kernel has in flight, if any."""
    ctx = safe_get_context()
    if not isinstance(ctx, KernelRuntimeContext):
        return None
    return ctx.active_scheduler


@dataclass
class _Preparing:
    """A run being readied for the kernel, in its turn."""

    translator: RunTranslator
    turn: Turn
    task: asyncio.Task[None]


class WorkerBackend:
    """Run the notebook on the worker's kernel and report through the host.

    The kernel shares the worker's thread, so a cell that holds it can
    only be interrupted by the page, through the interrupt buffer. This
    backend cancels a run the kernel has not started and, once the thread
    is free, halts a run the kernel has in flight, on the run's next
    report if the kernel has not exposed its scheduler yet.
    """

    def __init__(
        self,
        session: PyodideSession,
        observe: Callable[[be.Message], None],
        load_packages: Callable[[str], Awaitable[None]],
    ) -> None:
        self._session = session
        self._observe = observe
        self._load_packages = load_packages
        self._translators = RunTranslators()
        self._handover = Handover()
        self._preparing: dict[protocol.RunId, _Preparing] = {}
        """Runs handed over that the kernel does not have yet."""
        self._halting: set[protocol.RunId] = set()
        """Runs asked to stop whose halt has not taken yet."""
        self._scratchpad = asyncio.Lock()
        self._scratch_run: protocol.RunId | None = None
        """The scratch run holding the scratchpad until it completes."""
        self._announce: asyncio.Task[None] | None = None
        session.consumers.append(self._notify)

    def close(self) -> None:
        if self._notify in self._session.consumers:
            self._session.consumers.remove(self._notify)
        if self._announce is not None:
            self._announce.cancel()
        for preparing in list(self._preparing.values()):
            preparing.task.cancel()

    # Backend commands

    def attach(self, runtime_id: protocol.RuntimeId) -> None:
        """Adopt the page's kernel as `runtime_id`, running once it starts.

        The notebook exists from the first subscription, before the page
        starts the kernel, so the runtime stays `starting` until then.
        """
        if self._announce is not None:
            self._announce.cancel()
        self._announce = asyncio.get_running_loop().create_task(
            self._follow_kernel(runtime_id),
            name=f"worker.runtime.{runtime_id}",
        )

    async def _follow_kernel(self, runtime_id: protocol.RuntimeId) -> None:
        session = self._session
        started = asyncio.ensure_future(session.started.wait())
        stopped = asyncio.ensure_future(session.stopped.wait())
        try:
            # A kernel that fails to launch stops without starting.
            await asyncio.wait(
                {started, stopped}, return_when=asyncio.FIRST_COMPLETED
            )
            if session.started.is_set():
                self._observe(be.Running(runtime_id, __version__))
                await stopped
            self._observe(be.Exited(runtime_id, session.exit_reason))
        finally:
            started.cancel()
            stopped.cancel()

    def start(self, runtime_id: protocol.RuntimeId) -> None:
        self.attach(runtime_id)

    def stop(self, runtime_id: protocol.RuntimeId) -> None:
        del runtime_id
        LOGGER.warning("The worker's kernel stops with its page")

    def run(
        self,
        run_id: protocol.RunId,
        code: str,
        *,
        request: be.RequestInfo | None,
    ) -> None:
        del request  # The worker's runs arrive without an HTTP request.
        session = self._session

        def build() -> CommandMessage:
            # Snapshot the document and outputs as the kernel will see them.
            cells, outputs = scratchpad_snapshot(
                session.app_manager.app.cell_manager.document,
                session.session_view,
            )
            return ExecuteScratchpadCommand(
                code=code,
                request=None,
                notebook_cells=cells,
                cell_outputs=outputs,
                run_id=run_id,
                allow_stdin=True,
            )

        self._prepare(
            RunTranslator(run_id, code), [code], build, scratchpad=True
        )

    def run_cells(
        self,
        run_id: protocol.RunId,
        document: Document,
        cell_ids: Sequence[protocol.CellId],
        *,
        request: be.RequestInfo | None,
    ) -> None:
        del request  # The worker's runs arrive without an HTTP request.

        def build() -> CommandMessage:
            cells = {
                cell.id: ExecuteCellCommand(
                    cell_id=CellId_t(cell.id),
                    code=cell.code,
                    code_fingerprint=cell.code_fingerprint,
                )
                for cell in document
            }
            return ExecuteCellsCommand(
                execution_requests=[cells[cell_id] for cell_id in cell_ids],
                request=None,
                run_id=run_id,
                allow_stdin=True,
            )

        # Dependents run too, so every cell's imports are loaded, each
        # on its own: a cell that does not parse hides no other's imports.
        self._prepare(
            RunTranslator(run_id, None),
            [cell.code for cell in document],
            build,
        )

    def reply_input(self, input_id: protocol.ItemId, value: str) -> None:
        self._session.put_input(InputReply(input_id, value))

    def interrupt(self, run_id: protocol.RunId) -> None:
        preparing = self._preparing.get(run_id)
        if preparing is not None:
            preparing.task.cancel()
            return
        translator = self._translators.get(run_id)
        if translator is None or translator.completed:
            return
        if not translator.started:
            # The kernel drops a queued run when the cancellation reaches it.
            # One that started first is halted on its next report.
            self._session.put_control_request(CancelRunCommand(run_id=run_id))
        self._halt(run_id)

    def _halt(self, run_id: protocol.RunId) -> None:
        """Halt a run the kernel has in flight, or keep after it.

        This runs once the thread is free, so no cell holds it: halt the
        queue and cancel any async cell. A cell that held the thread was
        interrupted by the page's buffer. Until the kernel exposes the
        run's scheduler, the halt waits for the run's next report.
        """
        self._halting.add(run_id)
        translator = self._translators.get(run_id)
        if translator is None or not translator.started:
            return
        scheduler = _active_scheduler()
        if scheduler is None:
            return
        scheduler.cancel_all()
        self._halting.discard(run_id)

    def forget(self, run_id: protocol.RunId) -> None:
        self._translators.forget(run_id)

    def apply(self, command: CommandMessage) -> None:
        """Send the kernel a command in turn with the runs handed over.

        An edit that followed a run must not reach the kernel before it.
        """
        self._handover.submit(
            lambda: self._session.put_control_request(command)
        )

    # Submission

    def _prepare(
        self,
        translator: RunTranslator,
        sources: Sequence[str],
        build: Callable[[], CommandMessage],
        *,
        scratchpad: bool = False,
    ) -> None:
        """Queue the command in turn, once the packages `sources` import are loaded.

        A scratch run also waits for the scratchpad, which the scratch run
        ahead holds until it completes, so `build` snapshots the document
        and outputs that run leaves. As on the server, the runs behind it
        wait their turn only until it submits.
        """
        turn = self._handover.take()

        async def submit() -> None:
            await turn.wait()
            for source in sources:
                await self._load_packages(source)
            if scratchpad:
                await self._scratchpad.acquire()
                self._scratch_run = translator.run_id
            if not self._session.instantiated:
                # The page registers the cells when it starts the kernel;
                # a host run that comes first registers them itself.
                self._session.instantiate(auto_run=False)
            self._translators.add(translator)
            self._session.put_control_request(build())
            self._preparing.pop(translator.run_id, None)
            self._handover.finish(turn)

        task = asyncio.get_running_loop().create_task(
            submit(), name=f"worker.run.{translator.run_id}"
        )
        preparing = _Preparing(translator, turn, task)
        self._preparing[translator.run_id] = preparing
        task.add_done_callback(lambda task: self._settle(preparing, task))

    def _settle(self, preparing: _Preparing, task: asyncio.Task[None]) -> None:
        """End a run whose preparation was cancelled or failed."""
        if self._preparing.get(preparing.translator.run_id) is preparing:
            del self._preparing[preparing.translator.run_id]
        self._handover.finish(preparing.turn)
        if task.cancelled():
            preparing.translator.interrupted = True
            self._finish(preparing.translator)
            return
        exception = task.exception()
        if exception is None:
            return
        LOGGER.error("Run failed in the worker: %s", exception)
        self._finish(
            preparing.translator,
            error=protocol.Error(
                kind="internal",
                name=None,
                message=str(exception) or type(exception).__name__,
                traceback=None,
                source="marimo",
                severity="error",
                range=None,
                related=(),
            ),
        )

    def _finish(
        self, translator: RunTranslator, *, error: protocol.Error | None = None
    ) -> None:
        if self._scratch_run == translator.run_id:
            self._scratch_run = None
            self._scratchpad.release()
        for message in translator.finish(error=error):
            self._observe(message)

    # Kernel notifications

    def _notify(self, message: KernelMessage) -> None:
        notification = deserialize_kernel_message(message)
        for reported in variable_messages(notification):
            self._observe(reported)
        translator, reports = self._translators.feed(notification)
        for reported in reports:
            self._observe(reported)
        if translator is None:
            return
        if translator.completed:
            self._halting.discard(translator.run_id)
            self._finish(translator)
        elif translator.run_id in self._halting:
            self._halt(translator.run_id)


class PyodideNotebook:
    """One session's notebook, independent of the worker RPC and React."""

    def __init__(self, session: PyodideSession) -> None:
        self._session = session
        self._subscriptions: dict[str, Callable[[], None]] = {}
        self._closed = False
        self._save_lock = asyncio.Lock()
        self._persist: Callable[[str, str], Awaitable[None]] | None = None
        self._load_packages: Callable[[str], Awaitable[None]] | None = None
        self._backend: WorkerBackend | None = None
        self.host = Host(operations=_OPERATIONS)
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
                operations=_OPERATIONS
                if session.mode is SessionMode.EDIT
                else (),
            ),
            self._initialize,
        )

        self.mutations = Mutations(self.host)

    def _initialize(self, record: protocol.Notebook, sink: Sink) -> Notebook:
        cells, config = documents.from_file_manager(self._session.app_manager)
        document = Document(cells, config)
        backend = WorkerBackend(
            self._session,
            lambda message: self._observe(record.id, message),
            self._load_packages_for,
        )
        self._backend = backend
        notebook = Notebook(
            record.id,
            document,
            Executions(),
            backend,
            sink,
            saved_etag=document.etag,
        )
        # The page starts the kernel; the notebook adopts it as its runtime.
        notebook.adopt(backend.attach)
        return notebook

    def _observe(self, notebook_id: str, message: be.Message) -> None:
        try:
            notebook = self.host.peek_notebook(notebook_id)
        except NotFound:
            return
        if notebook is not None:
            notebook.observe(message)

    async def _load_packages_for(self, code: str) -> None:
        if self._load_packages is not None:
            await self._load_packages(code)

    def set_package_loader(
        self, load: Callable[[str], Awaitable[None]]
    ) -> None:
        """Load the packages a run's code imports before the kernel runs it."""
        self._load_packages = load

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
            status, body = await dispatch(
                self.mutations, self, call, request=None
            )
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
        if update is None or not self._session.instantiated:
            return
        if self._backend is not None:
            self._backend.apply(update)
        else:
            self._session.put_control_request(update)

    async def update_config(self, config: dict[str, Any]) -> None:
        notebook = await self.host.notebook(self.id)
        self._session.app_manager.app.update_config(config)
        notebook.replace(
            list(notebook.document),
            self._session.app_manager.app.config.asdict_difference(),
        )

    async def save_app_config(self, config: dict[str, Any]) -> None:
        """Apply the config and write the notebook, as the server does."""
        await self.update_config(config)
        if self._persist is not None:
            await self.save(
                self.id,
                if_match=None,
                decisions={},
                request_id=f"app-config:{uuid.uuid4()}",
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
        if self._backend is not None:
            self._backend.close()
        for subscription_id in list(self._subscriptions):
            self.unsubscribe(subscription_id)
        self.mutations.replies.clear()
        self.host.remove_notebook(self.id)
