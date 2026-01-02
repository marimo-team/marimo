# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from enum import Enum


class ConnectionState(Enum):
    """Connection state for a session"""

    CONNECTING = 0
    OPEN = 1
    CLOSED = 2
    ORPHANED = 3


class SessionMode(str, Enum):
    """Session mode for a session"""

    # read-write
    EDIT = "edit"
    # read-only
    RUN = "run"
