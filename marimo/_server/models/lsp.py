# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Literal, NewType, Optional

import msgspec

# Type-safe server identifier
LspServerId = NewType("LspServerId", str)

# Status enum for LSP server health
LspServerStatus = Literal[
    "starting",  # process launched, initializing
    "running",  # healthy and responsive to pings
    "stopped",  # not running (never started or cleanly stopped)
    "crashed",  # exited with non-zero code
    "unresponsive",  # process alive but not responding to pings
]


class LspServerHealth(msgspec.Struct, rename="camel"):
    """Health status for a single LSP server.

    Status meanings:
    - starting: process launched, initializing
    - running: healthy and responsive to pings
    - stopped: not running (never started or cleanly stopped)
    - crashed: exited with non-zero code
    - unresponsive: process alive but not responding to pings
    """

    server_id: LspServerId
    status: LspServerStatus
    port: int
    last_ping_ms: Optional[float] = None
    error: Optional[str] = None
    started_at: Optional[float] = None  # Unix timestamp


class LspHealthResponse(msgspec.Struct, rename="camel"):
    """Aggregated health response for all LSP servers."""

    status: Literal["healthy", "degraded", "unhealthy"]
    servers: list[LspServerHealth]


class LspRestartRequest(msgspec.Struct, rename="camel"):
    """Request to restart LSP servers."""

    server_ids: Optional[list[LspServerId]] = (
        None  # None = restart failed servers
    )


class LspRestartResponse(msgspec.Struct, rename="camel"):
    """Response from restart operation."""

    success: bool
    restarted: list[LspServerId]  # Server IDs that were restarted
    errors: dict[LspServerId, str] = {}  # Server ID -> error message
