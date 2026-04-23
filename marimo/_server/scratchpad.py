# Copyright 2026 Marimo. All rights reserved.
"""Shared utilities for scratchpad execution."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any, TypedDict

from marimo._ai._tools.types import CodeExecutionResult
from marimo._messaging.cell_output import CellChannel
from marimo._messaging.notification import (
    CellNotification,
    CompletedRunNotification,
)
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


class ConsoleEvent(TypedDict):
    data: str


class Done(TypedDict):
    """Terminal SSE event for ``/api/kernel/execute``.

    ``success`` drives the CLI exit code. ``output`` is the scratch
    cell's rendered value on success, or ``{mimetype: "text/plain",
    data: ""}`` on failure — the actual error detail (traceback, etc.)
    was already streamed via preceding ``stderr`` events.
    """

    success: bool
    output: OutputData


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
    ``_code_mode``.  The done sentinel fires on the
    ``CompletedRunNotification`` whose ``run_id`` matches this
    listener's ``run_id`` — other completion events (e.g. from the
    ``session.instantiate`` that happens before the scratchpad runs, or
    from concurrent browser activity) are ignored, so we can't
    misidentify someone else's completion as ours.
    """

    def __init__(self, *, run_id: str) -> None:
        super().__init__()
        self._queue: asyncio.Queue[CellNotification | None] = asyncio.Queue()
        self._run_id = run_id
        self.timed_out = False
        self.child_error_summaries: list[str] = []

    def on_notification_sent(
        self, session: Session, notification: KernelMessage
    ) -> None:
        del session
        msg = deserialize_kernel_message(notification)

        # Completion sentinel: the ``CompletedRunNotification`` tagged
        # with OUR run_id means the scratchpad's full cascade (including
        # any ``state_updates`` flushed after the scratch cell goes
        # idle) has settled. ``CompletedRun``s with other ids belong to
        # unrelated commands — skip them.
        if isinstance(msg, CompletedRunNotification):
            if msg.run_id == self._run_id:
                self._queue.put_nowait(None)
            return

        if not isinstance(msg, CellNotification):
            return

        if msg.cell_id == SCRATCH_CELL_ID:
            self._queue.put_nowait(msg)
        else:
            if msg.console is not None:
                # Stream console output from cells run by _code_mode
                # during this scratchpad execution.
                self._queue.put_nowait(msg)
            if (
                msg.output is not None
                and msg.output.channel == CellChannel.MARIMO_ERROR
                and isinstance(msg.output.data, list)
                and msg.output.data
            ):
                err = msg.output.data[0]
                exc_type = (
                    getattr(err, "exception_type", None) or type(err).__name__
                )
                self.child_error_summaries.append(
                    f"cell '{msg.cell_id}' raised {exc_type}"
                )

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


_EMPTY_OUTPUT = OutputData(mimetype="text/plain", data="")


def build_done_event(
    session: Session,
    listener: ScratchCellListener | None = None,
) -> str:
    """Build the terminal ``done`` SSE event.

    ``success`` is false when the scratch cell itself errored OR any
    downstream cell captured by the listener errored. The actual error
    detail was already streamed via ``stderr`` events earlier in the
    response — ``done`` carries only the success bit plus the scratch
    cell's rendered output on success (empty on failure).
    """
    cell_notif = session.session_view.cell_notifications.get(SCRATCH_CELL_ID)
    output = cell_notif.output if cell_notif is not None else None

    scratch_errored = (
        output is not None and output.channel == CellChannel.MARIMO_ERROR
    )
    has_child_errors = bool(listener and listener.child_error_summaries)
    success = not (scratch_errored or has_child_errors)

    if success and output is not None and output.channel == CellChannel.OUTPUT:
        data = output.data
        if isinstance(data, dict):
            data = data.get("text/plain", data.get("text/html", str(data)))
        output_data = OutputData(mimetype=str(output.mimetype), data=str(data))
    else:
        output_data = _EMPTY_OUTPUT

    return _format_sse("done", Done(success=success, output=output_data))


def extract_result(
    session: Session,
    listener: ScratchCellListener | None = None,
) -> CodeExecutionResult:
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

    # Include child cell error summaries.
    if listener:
        errors.extend(listener.child_error_summaries)

    return CodeExecutionResult(
        success=len(errors) == 0,
        output=output_data,
        stdout=stdout,
        stderr=stderr,
        errors=errors,
    )
