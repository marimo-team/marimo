# Copyright 2026 Marimo. All rights reserved.
"""Queue proxy for ZeroMQ sockets."""

from __future__ import annotations

import pickle
import threading
import typing

import zmq

from marimo import _loggers
from marimo._session.queue import QueueType

LOGGER = _loggers.marimo_logger()

T = typing.TypeVar("T")


class PushQueue(QueueType[T]):
    """Queue for pushing messages through ZeroMQ socket (sender side only).

    This is a simple wrapper that sends messages over a ZeroMQ PUSH socket.
    """

    def __init__(
        self,
        socket: zmq.Socket[bytes],
        *,
        maxsize: int = 0,
    ) -> None:
        self.socket = socket
        self.maxsize = maxsize

    def put(
        self,
        obj: T,
        block: bool = True,  # noqa: ARG002
        timeout: float | None = None,  # noqa: ARG002
    ) -> None:
        """Put an item into the queue."""
        self.socket.send(pickle.dumps(obj))

    def put_nowait(self, obj: T) -> None:
        """Put an item into the queue without blocking."""
        self.put(obj, block=False)

    def get(self, block: bool = True, timeout: float | None = None) -> T:  # noqa: FBT001, FBT002
        """Get an item from the queue (stub - not implemented for PushQueue)."""
        msg = "PushQueue does not support get operations"
        raise NotImplementedError(msg)

    def get_nowait(self) -> T:
        """Get an item from the queue without blocking (stub - not implemented)."""
        msg = "PushQueue does not support get operations"
        raise NotImplementedError(msg)

    def empty(self) -> bool:
        """Return True if the queue is empty (stub - not implemented for PushQueue)."""
        msg = "PushQueue does not support empty() operation"
        raise NotImplementedError(msg)


def start_receiver_thread(
    receivers: dict[zmq.Socket[bytes], QueueType[typing.Any]],
) -> tuple[threading.Event, threading.Thread]:
    """Start receiver thread."""

    def receive_loop(
        receivers: dict[zmq.Socket[bytes], QueueType[typing.Any]],
        stop_event: threading.Event,
    ) -> None:
        """Receive messages from sockets and put them in queues using polling."""
        poller = zmq.Poller()
        for socket in receivers:
            poller.register(socket, zmq.POLLIN)

        while not stop_event.is_set():
            try:
                # Poll with 100ms timeout
                socks = dict(poller.poll(100))
                for socket, event in socks.items():
                    if event & zmq.POLLIN:
                        msg = socket.recv(flags=zmq.NOBLOCK)
                        obj = pickle.loads(msg)
                        receivers[socket].put(obj)
            except zmq.Again:
                continue
            except zmq.ZMQError as e:
                LOGGER.debug(f"ZeroMQ socket error in receiver thread: {e}")
                break
            except Exception as e:
                LOGGER.warning(
                    f"Unexpected error in ZeroMQ receiver thread: {e}",
                    exc_info=True,
                )
                continue

    stop_event = threading.Event()
    thread = threading.Thread(
        target=receive_loop,
        args=(receivers, stop_event),
        daemon=True,
    )
    thread.start()
    return stop_event, thread
