# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from starlette.websockets import WebSocketDisconnect

from marimo import _loggers

if TYPE_CHECKING:
    from loro import DiffEvent, ExportMode, LoroDoc
    from starlette.websockets import WebSocket

    from marimo._server.file_router import MarimoFileKey
    from marimo._server.rtc.doc import LoroDocManager

LOGGER = _loggers.marimo_logger()


class RTCWebSocketHandler:
    """Handles Real-Time Collaboration WebSocket connections."""

    def __init__(
        self,
        websocket: WebSocket,
        file_key: MarimoFileKey,
        doc_manager: LoroDocManager,
    ):
        self.websocket = websocket
        self.file_key = file_key
        self.doc_manager = doc_manager

    async def handle(self) -> None:
        """Handle RTC WebSocket connection lifecycle.

        Manages the full lifecycle of an RTC WebSocket connection:
        1. Accept the connection
        2. Get or create LoroDoc
        3. Send initial sync to client
        4. Subscribe to updates
        5. Handle bidirectional updates
        6. Cleanup on disconnect
        """
        from loro import ExportMode

        await self.websocket.accept()

        # Get or create the LoroDoc and add the client to it
        LOGGER.debug("RTC: getting document")
        update_queue: asyncio.Queue[bytes] = asyncio.Queue()
        doc = await self.doc_manager.get_or_create_doc(self.file_key)
        self.doc_manager.add_client_to_doc(self.file_key, update_queue)

        # Send initial sync to client
        await self._send_initial_sync(doc, ExportMode)

        # Set up update handling
        def handle_doc_update(event: DiffEvent) -> None:
            LOGGER.debug("RTC: doc updated", event)

        # Subscribe to LoroDoc updates
        subscription = doc.subscribe_root(handle_doc_update)

        # Create async task to send updates to the client
        send_task = asyncio.create_task(
            self._send_updates_to_client(update_queue)
        )

        try:
            # Listen for updates from the client
            await self._receive_updates_from_client(doc, update_queue)
        except WebSocketDisconnect:
            LOGGER.debug("RTC: WebSocket disconnected")
        except Exception as e:
            LOGGER.warning(
                f"RTC: Exception in websocket loop for file {self.file_key}: {str(e)}"
            )
        finally:
            LOGGER.debug("RTC: Cleaning up resources")
            # Cleanup resources
            send_task.cancel()
            subscription.unsubscribe()
            await self.doc_manager.remove_client(self.file_key, update_queue)

    async def _send_initial_sync(
        self, doc: LoroDoc, export_mode: type[ExportMode]
    ) -> None:
        """Send initial document sync to client.

        Args:
            doc: LoroDoc instance
            export_mode: ExportMode from loro module
        """
        # Use shallow snapshot for fewer bytes
        LOGGER.debug("RTC: sending initial sync")
        init_sync_msg = doc.export(
            export_mode.ShallowSnapshot(frontiers=doc.state_frontiers)
        )
        await self.websocket.send_bytes(init_sync_msg)
        LOGGER.debug("RTC: initial sync sent")

    async def _send_updates_to_client(
        self, update_queue: asyncio.Queue[bytes]
    ) -> None:
        """Send updates from the document to the client.

        Args:
            update_queue: Queue of updates to send to client
        """
        try:
            while True:
                update = await update_queue.get()
                await self.websocket.send_bytes(update)
        except Exception as e:
            LOGGER.warning(
                f"RTC: Could not send loro update to client for file {self.file_key}: {str(e)}",
            )

    async def _receive_updates_from_client(
        self, doc: LoroDoc, update_queue: asyncio.Queue[bytes]
    ) -> None:
        """Receive and process updates from the client.

        Args:
            doc: LoroDoc instance
            update_queue: Queue used to avoid sending updates back to sender
        """
        while True:
            message = await self.websocket.receive_bytes()
            # Broadcast to other clients (but not back to sender)
            await self.doc_manager.broadcast_update(
                self.file_key, message, update_queue
            )

            # Check if the message is an awareness update
            if message.startswith(b"awareness:"):
                LOGGER.debug("RTC: received awareness update")
            else:
                # Apply the update to the LoroDoc
                doc.import_(message)
