# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Optional

from marimo import _loggers
from marimo._server.file_router import MarimoFileKey

if TYPE_CHECKING:
    from loro import LoroDoc

LOGGER = _loggers.marimo_logger()


class LoroDocManager:
    def __init__(self) -> None:
        self.loro_docs: dict[MarimoFileKey, LoroDoc] = {}
        self.loro_docs_lock = asyncio.Lock()
        self.loro_docs_clients: dict[
            MarimoFileKey, set[asyncio.Queue[bytes]]
        ] = {}
        # Hold subscription references to prevent garbage collection
        self._subscriptions: dict[MarimoFileKey, object] = {}

    async def register_doc(
        self,
        file_key: MarimoFileKey,
        doc: LoroDoc,
    ) -> None:
        """Register an existing LoroDoc (owned by a session's NotebookDocument).

        The session creates the LoroDoc at init time and the document
        model owns it for the lifetime of the session.  This method
        makes the same doc available for RTC client connections and
        subscribes to local updates so that server-originated changes
        (e.g. SetCode from kernel or file-watch) are broadcast to all
        connected RTC clients.
        """
        async with self.loro_docs_lock:
            if file_key in self.loro_docs:
                LOGGER.debug(
                    f"RTC: LoroDoc already registered for file {file_key}"
                )
                return
            # Ensure the languages map exists for the frontend
            doc.get_map("languages")
            LOGGER.debug(f"RTC: Registered LoroDoc for file {file_key}")
            self.loro_docs[file_key] = doc

            # Broadcast server-side Loro mutations to RTC clients.
            # The callback fires synchronously on doc.commit() — we
            # enqueue directly into client queues (non-blocking).
            def _on_local_update(update: bytes) -> bool:
                clients = self.loro_docs_clients.get(file_key, set())
                for client in clients:
                    client.put_nowait(update)
                return True  # keep subscription alive

            self._subscriptions[file_key] = doc.subscribe_local_update(
                _on_local_update
            )

    async def get_doc(self, file_key: MarimoFileKey) -> LoroDoc:
        """Get the LoroDoc registered for *file_key*.

        Raises ``KeyError`` if no doc has been registered via
        ``register_doc``.
        """
        async with self.loro_docs_lock:
            if file_key not in self.loro_docs:
                raise KeyError(f"No LoroDoc registered for file {file_key!r}")
            return self.loro_docs[file_key]

    def add_client_to_doc(
        self, file_key: MarimoFileKey, update_queue: asyncio.Queue[bytes]
    ) -> None:
        """Add a client queue to the loro doc clients."""
        if file_key not in self.loro_docs_clients:
            self.loro_docs_clients[file_key] = {update_queue}
        else:
            self.loro_docs_clients[file_key].add(update_queue)

    async def broadcast_update(
        self,
        file_key: MarimoFileKey,
        message: bytes,
        exclude_queue: Optional[asyncio.Queue[bytes]] = None,
    ) -> None:
        """Broadcast an update to all clients except the excluded queue."""
        clients = self.loro_docs_clients[file_key]
        for client in clients:
            if client == exclude_queue:
                continue
            client.put_nowait(message)

    async def remove_client(
        self,
        file_key: MarimoFileKey,
        update_queue: asyncio.Queue[bytes],
    ) -> None:
        """Remove an RTC client queue.

        The LoroDoc itself is *not* cleaned up when clients disconnect —
        it is owned by the session's ``NotebookDocument`` and lives for
        the session's lifetime.  Only the client tracking set is updated.
        """
        async with self.loro_docs_lock:
            if file_key not in self.loro_docs_clients:
                return
            self.loro_docs_clients[file_key].discard(update_queue)

    async def remove_doc(self, file_key: MarimoFileKey) -> None:
        """Unregister a LoroDoc and all associated client queues.

        Called when the session closes.
        """
        async with self.loro_docs_lock:
            self.loro_docs.pop(file_key, None)
            self.loro_docs_clients.pop(file_key, None)
            self._subscriptions.pop(file_key, None)
