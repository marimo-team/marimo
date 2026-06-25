# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._server.codes import WebSocketCloseReason


def test_websocket_close_reason_wire_values() -> None:
    """Pin the raw close-frame strings sent over the wire.

    Renaming a member must not silently change the value the frontend
    matches against in `useMarimoKernelConnection.tsx`.
    """
    assert (
        WebSocketCloseReason.LORO_NOT_INSTALLED == "MARIMO_LORO_NOT_INSTALLED"
    )
    assert WebSocketCloseReason.NOT_ALLOWED == "MARIMO_NOT_ALLOWED"
    assert WebSocketCloseReason.UNAUTHORIZED == "MARIMO_UNAUTHORIZED"
    assert WebSocketCloseReason.NO_SESSION_ID == "MARIMO_NO_SESSION_ID"
    assert WebSocketCloseReason.NO_FILE_KEY == "MARIMO_NO_FILE_KEY"
    assert WebSocketCloseReason.NO_SESSION == "MARIMO_NO_SESSION"
    assert WebSocketCloseReason.KIOSK_NOT_ALLOWED == "MARIMO_KIOSK_NOT_ALLOWED"
    assert (
        WebSocketCloseReason.KERNEL_STARTUP_ERROR
        == "MARIMO_KERNEL_STARTUP_ERROR"
    )
    assert WebSocketCloseReason.SHUTDOWN == "MARIMO_SHUTDOWN"
