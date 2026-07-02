# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from enum import Enum, IntEnum


class WebSocketCodes(IntEnum):
    ALREADY_CONNECTED = 1003
    NORMAL_CLOSE = 1000
    FORBIDDEN = 1008
    UNAUTHORIZED = 3000
    UNEXPECTED_ERROR = 1011


class WebSocketCloseReason(str, Enum):
    """Reasons the backend sends in a WebSocket close frame.

    The value is the raw `CloseEvent.reason` string sent over the wire. The
    frontend hand-mirrors the subset it handles in
    `frontend/src/core/websocket/useMarimoKernelConnection.tsx`.
    """

    LORO_NOT_INSTALLED = "MARIMO_LORO_NOT_INSTALLED"
    NOT_ALLOWED = "MARIMO_NOT_ALLOWED"
    UNAUTHORIZED = "MARIMO_UNAUTHORIZED"
    NO_SESSION_ID = "MARIMO_NO_SESSION_ID"
    NO_FILE_KEY = "MARIMO_NO_FILE_KEY"
    NO_SESSION = "MARIMO_NO_SESSION"
    KIOSK_NOT_ALLOWED = "MARIMO_KIOSK_NOT_ALLOWED"
    KERNEL_STARTUP_ERROR = "MARIMO_KERNEL_STARTUP_ERROR"
    SHUTDOWN = "MARIMO_SHUTDOWN"
