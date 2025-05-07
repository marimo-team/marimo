# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Optional

from marimo import _loggers
from marimo._server.file_router import MarimoFileKey
from marimo._types.ids import CellId_t

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
        self.loro_docs_cleaners: dict[
            MarimoFileKey, Optional[asyncio.Task[None]]
        ] = {}

    async def _clean_loro_doc(
        self, file_key: MarimoFileKey, timeout: float = 60
    ) -> None:
        """Clean up a loro doc if no clients are connected."""
        try:
            await asyncio.sleep(timeout)
            async with self.loro_docs_lock:
                if (
                    file_key in self.loro_docs_clients
                    and len(self.loro_docs_clients[file_key]) == 0
                ):
                    LOGGER.debug(
                        f"RTC: Removing loro doc for file {file_key} as it has no clients"
                    )
                    # Clean up the document
                    if file_key in self.loro_docs:
                        del self.loro_docs[file_key]
                    if file_key in self.loro_docs_clients:
                        del self.loro_docs_clients[file_key]
                    if file_key in self.loro_docs_cleaners:
                        del self.loro_docs_cleaners[file_key]
        except asyncio.CancelledError:
            # Task was cancelled due to client reconnection
            LOGGER.debug(
                f"RTC: clean_loro_doc task cancelled for file {file_key} - likely due to reconnection"
            )
            pass

    async def create_doc(
        self,
        file_key: MarimoFileKey,
        cell_ids: tuple[CellId_t, ...],
        codes: tuple[str, ...],
    ) -> LoroDoc:
        """Create a new loro doc."""
        from loro import LoroDoc, LoroText

        assert len(cell_ids) == len(codes), (
            "cell_ids and codes must be the same length"
        )

        async with self.loro_docs_lock:
            if file_key in self.loro_docs:
                return self.loro_docs[file_key]

            LOGGER.debug(f"RTC: Initializing LoroDoc for file {file_key}")
            doc = LoroDoc()  # type: ignore[no-untyped-call]
            self.loro_docs[file_key] = doc

            # Add all cell code to the doc
            doc_codes = doc.get_map("codes")
            doc.get_map("languages")
            for cell_id, code in zip(cell_ids, codes):
                cell_text = LoroText()  # type: ignore[no-untyped-call]
                cell_text.insert(0, code)
                doc_codes.insert_container(cell_id, cell_text)

                # We don't set the language here because it will be set
                # when the client connects for the first time.
        return doc

    async def get_or_create_doc(self, file_key: MarimoFileKey) -> LoroDoc:
        """Get or create a loro doc for a file key."""
        from loro import LoroDoc

        async with self.loro_docs_lock:
            if file_key in self.loro_docs:
                doc = self.loro_docs[file_key]
                # Cancel existing cleaner task if it exists
                cleaner = self.loro_docs_cleaners.get(file_key, None)
                if cleaner is not None:
                    LOGGER.debug(
                        f"RTC: Cancelling existing cleaner for file {file_key}"
                    )
                    cleaner.cancel()
                    self.loro_docs_cleaners[file_key] = None
            else:
                LOGGER.warning(f"RTC: Expected loro doc for file {file_key}")
                doc = LoroDoc()  # type: ignore[no-untyped-call]
                self.loro_docs[file_key] = doc
        return doc

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
        """Clean up a loro client and potentially the doc if no clients remain."""
        async with self.loro_docs_lock:
            self.loro_docs_clients[file_key].remove(update_queue)
            # If no clients are connected, set up a cleaner task
            if len(self.loro_docs_clients[file_key]) == 0:
                # Remove any existing cleaner
                cleaner = self.loro_docs_cleaners.get(file_key, None)
                if cleaner is not None:
                    cleaner.cancel()
                    self.loro_docs_cleaners[file_key] = None
                # Create a new cleaner with timeout of 60 seconds
                self.loro_docs_cleaners[file_key] = asyncio.create_task(
                    self._clean_loro_doc(file_key, 60.0)
                )
