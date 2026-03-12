# Copyright 2026 Marimo. All rights reserved.
"""Shared utilities for synchronous scratchpad execution."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, NotRequired, TypedDict, Union

from marimo._ai._tools.types import CodeExecutionResult
from marimo._messaging.cell_output import CellChannel
from marimo._messaging.notification import CellNotification
from marimo._messaging.serde import deserialize_kernel_message
from marimo._runtime.scratch import SCRATCH_CELL_ID
from marimo._session.events import SessionEventBus, SessionEventListener

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from marimo._messaging.types import KernelMessage
    from marimo._session.session import Session

EXECUTION_TIMEOUT = 30.0  # seconds


# -- SSE event payload types --------------------------------------------------


class OutputData(TypedDict):
    mimetype: str
    data: str


class ErrorData(TypedDict):
    type: str
    msg: str
    exception_type: NotRequired[str]


class ConsoleEvent(TypedDict):
    data: str


class DoneSuccess(TypedDict):
    success: bool
    output: NotRequired[OutputData]


class DoneError(TypedDict):
    success: bool
    error: ErrorData


DoneEvent = Union[DoneSuccess, DoneError]
SSEPayload = Union[ConsoleEvent, DoneEvent]


# -- SSE formatting -----------------------------------------------------------


def format_sse(event: str, data: SSEPayload) -> str:
    """Format a single SSE event (event + JSON data, no multi-line ambiguity)."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# -- Listeners ----------------------------------------------------------------


class ScratchCellListener(SessionEventListener):
    """Listens for scratch cell idle notifications and signals waiters."""

    def __init__(self) -> None:
        self._waiters: dict[str, asyncio.Event] = {}

    def wait_for(self, session_id: str) -> asyncio.Event:
        event = asyncio.Event()
        self._waiters[session_id] = event
        return event

    def on_attach(self, session: Session, event_bus: SessionEventBus) -> None:
        del session
        self._event_bus = event_bus
        event_bus.subscribe(self)

    def on_detach(self) -> None:
        if hasattr(self, "_event_bus"):
            self._event_bus.unsubscribe(self)
            del self._event_bus

    def on_notification_sent(
        self, session: Session, notification: KernelMessage
    ) -> None:
        del session
        msg = deserialize_kernel_message(notification)
        if not isinstance(msg, CellNotification):
            return
        if msg.cell_id != SCRATCH_CELL_ID:
            return
        if msg.status != "idle":
            return
        for sid, event in list(self._waiters.items()):
            if not event.is_set():
                event.set()
            del self._waiters[sid]


