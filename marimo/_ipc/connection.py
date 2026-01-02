# Copyright 2026 Marimo. All rights reserved.
"""ZeroMQ connection management for inter-process communication."""

from __future__ import annotations

import dataclasses
import queue
import sys
import typing

import zmq

from marimo import _loggers
from marimo._ipc.queue_proxy import PushQueue, start_receiver_thread
from marimo._ipc.types import ConnectionInfo
from marimo._session.queue import QueueType

if typing.TYPE_CHECKING:
    from marimo._messaging.types import KernelMessage
    from marimo._runtime.commands import (
        CodeCompletionCommand,
        CommandMessage,
        UpdateUIElementCommand,
    )

LOGGER = _loggers.marimo_logger()
ADDR = "tcp://127.0.0.1"

T = typing.TypeVar("T")


@dataclasses.dataclass
class Channel(typing.Generic[T]):
    """A typed communication channel wrapping a ZeroMQ socket and queue.

    Channels can be either:
    - Push: Send-only, uses PushQueue to immediately send via socket
    - Pull: Receive-only, uses Queue to buffer received messages
    """

    kind: typing.Literal["push", "pull"]
    socket: zmq.Socket[bytes]
    queue: QueueType[T]

    @classmethod
    def Push(
        cls, context: zmq.Context[zmq.Socket[bytes]], *, maxsize: int = 0
    ) -> Channel[T]:
        """Create a push (send-only) channel.

        Note: maxsize is ignored for push channels as ZeroMQ handles buffering.
        """
        socket = context.socket(zmq.PUSH)
        return cls(
            kind="push",
            socket=socket,
            queue=PushQueue(socket, maxsize=maxsize),
        )

    @classmethod
    def Pull(
        cls, context: zmq.Context[zmq.Socket[bytes]], *, maxsize: int = 0
    ) -> Channel[T]:
        """Create a pull (receive-only) channel.

        Args:
            context: ZeroMQ context for creating sockets
            maxsize: Maximum queue size (0 = unlimited)
        """
        socket = context.socket(zmq.PULL)
        return cls(
            kind="pull",
            socket=socket,
            queue=queue.Queue(maxsize=maxsize),
        )


@dataclasses.dataclass
class Connection:
    """Manages all ZeroMQ sockets for marimo IPC communication."""

    context: zmq.Context[zmq.Socket[bytes]]

    control: Channel[CommandMessage]
    ui_element: Channel[UpdateUIElementCommand]
    completion: Channel[CodeCompletionCommand]
    win32_interrupt: Channel[bool] | None

    input: Channel[str]
    stream: Channel[KernelMessage]

    def __post_init__(self) -> None:
        """Start receiver threads for all pull channels."""
        receivers: dict[zmq.Socket[bytes], QueueType[typing.Any]] = {}
        if self.control.kind == "pull":
            receivers[self.control.socket] = self.control.queue
        if self.ui_element.kind == "pull":
            receivers[self.ui_element.socket] = self.ui_element.queue
        if self.completion.kind == "pull":
            receivers[self.completion.socket] = self.completion.queue
        if self.win32_interrupt and self.win32_interrupt.kind == "pull":
            receivers[self.win32_interrupt.socket] = self.win32_interrupt.queue
        if self.input.kind == "pull":
            receivers[self.input.socket] = self.input.queue
        if self.stream.kind == "pull":
            receivers[self.stream.socket] = self.stream.queue

        self._stop_event, self._receiver_thread = start_receiver_thread(
            receivers
        )

    @classmethod
    def create(cls) -> tuple[Connection, ConnectionInfo]:
        """Create host-side connection with all sockets bound to random ports.

        Returns:
            Tuple of (Connection instance, ConnectionInfo with port numbers)
        """
        context = zmq.Context()
        conn = cls(
            context=context,
            control=Channel.Push(context),
            ui_element=Channel.Push(context),
            completion=Channel.Push(context),
            win32_interrupt=(
                Channel.Push(context) if sys.platform == "win32" else None
            ),
            input=Channel.Pull(context, maxsize=1),
            stream=Channel.Pull(context),
        )
        info = ConnectionInfo(
            control=conn.control.socket.bind_to_random_port(ADDR),
            ui_element=conn.ui_element.socket.bind_to_random_port(ADDR),
            completion=conn.completion.socket.bind_to_random_port(ADDR),
            input=conn.input.socket.bind_to_random_port(ADDR),
            stream=conn.stream.socket.bind_to_random_port(ADDR),
            win32_interrupt=conn.win32_interrupt.socket.bind_to_random_port(
                ADDR
            )
            if conn.win32_interrupt
            else None,
        )
        return conn, info

    @classmethod
    def connect(cls, connection_info: ConnectionInfo) -> Connection:
        """Connect to host with all sockets and start receivers.

        Args:
            connection_info: Port information from host

        Returns:
            Connected Connection instance
        """
        context = zmq.Context()

        conn = cls(
            context=context,
            control=Channel.Pull(context),
            ui_element=Channel.Pull(context),
            completion=Channel.Pull(context),
            win32_interrupt=Channel.Pull(context)
            if connection_info.win32_interrupt
            else None,
            input=Channel.Push(context, maxsize=1),
            stream=Channel.Push(context),
        )

        # Attach to existing ports
        conn.control.socket.connect(f"{ADDR}:{connection_info.control}")
        conn.ui_element.socket.connect(f"{ADDR}:{connection_info.ui_element}")
        conn.completion.socket.connect(f"{ADDR}:{connection_info.completion}")
        if conn.win32_interrupt:
            conn.win32_interrupt.socket.connect(
                f"{ADDR}:{connection_info.win32_interrupt}"
            )
        conn.input.socket.connect(f"{ADDR}:{connection_info.input}")
        conn.stream.socket.connect(f"{ADDR}:{connection_info.stream}")

        return conn

    def close(self) -> None:
        """Close all sockets and cleanup resources."""
        # Stop receiver thread
        self._stop_event.set()
        if self._receiver_thread.is_alive():
            self._receiver_thread.join(timeout=1)

        # Close all associated sockets (and finally terminate)
        self.context.destroy()
