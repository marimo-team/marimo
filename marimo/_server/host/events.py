# Copyright 2026 Marimo. All rights reserved.
"""Internal marimo events for the host stream."""

from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec

from marimo._core import protocol
from marimo._core.stream import ExtensionEvent, RoutedEvent, event_name
from marimo._messaging.notification import (
    CallbackOutputNotification,
    CellNotification,
    ConsoleInputsClearedNotification,
    EditorNotification,
    ExecutionNotification,
    KernelReadyNotification,
    NotificationMessage,
    PdbInputNotification,
    PdbOutputNotification,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from marimo._messaging.command_output import CommandOutput
    from marimo._session.state.session_view import SessionView
    from marimo._types.ids import CellId_t


class MarimoMessage(msgspec.Struct, frozen=True):
    """A marimo notification carried by the host event stream.

    This type is internal to marimo and may change between releases.
    """

    marimo: EditorNotification


class MarimoEvent(ExtensionEvent, frozen=True, tag="marimo"):
    """A typed envelope for internal marimo notifications."""

    data: MarimoMessage


class EditorNotifications:
    """Project kernel updates onto one editor subscription."""

    def __init__(self) -> None:
        self._cleared_inputs: dict[CellId_t, tuple[str, int]] = {}
        self._command_output: dict[CellId_t, set[CommandOutput]] = {}

    def events(
        self,
        notebook_id: protocol.NotebookId | None,
        notification: NotificationMessage,
        view: SessionView | None = None,
    ) -> Iterator[RoutedEvent]:
        if isinstance(notification, CellNotification):
            if (
                notification.console == []
                and notification.execution_id is not None
                and view is not None
            ):
                if notification.execution_id == view.current_execution_id(
                    notification.cell_id
                ):
                    kinds = self._command_output.pop(
                        notification.cell_id, None
                    )
                    if kinds and notification.status != "running":
                        for kind in kinds:
                            yield self._event(
                                notebook_id,
                                kind(notification.cell_id, [], replace=True),
                            )
                cleared = view.cleared_console_inputs(
                    notification.cell_id, notification.execution_id
                )
                if cleared is not None:
                    yield from self.events(notebook_id, cleared)
            return
        if view is not None and isinstance(
            notification, (PdbOutputNotification, CallbackOutputNotification)
        ):
            if notification.entries:
                self._command_output.setdefault(
                    notification.cell_id, set()
                ).add(type(notification))
            elif kinds := self._command_output.get(notification.cell_id):
                kinds.discard(type(notification))
            if (
                isinstance(notification, CallbackOutputNotification)
                and notification.clears_cell_console
            ):
                self._command_output.pop(notification.cell_id, None)
                cleared = view.cleared_console_inputs(notification.cell_id)
                if cleared is not None:
                    yield from self.events(notebook_id, cleared)
            notification = view.position_command_output(notification)
        if isinstance(notification, KernelReadyNotification):
            # The renderer resets on kernel-ready, before the session replay.
            self._cleared_inputs.clear()
        if isinstance(notification, ConsoleInputsClearedNotification):
            revision = (notification.execution_id, len(notification.input_ids))
            if self._cleared_inputs.get(notification.cell_id) == revision:
                return
            self._cleared_inputs[notification.cell_id] = revision
        event = notification_event(
            notebook_id, notification, editor_session=True
        )
        if event is not None:
            yield event

    @staticmethod
    def _event(
        notebook_id: protocol.NotebookId | None, message: EditorNotification
    ) -> RoutedEvent:
        return RoutedEvent(
            MarimoEvent(MarimoMessage(message)), notebook_id=notebook_id
        )


def notification_event(
    notebook_id: protocol.NotebookId | None,
    notification: NotificationMessage,
    *,
    editor_session: bool = False,
) -> RoutedEvent | None:
    """Project a kernel notification onto the host or attached editor stream."""
    if isinstance(notification, (ExecutionNotification, CellNotification)):
        return None
    if not editor_session and isinstance(
        notification,
        (
            PdbInputNotification,
            CallbackOutputNotification,
            PdbOutputNotification,
            ConsoleInputsClearedNotification,
        ),
    ):
        return None
    run_id = getattr(notification, "run_id", None)
    return RoutedEvent(
        MarimoEvent(MarimoMessage(notification)),
        notebook_id=notebook_id,
        run_id=protocol.RunId(run_id) if run_id is not None else None,
    )


def _visible_event(
    event: RoutedEvent, *, include_code: bool
) -> protocol.Event | ExtensionEvent:
    """Encode a frame using this connection's source-visibility policy.

    Project a copy at delivery, so the host retains source and revisions for
    snapshots, replay, and staleness checks regardless of the reader.
    """
    message = event.event
    if not include_code and isinstance(message, protocol.CellEvent):
        cell = msgspec.structs.replace(message.data.cell, code=None)
        data = msgspec.structs.replace(message.data, cell=cell)
        message = msgspec.structs.replace(message, data=data)
    return message


def serialize_event(event: RoutedEvent, *, include_code: bool = True) -> str:
    """Encode a host WebSocket envelope."""
    return msgspec.json.encode(
        _visible_event(event, include_code=include_code)
    ).decode()


def serialize_sse_event(
    event: RoutedEvent, *, include_code: bool = True
) -> str:
    """Encode the same host event using SSE fields."""
    message = _visible_event(event, include_code=include_code)
    lines = []
    if message.id is not msgspec.UNSET:
        lines.append(f"id: {message.id}")
    lines.append(f"event: {event_name(message)}")
    lines.append(f"data: {msgspec.json.encode(message.data).decode()}")
    return "\n".join(lines) + "\n\n"
