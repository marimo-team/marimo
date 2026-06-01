# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import MagicMock

from marimo._messaging.notification import (
    CompletionResultNotification,
    FocusCellNotification,
)
from marimo._server.api.endpoints.ws.ws_message_loop import (
    WebSocketMessageLoop,
)


def _loop(is_kiosk: bool) -> WebSocketMessageLoop:
    return WebSocketMessageLoop(
        websocket=MagicMock(),
        message_queue=MagicMock(),
        is_kiosk=lambda: is_kiosk,
        on_disconnect=MagicMock(),
        on_check_status_update=MagicMock(),
    )


def test_editor_filters_kiosk_only_and_keeps_completions() -> None:
    loop = _loop(is_kiosk=False)
    assert loop._should_filter_operation(FocusCellNotification.name) is True
    assert (
        loop._should_filter_operation(CompletionResultNotification.name)
        is False
    )


def test_viewer_keeps_kiosk_only_and_filters_completions() -> None:
    loop = _loop(is_kiosk=True)
    assert loop._should_filter_operation(FocusCellNotification.name) is False
    assert (
        loop._should_filter_operation(CompletionResultNotification.name)
        is True
    )


def test_derived_flag_follows_live_value() -> None:
    state = {"kiosk": True}
    loop = WebSocketMessageLoop(
        websocket=MagicMock(),
        message_queue=MagicMock(),
        is_kiosk=lambda: state["kiosk"],
        on_disconnect=MagicMock(),
        on_check_status_update=MagicMock(),
    )
    assert loop._should_filter_operation(FocusCellNotification.name) is False
    state["kiosk"] = False  # takeover happened
    assert loop._should_filter_operation(FocusCellNotification.name) is True
