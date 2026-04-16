# Copyright 2026 Marimo. All rights reserved.
"""Shared utilities for scratchpad execution."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import TYPE_CHECKING, Any, TypedDict

if sys.version_info < (3, 11):
    from typing_extensions import NotRequired
else:
    from typing import NotRequired

from marimo._ai._tools.types import CodeExecutionResult
from marimo._messaging.cell_output import CellChannel
from marimo._messaging.notification import CellNotification
from marimo._messaging.serde import deserialize_kernel_message
from marimo._runtime.scratch import SCRATCH_CELL_ID
from marimo._session.extensions.types import EventAwareExtension

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from marimo._messaging.types import KernelMessage
    from marimo._session.session import Session

EXECUTION_TIMEOUT = (
    30.0  # seconds — used only by wait(); stream() has no timeout
)

# Channel name constants for SSE events
_CHANNEL_MAP = {
    CellChannel.STDOUT: "stdout",
    CellChannel.STDERR: "stderr",
}


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


def _format_sse(event: str, data: Any) -> str:
    """Format a single SSE event (event + JSON data)."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# -- Listeners ----------------------------------------------------------------


class ScratchCellListener(EventAwareExtension):
    """Listens for scratch cell notifications via an asyncio.Queue.

    Supports both SSE streaming (via ``stream()``) and simple blocking
    wait (via ``wait()``) so the same listener works for the HTTP
    ``/execute`` endpoint and the MCP ``execute_code`` tool.

    In addition to the scratch cell's own output, the listener captures
    console output (stdout/stderr) from *other* cells that execute while
    the scratchpad is active — e.g. cells created and run by
    ``_code_mode``.  Only the scratch cell's ``idle`` status triggers
    the done sentinel; non-scratch notifications are streamed but never
    signal completion.
    """

    def __init__(self) -> None:
        super().__init__()
        self._queue: asyncio.Queue[CellNotification | None] = asyncio.Queue()
        self.timed_out = False

    def on_notification_sent(
        self, session: Session, notification: KernelMessage
    ) -> None:
        del session
        msg = deserialize_kernel_message(notification)
        if not isinstance(msg, CellNotification):
            return

        if msg.cell_id == SCRATCH_CELL_ID:
            self._queue.put_nowait(msg)
            if msg.status == "idle":
                self._queue.put_nowait(None)  # sentinel
        elif msg.console is not None:
            # Stream console output from cells run by _code_mode
            # during this scratchpad execution.
            self._queue.put_nowait(msg)

    async def stream(self) -> AsyncGenerator[str, None]:
        """Yield SSE-formatted stdout/stderr events until execution completes.

        Streams indefinitely — the caller is responsible for cancellation
        (e.g. by disconnecting the SSE client, which triggers a kernel
        interrupt server-side).
        """
        while True:
            msg = await self._queue.get()

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

    async def wait(self, timeout: float = EXECUTION_TIMEOUT) -> None:
        """Block until execution completes, discarding streamed events.

        Sets ``self.timed_out`` if the deadline is exceeded.
        """
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
                # Same flush delay as stream()
                await asyncio.sleep(0.05)
                return


# -- Helpers ------------------------------------------------------------------


def _format_console(msg: CellNotification) -> list[str]:
    """Extract SSE-formatted stdout/stderr events from a CellNotification."""
    if msg.console is None:
        return []
    console_list = (
        msg.console if isinstance(msg.console, list) else [msg.console]
    )
    return [
        _format_sse(channel, ConsoleEvent(data=str(out.data)))
        for out in console_list
        if out is not None
        for channel in (_CHANNEL_MAP.get(out.channel),)
        if channel is not None
    ]


def build_done_event(session: Session) -> str:
    """Build the ``done`` SSE event from the session's scratch cell state."""
    cell_notif = session.session_view.cell_notifications.get(SCRATCH_CELL_ID)
    if cell_notif is None:
        return _format_sse("done", DoneSuccess(success=True))

    output = cell_notif.output

    # Error case
    if (
        output is not None
        and output.channel == CellChannel.MARIMO_ERROR
        and isinstance(output.data, list)
        and output.data
    ):
        err = output.data[0]
        error_data = ErrorData(
            type=type(err).__name__,
            msg=str(getattr(err, "msg", None) or err),
        )
        if hasattr(err, "exception_type"):
            error_data["exception_type"] = err.exception_type
            if err.exception_type in (
                "ModuleNotFoundError",
                "ImportError",
            ):
                error_data["msg"] += (
                    "\n\nHint: Use ctx.install_packages(...)"
                    " to install missing packages."
                )
        return _format_sse("done", DoneError(success=False, error=error_data))

    # Success case
    if output is not None:
        data = output.data
        if isinstance(data, dict):
            data = data.get("text/plain", data.get("text/html", str(data)))
        return _format_sse(
            "done",
            DoneSuccess(
                success=True,
                output=OutputData(
                    mimetype=str(output.mimetype), data=str(data)
                ),
            ),
        )

    return _format_sse("done", DoneSuccess(success=True))


def build_timeout_event(timeout: float) -> str:
    """Build a ``done`` SSE event for a timeout."""
    return _format_sse(
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
