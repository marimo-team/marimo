# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from starlette.websockets import WebSocketDisconnect, WebSocketState

from marimo import _loggers
from marimo._messaging.notification import (
    CompletionResultNotification,
    FocusCellNotification,
)
from marimo._messaging.serde import deserialize_kernel_notification_name
from marimo._messaging.types import KernelMessage
from marimo._server.api.endpoints.ws.ws_formatter import format_wire_message

if TYPE_CHECKING:
    from collections.abc import Callable

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


def _should_filter_operation(op: str, *, is_kiosk: bool) -> bool:
    """Determine if operation should be filtered based on kiosk mode.

    Args:
        op: Operation name to check
        is_kiosk: Whether the connection is in kiosk (viewer) mode

    Returns:
        True if the operation should be filtered (not sent), False
        otherwise.
    """
    if op in KIOSK_ONLY_OPERATIONS and not is_kiosk:
        LOGGER.debug(
            "Ignoring operation %s, not in kiosk mode",
            op,
        )
        return True
    if op in KIOSK_EXCLUDED_OPERATIONS and is_kiosk:
        LOGGER.debug(
            "Ignoring operation %s, in kiosk mode",
            op,
        )
        return True
    return False


def prepare_wire_message(data: KernelMessage, *, is_kiosk: bool) -> str | None:
    """Filter and serialize a kernel message for the frontend.

    Shared by the WebSocket and SSE transports so both apply identical
    kiosk filtering and produce identical wire payloads.

    Returns:
        The wire-format text, or None if the message is filtered out or
        fails to serialize.
    """
    op: str = deserialize_kernel_notification_name(data)

    if _should_filter_operation(op, is_kiosk=is_kiosk):
        return None

    try:
        return format_wire_message(op, data)
    except Exception as e:
        LOGGER.error("Failed to deserialize message: %s", str(e))
        LOGGER.error("Message: %s", data)
        return None


class WebSocketMessageLoop:
    """Handles the async message send/receive loops for WebSocket."""

    def __init__(
        self,
        websocket: WebSocket,
        message_queue: asyncio.Queue[KernelMessage],
        is_kiosk: Callable[[], bool],
        on_check_status_update: Callable[[], None],
    ):
        self.websocket = websocket
        self.message_queue = message_queue
        self.is_kiosk = is_kiosk
        self.on_check_status_update = on_check_status_update

    async def start(self) -> None:
        """Start the message loops.

        Runs two concurrent tasks:
        - listen_for_messages: Sends messages from kernel to frontend
        - listen_for_disconnect: Detects when WebSocket disconnects
        """
        tasks = (
            asyncio.create_task(self._listen_for_messages()),
            asyncio.create_task(self._listen_for_disconnect()),
        )
        try:
            done, _ = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                task.result()
        except WebSocketDisconnect:
            pass
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _listen_for_messages(self) -> None:
        """Listen for messages from kernel and send to frontend."""
        while True:
            data = await self.message_queue.get()
            text = prepare_wire_message(data, is_kiosk=self.is_kiosk())
            if text is None:
                continue

            # Send to WebSocket
            try:
                await self.websocket.send_text(text)
            except RuntimeError:
                # Starlette can raise a runtime error if a message is sent
                # when the socket is closed. In case the disconnection
                # error hasn't made its way to listen_for_disconnect, do
                # the cleanup here.
                if (
                    self.websocket.application_state
                    == WebSocketState.DISCONNECTED
                ):
                    return
                raise

    async def _listen_for_disconnect(self) -> None:
        """Listen for WebSocket disconnect."""
        self.on_check_status_update()
        while True:
            await self.websocket.receive_text()
