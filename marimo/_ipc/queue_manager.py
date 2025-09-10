# Copyright 2025 Marimo. All rights reserved.
"""ZeroMQ-based QueueManager implementation."""

from __future__ import annotations

import dataclasses
import queue
import sys
import threading
import typing

import zmq

from marimo._ipc.queue_proxy import PushQueue, start_queue_receiver_thread
from marimo._ipc.types import ConnectionInfo

if typing.TYPE_CHECKING:
    from marimo._messaging.types import KernelMessage
    from marimo._runtime.requests import (
        CodeCompletionRequest,
        ControlRequest,
        SetUIElementValueRequest,
    )
    from marimo._server.types import QueueType

ADDR = "tcp://127.0.0.1"


@dataclasses.dataclass
class Connection:
    """Marimo socket connection info."""

    context: zmq.Context[zmq.Socket[bytes]]

    control: zmq.Socket[bytes]
    ui_element: zmq.Socket[bytes]
    completion: zmq.Socket[bytes]
    win32_interrupt: zmq.Socket[bytes] | None

    input: zmq.Socket[bytes]
    stream: zmq.Socket[bytes]

    def close(self) -> None:
        """Close all sockets and connections."""
        self.control.close()
        self.ui_element.close()
        self.completion.close()
        if self.win32_interrupt:
            self.win32_interrupt.close()

        self.input.close()
        self.stream.close()

        self.context.term()


@dataclasses.dataclass
class QueueManager:
    """Queue manager using ZeroMQ for inter-process communication."""

    conn: Connection

    control_queue: QueueType[ControlRequest]
    set_ui_element_queue: QueueType[SetUIElementValueRequest]
    completion_queue: QueueType[CodeCompletionRequest]
    win32_interrupt_queue: QueueType[bool] | None

    input_queue: QueueType[str]
    stream_queue: QueueType[KernelMessage]

    def __post_init__(self) -> None:
        self._stop_event = threading.Event()
        self._receiver_thread: threading.Thread | None = None

    def start(self) -> None:
        """Start receiver thread."""
        assert self._receiver_thread is None, "Already started"

        receivers: dict[zmq.Socket[bytes], QueueType[typing.Any]] = {}

        if self.conn.control.getsockopt(zmq.TYPE) == zmq.PULL:
            receivers[self.conn.control] = self.control_queue
        if self.conn.ui_element.getsockopt(zmq.TYPE) == zmq.PULL:
            receivers[self.conn.ui_element] = self.set_ui_element_queue
        if (
            self.conn.win32_interrupt
            and self.conn.win32_interrupt.getsockopt(zmq.TYPE) == zmq.PULL
        ):
            assert self.win32_interrupt_queue, "Expected win32_interrupt_queue"
            receivers[self.conn.win32_interrupt] = self.win32_interrupt_queue
        if self.conn.completion.getsockopt(zmq.TYPE) == zmq.PULL:
            receivers[self.conn.completion] = self.completion_queue
        if self.conn.input.getsockopt(zmq.TYPE) == zmq.PULL:
            receivers[self.conn.input] = self.input_queue
        if self.conn.stream.getsockopt(zmq.TYPE) == zmq.PULL:
            receivers[self.conn.stream] = self.stream_queue

        self._receiver_thread = start_queue_receiver_thread(
            receivers, self._stop_event
        )

    def close_queues(self) -> None:
        """Close all queues and cleanup resources."""
        self._stop_event.set()
        if self._receiver_thread and self._receiver_thread.is_alive():
            self._receiver_thread.join(timeout=1)
        self.conn.close()

    @classmethod
    def create(
        cls,
    ) -> tuple[QueueManager, ConnectionInfo]:
        """Create host-side connections with all sockets and start receivers."""
        context = zmq.Context()

        conn = Connection(
            context=context,
            control=context.socket(zmq.PUSH),
            ui_element=context.socket(zmq.PUSH),
            completion=context.socket(zmq.PUSH),
            win32_interrupt=context.socket(zmq.PUSH)
            if sys.platform == "win32"
            else None,
            input=context.socket(zmq.PULL),
            stream=context.socket(zmq.PULL),
        )

        # Bind each socket to a port
        info = ConnectionInfo(
            control=conn.control.bind_to_random_port(ADDR),
            ui_element=conn.ui_element.bind_to_random_port(ADDR),
            completion=conn.completion.bind_to_random_port(ADDR),
            input=conn.input.bind_to_random_port(ADDR),
            stream=conn.stream.bind_to_random_port(ADDR),
            win32_interrupt=conn.win32_interrupt.bind_to_random_port(ADDR)
            if conn.win32_interrupt
            else None,
        )

        queue_manager = cls(
            conn=conn,
            # push queues
            control_queue=PushQueue(conn.control),
            set_ui_element_queue=PushQueue(conn.ui_element),
            completion_queue=PushQueue(conn.completion),
            win32_interrupt_queue=PushQueue(conn.win32_interrupt)
            if conn.win32_interrupt
            else None,
            # pull queues
            input_queue=queue.Queue(maxsize=1),
            stream_queue=queue.Queue(),
        )
        queue_manager.start()

        return queue_manager, info

    @classmethod
    def connect(
        cls,
        connection_info: ConnectionInfo,
    ) -> QueueManager:
        """Connect to host with all sockets and start receivers."""
        context = zmq.Context()

        # Create all sockets (inverse of host)
        conn = Connection(
            context=context,
            control=context.socket(zmq.PULL),
            ui_element=context.socket(zmq.PULL),
            completion=context.socket(zmq.PULL),
            win32_interrupt=context.socket(zmq.PULL)
            if connection_info.win32_interrupt
            else None,
            input=context.socket(zmq.PUSH),
            stream=context.socket(zmq.PUSH),
        )

        # Attach to existing ports
        conn.control.connect(f"{ADDR}:{connection_info.control}")
        conn.ui_element.connect(f"{ADDR}:{connection_info.ui_element}")
        conn.completion.connect(f"{ADDR}:{connection_info.completion}")
        if conn.win32_interrupt and connection_info.win32_interrupt:
            conn.win32_interrupt.connect(
                f"{ADDR}:{connection_info.win32_interrupt}"
            )

        conn.input.connect(f"{ADDR}:{connection_info.input}")
        conn.stream.connect(f"{ADDR}:{connection_info.stream}")

        queue_manager = cls(
            conn=conn,
            # pull queues
            control_queue=queue.Queue(),
            set_ui_element_queue=queue.Queue(),
            completion_queue=queue.Queue(),
            win32_interrupt_queue=queue.Queue()
            if conn.win32_interrupt
            else None,
            # push queues
            input_queue=PushQueue(conn.input, maxsize=1),
            stream_queue=PushQueue(conn.stream),
        )
        queue_manager.start()

        return queue_manager
