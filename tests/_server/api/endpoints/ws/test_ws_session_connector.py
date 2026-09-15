# Copyright 2026 Marimo. All rights reserved.
"""Tests for the session connector's connect decision."""

from __future__ import annotations

from unittest.mock import MagicMock

from marimo._server.api.endpoints.ws.ws_session_connector import (
    ConnectionType,
    SessionConnector,
)
from marimo._session.model import ConnectionState, SessionMode


def create_connector(
    *,
    existing_by_file: MagicMock | None,
    resumable: MagicMock | None,
) -> tuple[SessionConnector, MagicMock, MagicMock]:
    """Build a connector over mocks for a non-kiosk edit-mode connection."""
    manager = MagicMock()
    manager.mode = SessionMode.EDIT
    manager.get_session.return_value = None
    manager.get_session_by_file_key.return_value = existing_by_file
    manager.maybe_resume_session.return_value = resumable

    handler = MagicMock()

    params = MagicMock()
    params.kiosk = False
    params.rtc_enabled = False
    params.session_id = "s_new"
    params.file_key = "example.py"

    connector = SessionConnector(
        manager=manager,
        handler=handler,
        params=params,
        connection=MagicMock(),
    )
    return connector, manager, handler


def test_connect_joins_mid_handshake_edit_session_as_viewer() -> None:
    """Edit mode never creates a second session for the same notebook.

    A same-file session that is neither open (would be routed to a viewer)
    nor resumable is mid-handshake; the new connection joins it as a viewer
    instead of creating a second kernel.
    """
    session = MagicMock()
    session.connection_state.return_value = ConnectionState.CONNECTING
    connector, manager, handler = create_connector(
        existing_by_file=session, resumable=None
    )

    result_session, connection_type = connector.connect()

    assert result_session is session
    assert connection_type is ConnectionType.KIOSK
    handler._connect_kiosk.assert_called_once_with(session)
    manager.create_session.assert_not_called()


def test_resume_detaches_stale_main_consumer() -> None:
    """Resuming detaches a main consumer whose socket already closed.

    A browser refresh can deliver the new connection before the old
    socket's disconnect is processed, leaving a dead main consumer
    registered; resume must clear it before attaching the new consumer.
    """
    session = MagicMock()
    session.connection_state.return_value = ConnectionState.CLOSED
    connector, manager, handler = create_connector(
        existing_by_file=session, resumable=session
    )

    result_session, connection_type = connector.connect()

    assert result_session is session
    assert connection_type is ConnectionType.RESUME
    session.disconnect_main_consumer.assert_called_once_with()
    handler._reconnect_session.assert_called_once_with(session, replay=True)
    manager.create_session.assert_not_called()
