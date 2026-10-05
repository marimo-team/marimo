# Copyright 2026 Marimo. All rights reserved.
"""What the host's routes share: the host, its secret, and remembered replies."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from marimo._server.host import HOST_API_PATH as _HOST_API_PATH

if TYPE_CHECKING:
    from marimo._host.host import Host
    from marimo._server.host.index import WorkspaceIndex
    from marimo._server.host.runtime import SessionManagerRuntime

HOST_API_PATH = _HOST_API_PATH
"""Where the host API lives, under the server's base URL."""


class RememberedReplies:
    """Replies to requests already carried out, by their `Idempotency-Key`.

    A client that repeats a request, after a timeout say, gets the reply
    it would have gotten the first time instead of causing the work twice.
    Keys are scoped to the host, so the same key with a different request
    is a conflict. Only the most recent replies are kept; a host's clients
    are few and retry soon or not at all.
    """

    def __init__(self, limit: int = 1024) -> None:
        self._limit = limit
        self._replies: OrderedDict[str, tuple[str, int, bytes]] = OrderedDict()

    def get(self, key: str, fingerprint: str) -> tuple[int, bytes] | None:
        """Returns the reply for `key`, if the request is the same one.

        Raises:
            KeyReused: If `key` was used for a different request.
        """
        remembered = self._replies.get(key)
        if remembered is None:
            return None
        seen, status, body = remembered
        if seen != fingerprint:
            raise KeyReused(key)
        return status, body

    def put(
        self, key: str, fingerprint: str, status: int, body: bytes
    ) -> None:
        self._replies[key] = (fingerprint, status, body)
        while len(self._replies) > self._limit:
            self._replies.popitem(last=False)


class KeyReused(Exception):
    """An `Idempotency-Key` arrived with a different request than before."""


@dataclass
class HostContext:
    """Everything the host API needs, built once per server by its lifespan."""

    host: Host
    runtime: SessionManagerRuntime
    index: WorkspaceIndex
    token: str
    """The secret in the host record. A request must carry it as a bearer."""
    url: str
    """The API's base URL, as written in the record."""
    port: int
    """The port the server listens on; the `Host` header must name it."""
    replies: RememberedReplies = field(default_factory=RememberedReplies)
