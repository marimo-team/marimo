# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Callable

from starlette.websockets import WebSocketDisconnect, WebSocketState

from marimo import _loggers
from marimo._messaging.notification import (
    CompletionResultNotification,
    FocusCellNotification,
)
from marimo._messaging.serde import deserialize_kernel_notification_name
from marimo._messaging.types import KernelMessage

if TYPE_CHECKING:
    from starlette.websockets import WebSocket

LOGGER = _loggers.marimo_logger()

# Operations that are only sent in kiosk mode
KIOSK_ONLY_OPERATIONS = {
    FocusCellNotification.name,
}

# Operations that are excluded from kiosk mode
KIOSK_EXCLUDED_OPERATIONS = {
    CompletionResultNotification.name,
}


class WebSocketMessageLoop:
    """Handles the async message send/receive loops for WebSocket."""

    def __init__(
        self,
        websocket: WebSocket,
        message_queue: asyncio.Queue[KernelMessage],
        kiosk: bool,
        on_disconnect: Callable[[Exception, Callable[[], Any]], None],
        on_check_status_update: Callable[[], None],
    ):
        self.websocket = websocket
        self.message_queue = message_queue
        self.kiosk = kiosk
        self.on_disconnect = on_disconnect
        self.on_check_status_update = on_check_status_update
        self._listen_messages_task: asyncio.Task[None] | None = None
        self._listen_disconnect_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the message loops.

        Runs two concurrent tasks:
        - listen_for_messages: Sends messages from kernel to frontend
        - listen_for_disconnect: Detects when WebSocket disconnects
        """
        self._listen_messages_task = asyncio.create_task(
            self._listen_for_messages()
        )
        self._listen_disconnect_task = asyncio.create_task(
            self._listen_for_disconnect()
        )

        await asyncio.gather(
            self._listen_messages_task,
            self._listen_disconnect_task,
        )

    async def _listen_for_messages(self) -> None:
        """Listen for messages from kernel and send to frontend."""
        while True:
            data = await self.message_queue.get()
            op: str = deserialize_kernel_notification_name(data)

            if self._should_filter_operation(op):
                continue

            # Serialize message
            try:
                text = f'{{"op": "{op}", "data": {data.decode("utf-8")}}}'
            except Exception as e:
                LOGGER.error("Failed to deserialize message: %s", str(e))
                LOGGER.error("Message: %s", data)
                continue

            # Send to WebSocket
            try:
                await self.websocket.send_text(text)
            except WebSocketDisconnect as e:
                self.on_disconnect(e, self._cancel_disconnect_task)
            except RuntimeError as e:
                # Starlette can raise a runtime error if a message is sent
                # when the socket is closed. In case the disconnection
                # error hasn't made its way to listen_for_disconnect, do
                # the cleanup here.
                if (
                    self.websocket.application_state
                    == WebSocketState.DISCONNECTED
                ):
                    self.on_disconnect(e, self._cancel_disconnect_task)
                else:
                    LOGGER.error(
                        "Error sending message to frontend: %s", str(e)
                    )
            except Exception as e:
                LOGGER.error("Error sending message to frontend: %s", str(e))
                raise e

    async def _listen_for_disconnect(self) -> None:
        """Listen for WebSocket disconnect."""
        try:
            # Check for marimo updates when connection starts
            self.on_check_status_update()
            # Wait for disconnection
            await self.websocket.receive_text()
        except WebSocketDisconnect as e:
            self.on_disconnect(e, self._cancel_messages_task)
        except Exception as e:
            LOGGER.error("Error listening for disconnect: %s", str(e))
            raise e

    def _should_filter_operation(self, op: str) -> bool:
        """Determine if operation should be filtered based on kiosk mode.

        Args:
            op: Operation name to check

        Returns:
            True if the operation should be filtered (not sent), False
            otherwise.
        """
        if op in KIOSK_ONLY_OPERATIONS and not self.kiosk:
            LOGGER.debug(
                "Ignoring operation %s, not in kiosk mode",
                op,
            )
            return True
        if op in KIOSK_EXCLUDED_OPERATIONS and self.kiosk:
            LOGGER.debug(
                "Ignoring operation %s, in kiosk mode",
                op,
            )
            return True
        return False

    def _cancel_messages_task(self) -> None:
        """Cancel the messages task."""
        if (
            self._listen_messages_task
            and not self._listen_messages_task.done()
        ):
            self._listen_messages_task.cancel()

    def _cancel_disconnect_task(self) -> None:
        """Cancel the disconnect task."""
        if (
            self._listen_disconnect_task
            and not self._listen_disconnect_task.done()
        ):
            self._listen_disconnect_task.cancel()
