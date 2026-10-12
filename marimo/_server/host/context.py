# Copyright 2026 Marimo. All rights reserved.
"""Shared state for host API routes."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Callable

    from starlette.responses import Response

    from marimo._core import protocol
    from marimo._server.host.bridge import SessionBridge


@dataclass
class CachedMutation:
    """One accepted request, including its in-flight or completed reply."""

    fingerprint: str
    task: asyncio.Task[Response]
    run: protocol.Run | None = None
    expires_at: float | None = None


@dataclass
class HostContext:
    """Host API token, address, session bridge, and cached replies."""

    bridge: SessionBridge
    token: str
    port: int
    replies: dict[str, CachedMutation] = field(default_factory=dict)
    # A receipt covers a client's retry loop after a lost response, so it
    # outlasts retry backoff rather than a person's absence.
    receipt_seconds: float = 300.0
    clock: Callable[[], float] = monotonic

    def remembered(self, key: str) -> CachedMutation | None:
        """Return the receipt for a key, dropping it if it has expired."""
        reply = self.replies.get(key)
        if reply is not None and self._expired(reply):
            del self.replies[key]
            return None
        return reply

    def settle(self, mutation: CachedMutation) -> None:
        """Start the receipt's retention window once its work is complete."""
        mutation.expires_at = self.clock() + self.receipt_seconds

    def expire(self) -> None:
        """Sweep expired receipts and the host's results."""
        self.bridge.host.expire()
        for key, reply in list(self.replies.items()):
            if self._expired(reply):
                del self.replies[key]

    def _expired(self, reply: CachedMutation) -> bool:
        return (
            reply.expires_at is not None and self.clock() >= reply.expires_at
        )
