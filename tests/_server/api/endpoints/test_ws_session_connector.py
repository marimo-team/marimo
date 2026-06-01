# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._server.api.endpoints.ws.ws_session_connector import (
    ConnectionType,
    is_viewer_connection,
)


def test_main_editor_is_not_viewer() -> None:
    for connection_type in (
        ConnectionType.NEW,
        ConnectionType.RECONNECT,
        ConnectionType.RESUME,
    ):
        assert (
            is_viewer_connection(
                connection_type=connection_type, is_main_consumer=True
            )
            is False
        )


def test_kiosk_connection_is_viewer_until_takeover() -> None:
    assert (
        is_viewer_connection(
            connection_type=ConnectionType.KIOSK, is_main_consumer=False
        )
        is True
    )
    # After taking over, the kiosk viewer becomes the main consumer.
    assert (
        is_viewer_connection(
            connection_type=ConnectionType.KIOSK, is_main_consumer=True
        )
        is False
    )


def test_rtc_collaborator_is_never_viewer() -> None:
    # RTC collaborators connect with main=False but are full editors.
    assert (
        is_viewer_connection(
            connection_type=ConnectionType.RTC_EXISTING,
            is_main_consumer=False,
        )
        is False
    )


def test_demoted_editor_becomes_viewer() -> None:
    # An editor that was taken over is no longer the main consumer.
    assert (
        is_viewer_connection(
            connection_type=ConnectionType.NEW, is_main_consumer=False
        )
        is True
    )
