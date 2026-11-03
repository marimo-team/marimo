# Copyright 2026 Marimo. All rights reserved.
"""Kernel commands and updates using marimo sessions."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import msgspec

from marimo import _loggers
from marimo._core import backend as be, protocol
from marimo._messaging.notification import (
    CellNotification,
    CompletedRunNotification,
    ExecutionNotification,
    InterruptedNotification,
    NotebookDocumentTransactionNotification,
    StartupProgressNotification,
    VariableValuesNotification,
)
from marimo._messaging.serde import deserialize_kernel_message
from marimo._runtime.commands import (
    ExecuteCellsCommand,
    ExecuteScratchpadCommand,
    HTTPRequest,
)
from marimo._runtime.scratch import SCRATCH_CELL_ID
from marimo._server.host.events import notification_event
from marimo._server.host.translate import RunTranslator
from marimo._server.scratchpad import snapshot_for_scratchpad
from marimo._session.consumer import SessionConsumer
from marimo._session.model import ConnectionState, SessionMode
from marimo._session.requests import InstantiateNotebookRequest
from marimo._session.types import KernelState
from marimo._types.ids import CellId_t, ConsumerId, SessionId
from marimo._version import __version__

if TYPE_CHECKING:
    from collections.abc import Coroutine, Sequence

    from marimo._core.document import Document
    from marimo._core.stream import Sink
    from marimo._messaging.notification import NotificationMessage
    from marimo._messaging.types import KernelMessage
    from marimo._runtime.commands import CommandMessage
    from marimo._server.session_manager import SessionManager
    from marimo._session.events import SessionEventBus
    from marimo._session.session import Session
    from marimo._types.encodable import Encodable

LOGGER = _loggers.marimo_logger()

_PHASES = {
    "preparing-environment": "Preparing the environment",
    "starting-kernel": "Starting the kernel",
}

Observe = Callable[[be.Message], None]
RequestMetadata = Callable[["Session"], dict[str, "Encodable"]]


@dataclass
class _Kernel:
    """The session backing one runtime, once it exists."""

    runtime_id: protocol.RuntimeId
    session: Session | None = None
    stop_requested: bool = False


@dataclass
class _Run:
    session: Session
    translator: RunTranslator
    done: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task[object] | None = None
    submitted: bool = False


class SessionBackend(SessionConsumer):
    """A notebook backend that reports updates from a session.

    Connects as a secondary consumer to receive startup, execution,
    and shutdown notifications.
    """

    def __init__(
        self,
        notebook_id: protocol.NotebookId,
        file: Callable[[], str | None],
        manager: SessionManager,
        observe: Observe,
        sink: Sink,
        document_changed: Callable[[], None] | None = None,
        session_attached: Callable[[], None] | None = None,
        session_detached: Callable[[Session], None] | None = None,
        *,
        request_metadata: RequestMetadata | None = None,
    ) -> None:
        self._notebook_id = notebook_id
        self._file = file
        """Resolve the notebook's current path after file moves."""
        self._manager = manager
        self._observe = observe
        self._sink = sink
        self._document_changed = document_changed
        """Called after the session's document changes, from any writer."""
        self._session_attached = session_attached
        """Called with the session attached, before the runtime is reported."""
        self._session_detached = session_detached
        """Called with the session that detached, before its exit is reported."""
        self._request_metadata = request_metadata
        self._kernel: _Kernel | None = None
        self._run: _Run | None = None
        self._translators: dict[str, RunTranslator] = {}

    @property
    def session(self) -> Session | None:
        """The session backing the current runtime, once attached."""
        return None if self._kernel is None else self._kernel.session

    # Backend commands

    def start(self, runtime_id: protocol.RuntimeId) -> None:
        kernel = self._kernel = _Kernel(runtime_id)
        asyncio.get_running_loop().create_task(
            self._start(kernel, SessionId(f"host-{runtime_id}")),
            name=f"host.start.{runtime_id}",
        )

    async def _start(self, kernel: _Kernel, session_id: SessionId) -> None:
        file = self._file()
        if file is None:
            self._fail(kernel, "The notebook has no file to run")
            return
        try:
            await self._manager.create_session(
                session_id,
                self,
                {},
                file,
                auto_instantiate=False,
                main=False,
            )
        except Exception as e:
            LOGGER.warning(
                "Kernel for %s failed to start", file, exc_info=True
            )
            self._fail(kernel, str(e) or type(e).__name__)
            return
        # Apply a stop requested during startup.
        if kernel.stop_requested:
            self.stop(kernel.runtime_id)

    def _fail(self, kernel: _Kernel, reason: str) -> None:
        if self._kernel is kernel:
            self._kernel = None
        self._observe(be.Exited(kernel.runtime_id, reason))

    def stop(self, runtime_id: protocol.RuntimeId) -> None:
        kernel = self._kernel
        if kernel is None or kernel.runtime_id != runtime_id:
            return
        session = kernel.session
        if session is None:
            kernel.stop_requested = True
            return
        for session_id, candidate in self._manager.sessions.items():
            if candidate is session:
                self._manager.close_session(session_id)
                return
        # Closing an unregistered session still detaches its consumers.
        session.close()

    def run(self, run_id: protocol.RunId, code: str) -> None:
        session = self.session
        if session is None:
            return
        run = _Run(session, RunTranslator(run_id, code))
        self._run = run
        self._watch_run(run, self._run_code(run, code))

    def run_cells(
        self,
        run_id: protocol.RunId,
        document: Document,
        cell_ids: Sequence[protocol.CellId],
    ) -> None:
        session = self.session
        if session is None:
            return
        run = _Run(session, RunTranslator(run_id, None))
        self._run = run
        codes = {CellId_t(cell.id): cell.code for cell in document}
        targets = [CellId_t(cell_id) for cell_id in cell_ids]
        try:
            # Enqueue before returning so later document edits follow the run.
            session.instantiate(
                InstantiateNotebookRequest(
                    object_ids=[], values=[], auto_run=False, codes=codes
                ),
                http_request=None,
            )
            self._submit(
                run,
                ExecuteCellsCommand(
                    cell_ids=targets,
                    codes=[codes[cell_id] for cell_id in targets],
                    request=self._http_request(session),
                    run_id=run_id,
                    allow_stdin=False,
                ),
            )
        except Exception as exception:
            self._finish_run(run, exception)
            return
        self._watch_run(run, run.done.wait())

    def _watch_run(
        self, run: _Run, coroutine: Coroutine[object, object, object]
    ) -> None:
        run.task = asyncio.get_running_loop().create_task(
            coroutine, name=f"host.run.{run.translator.run_id}"
        )
        # A callback also finalizes cancellation before the coroutine starts.
        run.task.add_done_callback(
            lambda task: self._finish_run(
                run,
                asyncio.CancelledError()
                if task.cancelled()
                else task.exception(),
            )
        )

    def _submit(self, run: _Run, command: CommandMessage) -> None:
        run.submitted = True
        self._translators[run.translator.run_id] = run.translator
        run.session.put_control_request(command, from_consumer_id=None)

    async def _run_code(self, run: _Run, code: str) -> None:
        session = run.session
        async with session.scratchpad_lock:
            # Register notebook definitions once, without executing cells.
            session.instantiate(
                InstantiateNotebookRequest(
                    object_ids=[], values=[], auto_run=False
                ),
                http_request=None,
            )
            cells, outputs = snapshot_for_scratchpad(session)
            self._submit(
                run,
                ExecuteScratchpadCommand(
                    code=code,
                    request=self._http_request(session),
                    notebook_cells=cells,
                    cell_outputs=outputs,
                    run_id=run.translator.run_id,
                    allow_stdin=False,
                ),
            )
            await run.done.wait()

    def _http_request(self, session: Session) -> HTTPRequest | None:
        if self._request_metadata is None:
            return None
        # Host runs have no HTTP origin. Give the URL fields the same
        # keys a real request has so notebook code can read them.
        empty_url: dict[str, Encodable] = {
            "path": "",
            "port": None,
            "scheme": "",
            "netloc": "",
            "query": "",
            "hostname": None,
        }
        return HTTPRequest(
            url=dict(empty_url),
            base_url=dict(empty_url),
            headers={},
            query_params={},
            path_params={},
            cookies={},
            user={},
            meta=self._request_metadata(session),
        )

    def _finish_run(self, run: _Run, exception: BaseException | None) -> None:
        if self._run is run:
            self._run = None
        error = None
        if isinstance(exception, asyncio.CancelledError):
            run.translator.interrupted = True
        elif exception is not None:
            LOGGER.error("Run failed in the host: %s", exception)
            error = protocol.Error(
                kind="internal",
                name=None,
                message=str(exception) or type(exception).__name__,
                traceback=None,
                source="marimo",
                severity="error",
                range=None,
                related=(),
            )
        # Detachment already ended this session's runs in the core model.
        if self.session is run.session:
            for message in run.translator.finish(error=error):
                self._observe(message)

    def interrupt(self, run_id: protocol.RunId) -> None:
        run = self._run
        if run is None or run.translator.run_id != run_id:
            translator = self._translators.get(run_id)
            if (
                translator is not None
                and not translator.completed
                and self.session is not None
            ):
                self.session.try_interrupt()
            return
        if run.done.is_set():
            return
        if run.submitted:
            run.session.try_interrupt()
        elif run.task is not None:
            run.task.cancel()

    def forget(self, run_id: protocol.RunId) -> None:
        self._translators.pop(run_id, None)

    # Existing sessions

    def adopt(self, runtime_id: protocol.RuntimeId, session: Session) -> None:
        """Observe an existing session as the given runtime."""
        if self.session is not None:
            return
        kernel = self._kernel = _Kernel(runtime_id)
        try:
            session.connect_consumer(self, main=False)
        except Exception as e:
            LOGGER.warning("Failed to adopt session", exc_info=True)
            # Detachment must not report a second exit or close the session
            # that another client owns.
            self._kernel = None
            session.disconnect_consumer(self)
            self._fail(kernel, str(e) or type(e).__name__)

    # Session consumer

    @property
    def consumer_id(self) -> ConsumerId:
        return ConsumerId(f"host-{self._notebook_id}")

    def connection_state(self) -> ConnectionState:
        return ConnectionState.OPEN

    def on_attach(self, session: Session, event_bus: SessionEventBus) -> None:
        del event_bus
        kernel = self._kernel
        if kernel is None:
            return
        kernel.session = session
        if self._session_attached is not None:
            self._session_attached()
        self._observe(be.Running(kernel.runtime_id, __version__))

    def on_detach(self) -> None:
        """Report session closure and release any waiting run."""
        kernel, self._kernel = self._kernel, None
        if kernel is None or kernel.session is None:
            return
        session = kernel.session
        if self._session_detached is not None:
            self._session_detached(session)
        reason = None
        if session.kernel_state() is KernelState.STOPPED:
            info = session.kernel_exit_info()
            reason = info.message if info is not None else "The kernel died"
        run = self._run
        if run is not None and run.task is not None:
            run.task.cancel()
        self._translators.clear()
        self._observe(be.Exited(kernel.runtime_id, reason))

    def notify(self, notification: KernelMessage) -> None:
        message = deserialize_kernel_message(notification)
        with self._sink.deferred():
            self._sink.append(notification_event(self._notebook_id, message))
            self._handle_notification(message)

    def _handle_notification(self, message: NotificationMessage) -> None:
        if isinstance(message, VariableValuesNotification):
            for removed in message.removed:
                self._observe(
                    be.Unbound(
                        protocol.ExecutionId(removed.execution_id),
                        removed.name,
                    )
                )
            for value in message.variables:
                if value.execution_id is None or value.revision is None:
                    continue
                self._observe(
                    be.Produced(
                        protocol.Variable(
                            execution_id=protocol.ExecutionId(
                                value.execution_id
                            ),
                            id=protocol.ItemId(
                                f"{value.execution_id}-variable-{value.name}"
                            ),
                            name=value.name,
                            preview=value.value,
                            revision=value.revision,
                            type=value.datatype,
                        )
                    )
                )
            return
        if isinstance(message, NotebookDocumentTransactionNotification):
            if self._document_changed is not None and self.session is not None:
                self._document_changed()
            return
        if isinstance(message, StartupProgressNotification):
            if (kernel := self._kernel) is not None:
                phase = _PHASES.get(message.phase, message.phase)
                self._observe(be.Starting(kernel.runtime_id, phase))
            return
        if not isinstance(
            message,
            (
                CellNotification,
                ExecutionNotification,
                CompletedRunNotification,
                InterruptedNotification,
            ),
        ):
            return
        run_id = message.run_id
        if run_id is None:
            return
        run = self._run
        translator = self._translators.get(run_id)
        if translator is None:
            if (
                not isinstance(message, ExecutionNotification)
                or message.phase != "planned"
                or self.session is None
            ):
                return
            translator = RunTranslator(
                protocol.RunId(run_id),
                message.code if message.cell_id == SCRATCH_CELL_ID else None,
            )
            self._translators[run_id] = translator
            self._observe(be.Scheduled(translator.run_id))
        # Run kernels omit source from native notifications. App documents are
        # immutable, so recover the submitted source for host revision hashes.
        # Keep the native message private and unchanged in the shared log.
        if (
            isinstance(message, ExecutionNotification)
            and message.phase == "planned"
            and message.code is None
            and self._manager.mode is SessionMode.RUN
            and self.session is not None
        ):
            cell = self.session.document.get(message.cell_id)
            if cell is not None:
                message = msgspec.structs.replace(message, code=cell.code)
        for out in translator.feed(message):
            self._observe(out)
        if translator.completed:
            if run is not None and translator is run.translator:
                run.done.set()
            else:
                for out in translator.finish():
                    self._observe(out)
