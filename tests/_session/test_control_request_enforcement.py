# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import MagicMock

from marimo._messaging.notification import ConsumerCapabilities
from marimo._runtime import commands
from marimo._session.session import SessionImpl
from marimo._types.ids import ConsumerId


def _session_with_capabilities(
    caps: ConsumerCapabilities,
    *,
    consumer_present: bool = True,
) -> tuple[SessionImpl, MagicMock]:
    session = SessionImpl.__new__(SessionImpl)
    event_bus = MagicMock()
    session._event_bus = event_bus
    room = MagicMock()
    room.get_consumer.return_value = object() if consumer_present else None
    room.get_capabilities.return_value = caps
    session.room = room
    return session, event_bus


def _run_command() -> commands.CommandMessage:
    return commands.ExecuteCellsCommand(cell_ids=[], codes=[])


def test_viewer_run_request_is_dropped() -> None:
    session, event_bus = _session_with_capabilities(
        ConsumerCapabilities(edit=False, interact=False)
    )
    session.put_control_request(
        _run_command(), from_consumer_id=ConsumerId("viewer")
    )
    event_bus.emit_received_command.assert_not_called()


def test_editor_run_request_passes() -> None:
    session, event_bus = _session_with_capabilities(
        ConsumerCapabilities(edit=True, interact=True)
    )
    session.put_control_request(
        _run_command(), from_consumer_id=ConsumerId("editor")
    )
    event_bus.emit_received_command.assert_called_once()


def test_system_request_bypasses_enforcement() -> None:
    session, event_bus = _session_with_capabilities(
        ConsumerCapabilities(edit=False, interact=False)
    )
    session.put_control_request(_run_command(), from_consumer_id=None)
    event_bus.emit_received_command.assert_called_once()


def test_missing_consumer_read_request_is_dropped() -> None:
    session, event_bus = _session_with_capabilities(
        ConsumerCapabilities(edit=False, interact=False),
        consumer_present=False,
    )
    # Read-tier commands are granted unconditionally once a consumer is found,
    # so a stale or forged id must be dropped before that check.
    session.put_control_request(
        commands.CodeCompletionCommand(id="c", document="", cell_id="cell-0"),
        from_consumer_id=ConsumerId("ghost"),
    )
    event_bus.emit_received_command.assert_not_called()