class StreamingScratchCellListener(SessionEventListener):
    """Pushes scratch cell notifications into an asyncio.Queue for SSE streaming."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[CellNotification | None] = asyncio.Queue()
        self.timed_out = False

    def on_attach(self, session: Session, event_bus: SessionEventBus) -> None:
        del session
        self._event_bus = event_bus
        event_bus.subscribe(self)

    def on_detach(self) -> None:
        if hasattr(self, "_event_bus"):
            self._event_bus.unsubscribe(self)
            del self._event_bus

    def on_notification_sent(
        self, session: Session, notification: KernelMessage
    ) -> None:
        del session
        msg = deserialize_kernel_message(notification)
        if not isinstance(msg, CellNotification):
            return
        if msg.cell_id != SCRATCH_CELL_ID:
            return
        self._queue.put_nowait(msg)
        if msg.status == "idle":
            # Sentinel: signals that execution is complete
            self._queue.put_nowait(None)

    async def stream(
        self, timeout: float = EXECUTION_TIMEOUT
    ) -> AsyncGenerator[str, None]:
        """Yield SSE-formatted stdout/stderr events until execution completes."""
        import time

        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self.timed_out = True
                return
            try:
                msg = await asyncio.wait_for(
                    self._queue.get(), timeout=remaining
                )
            except asyncio.TimeoutError:
                self.timed_out = True
                return

            if msg is None:
                # Done sentinel — but stdout/stderr are flushed every
                # 10ms by the buffered writer thread. Wait 50ms so
                # trailing console output arrives before we finish.
                await asyncio.sleep(0.05)
                while not self._queue.empty():
                    trailing = self._queue.get_nowait()
                    if trailing is not None:
                        for event_str in _format_console(trailing):
                            yield event_str
                return

            for event_str in _format_console(msg):
                yield event_str


# -- Helpers ------------------------------------------------------------------


def _format_console(msg: CellNotification) -> list[str]:
    """Extract stdout/stderr from a CellNotification as SSE events."""
    if msg.console is None:
        return []
    console_list = (
        msg.console if isinstance(msg.console, list) else [msg.console]
    )
    events: list[str] = []
    for out in console_list:
        if out is None:
            continue
        if out.channel == CellChannel.STDOUT:
            events.append(
                format_sse("stdout", ConsoleEvent(data=str(out.data)))
            )
        elif out.channel == CellChannel.STDERR:
            events.append(
                format_sse("stderr", ConsoleEvent(data=str(out.data)))
            )
    return events


def build_done_event(session: Session) -> str:
    """Build the ``done`` SSE event from the session's scratch cell state.

    Returns either:
      ``{"success": true, "output": {"mimetype": "...", "data": "..."}}``
    or:
      ``{"success": false, "error": {"type": "...", "msg": "..."}}``
    """
    cell_notif = session.session_view.cell_notifications.get(SCRATCH_CELL_ID)
    if cell_notif is None:
        return format_sse("done", DoneSuccess(success=True))

    output = cell_notif.output

    # Error case
    if (
        output is not None
        and output.channel == CellChannel.MARIMO_ERROR
        and isinstance(output.data, list)
        and output.data
    ):
        err = output.data[0]
        msg = str(getattr(err, "msg", None) or err)
        error_data = ErrorData(
            type=type(err).__name__,
            msg=msg,
        )
        if hasattr(err, "exception_type"):
            error_data["exception_type"] = err.exception_type
        return format_sse("done", DoneError(success=False, error=error_data))

    # Success case
    if output is not None:
        data = output.data
        if isinstance(data, dict):
            data = data.get("text/plain", data.get("text/html", str(data)))
        return format_sse(
            "done",
            DoneSuccess(
                success=True,
                output=OutputData(
                    mimetype=str(output.mimetype), data=str(data)
                ),
            ),
        )

    return format_sse("done", DoneSuccess(success=True))


def build_timeout_event(timeout: float) -> str:
    """Build a ``done`` SSE event for a timeout."""
    return format_sse(
        "done",
        DoneError(
            success=False,
            error=ErrorData(
                type="TimeoutError",
                msg=f"Execution timed out after {timeout}s",
            ),
        ),
    )


def extract_result(session: Session) -> CodeExecutionResult:
    """Read the scratch cell's final state from the session view."""
    cell_notif = session.session_view.cell_notifications.get(SCRATCH_CELL_ID)
    if cell_notif is None:
        return CodeExecutionResult(success=True)

    output_data = None
    if cell_notif.output is not None:
        data = cell_notif.output.data
        if isinstance(data, str):
            output_data = data
        elif isinstance(data, dict):
            output_data = data.get(
                "text/plain", data.get("text/html", str(data))
            )

    stdout: list[str] = []
    stderr: list[str] = []
    for out in (
        cell_notif.console if isinstance(cell_notif.console, list) else []
    ):
        if out is None:
            continue
        if out.channel == CellChannel.STDOUT:
            stdout.append(str(out.data))
        elif out.channel == CellChannel.STDERR:
            stderr.append(str(out.data))

    errors: list[str] = []
    if cell_notif.output is not None and isinstance(
        cell_notif.output.data, list
    ):
        for err in cell_notif.output.data:
            errors.append(str(getattr(err, "msg", None) or err))

    return CodeExecutionResult(
        success=len(errors) == 0,
        output=output_data,
        stdout=stdout,
        stderr=stderr,
        errors=errors,
    )
