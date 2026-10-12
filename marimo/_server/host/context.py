# Copyright 2026 Marimo. All rights reserved.
"""Shared state for host API routes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncio

    from starlette.responses import Response

    from marimo._core import protocol
    from marimo._server.host.bridge import SessionBridge


@dataclass
class CachedMutation:
    """One accepted request, including its in-flight or completed reply."""

    fingerprint: str
    task: asyncio.Task[Response]
    run: protocol.Run | None = None


@dataclass
class HostContext:
    """Host API token, address, session bridge, and cached replies."""

    bridge: SessionBridge
    token: str
    port: int
    replies: dict[str, CachedMutation] = field(default_factory=dict)
