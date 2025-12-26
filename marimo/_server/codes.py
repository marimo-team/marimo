# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from enum import IntEnum


class WebSocketCodes(IntEnum):
    ALREADY_CONNECTED = 1003
    NORMAL_CLOSE = 1000
    FORBIDDEN = 1008
    UNAUTHORIZED = 3000
    UNEXPECTED_ERROR = 1011
