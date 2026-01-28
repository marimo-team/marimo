# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Literal, Optional

import msgspec


class LspServerHealth(msgspec.Struct, rename="camel"):
    """Health status for a single LSP server."""

    server_id: str
    is_running: bool
    is_responsive: bool  # True if responds to TCP ping
    has_failed: bool
    port: int
    last_ping_ms: Optional[float] = None
    error: Optional[str] = None


class LspHealthResponse(msgspec.Struct, rename="camel"):
    """Aggregated health response for all LSP servers."""

    status: Literal["healthy", "degraded", "unhealthy"]
    servers: list[LspServerHealth]


class LspRestartRequest(msgspec.Struct, rename="camel"):
    """Request to restart LSP servers."""

    server_ids: Optional[list[str]] = None  # None = restart failed servers


class LspRestartResponse(msgspec.Struct, rename="camel"):
    """Response from restart operation."""

    success: bool
    restarted: list[str]  # Server IDs that were restarted
    errors: dict[str, str] = {}  # Server ID -> error message
