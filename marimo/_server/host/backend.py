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
    CellNotification,
    CompletedRunNotification,
    ExecutionNotification,
    InterruptedNotification,
    NotebookDocumentTransactionNotification,
    StartupProgressNotification,
)
from marimo._messaging.serde import deserialize_kernel_message
from marimo._runtime.commands import ExecuteScratchpadCommand
from marimo._runtime.scratch import SCRATCH_CELL_ID
from marimo._server.host.translate import RunTranslator
from marimo._server.scratchpad import snapshot_for_scratchpad
from marimo._session.consumer import SessionConsumer
from marimo._session.model import ConnectionState
from marimo._session.requests import InstantiateNotebookRequest
from marimo._session.types import KernelState
from marimo._types.ids import ConsumerId, SessionId
from marimo._version import __version__

if TYPE_CHECKING:
    from marimo._messaging.types import KernelMessage
    from marimo._server.session_manager import SessionManager
    from marimo._session.events import SessionEventBus
    from marimo._session.session import Session

LOGGER = _loggers.marimo_logger()

_PHASES = {
    "preparing-environment": "Preparing the environment",
    "starting-kernel": "Starting the kernel",
}

Observe = Callable[[be.Message], None]


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
    task: asyncio.Task[None] | None = None
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
        document_changed: Callable[[], None] | None = None,
        session_attached: Callable[[], None] | None = None,
    ) -> None:
        self._notebook_id = notebook_id
        self._file = file
        """Resolve the notebook's current path after file moves."""
        self._manager = manager
        self._observe = observe
        self._document_changed = document_changed
        """Called after the session's document changes, from any writer."""
        self._session_attached = session_attached
        """Apply pre-session host edits before reporting the runtime ready."""
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
        run.task = asyncio.get_running_loop().create_task(
            self._run_code(run, code), name=f"host.run.{run_id}"
        )
        # A callback also finalizes cancellation before the coroutine starts.
        run.task.add_done_callback(lambda task: self._finish_run(run, task))

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
            run.submitted = True
            self._translators[run.translator.run_id] = run.translator
            session.put_control_request(
                ExecuteScratchpadCommand(
                    code=code,
                    request=None,
                    notebook_cells=cells,
                    cell_outputs=outputs,
                    run_id=run.translator.run_id,
                    allow_stdin=False,
                ),
                from_consumer_id=None,
            )
            await run.done.wait()

    def _finish_run(self, run: _Run, task: asyncio.Task[None]) -> None:
        if self._run is run:
            self._run = None
        error = None
        if task.cancelled():
            run.translator.interrupted = True
        elif (exception := task.exception()) is not None:
            LOGGER.error("Scratch run failed in the host: %s", exception)
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
        for out in translator.feed(message):
            self._observe(out)
        if translator.completed:
            if run is not None and translator is run.translator:
                run.done.set()
            else:
                for out in translator.finish():
                    self._observe(out)
