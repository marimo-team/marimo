# Copyright 2026 Marimo. All rights reserved.
"""Queue manager for generic inter-process communication."""

from __future__ import annotations

import dataclasses
import typing

from marimo._ipc.connection import Connection
from marimo._ipc.types import ConnectionInfo

if typing.TYPE_CHECKING:
    from marimo._messaging.types import KernelMessage
    from marimo._runtime.commands import (
        CodeCompletionCommand,
        CommandMessage,
        UpdateUIElementCommand,
    )
    from marimo._session.queue import QueueType


@dataclasses.dataclass
class QueueManager:
    """High-level interface for inter-process communication queues.

    Usage:
        # Host side - create and bind
        host_manager, connection_info = QueueManager.create()

        # Kernel side - connect
        kernel_manager = QueueManager.connect(connection_info)

        # Send/receive messages through queues
        host_manager.control_queue.put(request)
        response = kernel_manager.stream_queue.get()
    """

    conn: Connection

    @property
    def control_queue(self) -> QueueType[CommandMessage]:
        """Queue for control requests (execute, interrupt, etc.)."""
        return self.conn.control.queue

    @property
    def set_ui_element_queue(self) -> QueueType[UpdateUIElementCommand]:
        """Queue for UI element value updates."""
        return self.conn.ui_element.queue

    @property
    def completion_queue(self) -> QueueType[CodeCompletionCommand]:
        """Queue for code completion requests."""
        return self.conn.completion.queue

    @property
    def win32_interrupt_queue(self) -> typing.Union[QueueType[bool], None]:
        """Queue for Windows interrupt signals (None on non-Windows)."""
        return (
            self.conn.win32_interrupt.queue
            if self.conn.win32_interrupt
            else None
        )

    @property
    def input_queue(self) -> QueueType[str]:
        """Queue for user input responses."""
        return self.conn.input.queue

    @property
    def stream_queue(self) -> QueueType[KernelMessage]:
        """Queue for kernel output messages."""
        return self.conn.stream.queue

    def close_queues(self) -> None:
        """Close all queues and cleanup resources."""
        self.conn.close()

    @classmethod
    def create(
        cls,
    ) -> tuple[QueueManager, ConnectionInfo]:
        """Create host-side queue manager with all sockets bound.

        Returns:
            Tuple of (QueueManager instance, ConnectionInfo for kernel)
        """
        conn, info = Connection.create()
        return cls(conn=conn), info

    @classmethod
    def connect(
        cls,
        connection_info: ConnectionInfo,
    ) -> QueueManager:
        """Connect to host and create kernel-side queue manager.

        Args:
            connection_info: Connection details from host

        Returns:
            Connected QueueManager instance
        """
        return cls(conn=Connection.connect(connection_info))
