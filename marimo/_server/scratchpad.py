# Copyright 2026 Marimo. All rights reserved.
"""Shared utilities for synchronous scratchpad execution."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from marimo._ai._tools.types import CodeExecutionResult
from marimo._messaging.cell_output import CellChannel
from marimo._messaging.notification import CellNotification
from marimo._messaging.serde import deserialize_kernel_message
from marimo._runtime.scratch import SCRATCH_CELL_ID
from marimo._session.events import SessionEventBus, SessionEventListener

if TYPE_CHECKING:
    from marimo._messaging.types import KernelMessage
    from marimo._session.session import Session

EXECUTION_TIMEOUT = 30.0  # seconds


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


def extract_result(session: Any) -> CodeExecutionResult:
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
