# Copyright 2026 Marimo. All rights reserved.
"""Kernel commands and updates using marimo sessions."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._core import backend as be, protocol
from marimo._messaging.notification import (
    NotebookDocumentTransactionNotification,
    RemoveUIElementsNotification,
    StartupProgressNotification,
    UIElementCreatedNotification,
    UIElementResultNotification,
    UIElementUpdatedNotification,
    VariableValuesNotification,
)
from marimo._messaging.serde import deserialize_kernel_message
from marimo._runtime.commands import (
    CancelRunCommand,
    ExecuteCellCommand,
    ExecuteCellsCommand,
    ExecuteScratchpadCommand,
    HTTPRequest,
    InvokeFunctionCommand,
    UpdateUIElementCommand,
)
from marimo._server.host.events import notification_event
from marimo._server.host.handover import Handover, Turn
from marimo._server.host.translate import (
    RunTranslator,
    RunTranslators,
    variable_messages,
)
from marimo._server.scratchpad import snapshot_for_scratchpad
from marimo._session.consumer import SessionConsumer
from marimo._session.model import ConnectionState
from marimo._session.requests import InstantiateNotebookRequest
from marimo._session.types import KernelState
from marimo._types.ids import (
    CellId_t,
    ConsumerId,
    RequestId,
    SessionId,
    UIElementId,
)
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
    turn: Turn
    done: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task[object] | None = None
    submitted: bool = False
    """The kernel has this run's command."""
    interrupt_requested: bool = False
    """A cancellation was sent for this run while the kernel had it queued."""


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
        self._runs: dict[protocol.RunId, _Run] = {}
        """Runs this backend submitted that have not finished, by run id."""
        self._handover = Handover()
        self._translators = RunTranslators()

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

    def update_ui_element(
        self,
        element_id: str,
        state: protocol.UIElementPartialState,
        request_id: str,
    ) -> None:
        session = self.session
        assert session is not None
        session.put_control_request(
            UpdateUIElementCommand(
                object_ids=[UIElementId(element_id)],
                values=[None if state.value is msgspec.UNSET else state.value],
                value_supplied=state.value is not msgspec.UNSET,
                request_id=request_id,
            ),
            from_consumer_id=None,
        )

    def send_ui_element(
        self,
        element_id: str,
        message: protocol.UIElementFunctionCall,
        call_id: str,
    ) -> None:
        session = self.session
        assert session is not None
        session.put_control_request(
            InvokeFunctionCommand(
                function_call_id=RequestId(call_id),
                namespace=element_id,
                function_name=message.function,
                args=message.args,
                host_call=True,
            ),
            from_consumer_id=None,
        )

    def run(self, run_id: protocol.RunId, code: str) -> None:
        session = self.session
        if session is None:
            return
        run = self._accept(session, RunTranslator(run_id, code))
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
        run = self._accept(session, RunTranslator(run_id, None))
        try:
            request = self._http_request(session)
            cells = {
                cell.id: ExecuteCellCommand(
                    cell_id=CellId_t(cell.id),
                    code=cell.code,
                    code_fingerprint=cell.code_fingerprint,
                )
                for cell in document
            }
            execution_requests = tuple(cells.values())
            command = ExecuteCellsCommand(
                execution_requests=[cells[cell_id] for cell_id in cell_ids],
                request=request,
                run_id=run_id,
                allow_stdin=False,
            )
            if not run.turn.ready:
                # A run ahead is still preparing, such as a scratch run
                # waiting for the scratchpad.
                self._watch_run(
                    run,
                    self._run_cells_after(run, execution_requests, command),
                )
                return
            # Enqueue before returning so later document edits follow the run.
            self._submit_cells(run, execution_requests, command)
        except Exception as exception:
            self._finish_run(run, exception)
            return
        self._watch_run(run, run.done.wait())

    def _accept(self, session: Session, translator: RunTranslator) -> _Run:
        run = _Run(session, translator, self._handover.take())
        self._runs[translator.run_id] = run
        return run

    def _submit_cells(
        self,
        run: _Run,
        execution_requests: Sequence[ExecuteCellCommand],
        command: ExecuteCellsCommand,
    ) -> None:
        run.session.instantiate(
            InstantiateNotebookRequest(
                object_ids=[],
                values=[],
                auto_run=False,
            ),
            http_request=None,
            execution_requests=execution_requests,
        )
        self._submit(run, command)

    async def _run_cells_after(
        self,
        run: _Run,
        execution_requests: Sequence[ExecuteCellCommand],
        command: ExecuteCellsCommand,
    ) -> None:
        await run.turn.wait()
        self._submit_cells(run, execution_requests, command)
        await run.done.wait()

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
        self._translators.add(run.translator)
        run.session.put_control_request(command, from_consumer_id=None)
        self._handover.finish(run.turn)

    async def _run_code(self, run: _Run, code: str) -> None:
        await run.turn.wait()
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
        self._handover.finish(run.turn)
        if self._runs.get(run.translator.run_id) is run:
            del self._runs[run.translator.run_id]
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
        run = self._runs.get(run_id)
        if run is None:
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
        if not run.submitted:
            if run.task is not None:
                run.task.cancel()
        elif run.translator.started:
            run.session.try_interrupt()
        else:
            # The kernel drops a queued run when the cancellation reaches it.
            # One that started first is interrupted on its next report.
            run.interrupt_requested = True
            run.session.put_control_request(
                CancelRunCommand(run_id=run_id), from_consumer_id=None
            )

    def forget(self, run_id: protocol.RunId) -> None:
        self._translators.forget(run_id)

    def apply(self, command: CommandMessage) -> None:
        """Send the kernel a command in turn with the runs handed over.

        An edit that followed a run must not reach the kernel before it.
        """
        session = self.session
        if session is None:
            return

        def put() -> None:
            if self.session is session:
                session.put_control_request(command, from_consumer_id=None)

        self._handover.submit(put)

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
        for run in list(self._runs.values()):
            if run.task is not None:
                run.task.cancel()
        self._translators.clear()
        self._observe(be.Exited(kernel.runtime_id, reason))

    def notify(self, notification: KernelMessage) -> None:
        message = deserialize_kernel_message(notification)
        with self._sink.deferred():
            if not isinstance(
                message,
                (
                    UIElementCreatedNotification,
                    UIElementUpdatedNotification,
                    UIElementResultNotification,
                ),
            ):
                self._sink.append(
                    notification_event(self._notebook_id, message)
                )
            self._handle_notification(message)

    def _handle_notification(self, message: NotificationMessage) -> None:
        if isinstance(message, UIElementResultNotification):
            if self._kernel is not None:
                self._observe(
                    be.UIElementResult(
                        self._kernel.runtime_id,
                        message.function_call_id,
                        protocol.UIElementFunctionResult(
                            return_value=message.return_value,
                            found=message.found,
                            status=protocol.UIElementFunctionStatus(
                                code=message.status.code,
                                title=message.status.title,
                                message=message.status.message,
                            ),
                        ),
                    )
                )
            return
        if isinstance(message, UIElementUpdatedNotification):
            if self._kernel is not None:
                self._observe(
                    be.UIElementUpdated(
                        self._kernel.runtime_id,
                        message.id,
                        msgspec.convert(
                            message.state, type=protocol.UIElementPartialState
                        ),
                        message.request_id,
                    )
                )
            return
        if isinstance(message, RemoveUIElementsNotification):
            if self._kernel is not None:
                self._observe(
                    be.UIElementsRemoved(
                        self._kernel.runtime_id,
                        protocol.CellId(message.cell_id),
                    )
                )
            return
        if isinstance(message, UIElementCreatedNotification):
            if self._kernel is not None:
                self._observe(
                    be.UIElementCreated(
                        self._kernel.runtime_id,
                        protocol.UIElement(
                            id=message.id,
                            kind="element",
                            cell_id=protocol.CellId(message.cell_id),
                            config=protocol.UIElementConfig(
                                component=message.component,
                                label=message.label,
                                args=message.args,
                            ),
                            state=protocol.UIElementState(value=message.value),
                        ),
                    )
                )
            return
        if isinstance(message, VariableValuesNotification):
            for out in variable_messages(message):
                self._observe(out)
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
        if self.session is None:
            return
        translator, reports = self._translators.feed(message)
        for reported in reports:
            self._observe(reported)
        if translator is None:
            return
        run = self._runs.get(translator.run_id)
        if run is not None and translator is not run.translator:
            run = None
        if (
            run is not None
            and run.interrupt_requested
            and translator.started
            and not translator.completed
        ):
            # The cancellation arrived after the kernel started this run.
            run.interrupt_requested = False
            run.session.try_interrupt()
        if translator.completed:
            if run is not None:
                run.done.set()
            else:
                for reported in translator.finish():
                    self._observe(reported)
