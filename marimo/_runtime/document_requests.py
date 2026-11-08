# Copyright 2026 Marimo. All rights reserved.
"""Await host replies while the kernel's command loop is occupied."""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING

import msgspec

from marimo._messaging.types import KernelMessage

if TYPE_CHECKING:
    from collections.abc import Callable

    from marimo._messaging.host import DocumentRequest
    from marimo._runtime.commands import DocumentReplyCommand


class DocumentRequests:
    def __init__(self, send: Callable[[KernelMessage], None]) -> None:
        self._send = send
        self._pending: dict[str, asyncio.Future[DocumentReplyCommand]] = {}
        self._lock = threading.Lock()
        self._closed = False

    async def request(
        self, request: DocumentRequest, *, timeout: float = 30
    ) -> DocumentReplyCommand:
        future: asyncio.Future[DocumentReplyCommand] = (
            asyncio.get_running_loop().create_future()
        )
        with self._lock:
            if self._closed:
                raise RuntimeError("The document connection is closed")
            if request.request_id in self._pending:
                raise ValueError("A document request with this id is pending")
            self._pending[request.request_id] = future
        try:
            self._send(KernelMessage(msgspec.json.encode(request)))
            return await asyncio.wait_for(future, timeout)
        finally:
            with self._lock:
                self._pending.pop(request.request_id, None)
            future.cancel()

    def receive(self, reply: DocumentReplyCommand) -> None:
        with self._lock:
            future = self._pending.get(reply.request_id)
        if future is None:
            return

        def resolve() -> None:
            if not future.done():
                future.set_result(reply)

        _schedule(future, resolve)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            pending = list(self._pending.values())
            self._pending.clear()
        for future in pending:

            def fail(
                future: asyncio.Future[DocumentReplyCommand] = future,
            ) -> None:
                if not future.done():
                    future.set_exception(
                        RuntimeError(
                            "The document connection closed before replying"
                        )
                    )

            _schedule(future, fail)


def _schedule(
    future: asyncio.Future[DocumentReplyCommand], callback: Callable[[], None]
) -> None:
    loop = future.get_loop()
    try:
        loop.call_soon_threadsafe(callback)
    except RuntimeError:
        if not loop.is_closed():
            raise
