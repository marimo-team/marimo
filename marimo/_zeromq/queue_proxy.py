# Copyright 2025 Marimo. All rights reserved.
"""Queue proxy for ZeroMQ sockets."""

from __future__ import annotations

import pickle
import threading
import typing

import zmq

from marimo._server.types import QueueType

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


def start_queue_receiver_thread(
    mapping: dict[zmq.Socket[bytes], QueueType[typing.Any]],
    stop_event: threading.Event,
) -> threading.Thread:
    """Start a thread to receive messages from ZeroMQ sockets and populate queues."""

    def receive_loop(
        mapping: dict[zmq.Socket[bytes], QueueType[typing.Any]],
        stop_event: threading.Event,
    ) -> None:
        """Receive messages from sockets and put them in queues using polling."""
        poller = zmq.Poller()
        for socket in mapping:
            poller.register(socket, zmq.POLLIN)

        while not stop_event.is_set():
            try:
                # Poll with 100ms timeout
                socks = dict(poller.poll(100))
                for socket, event in socks.items():
                    if event & zmq.POLLIN:
                        msg = socket.recv(flags=zmq.NOBLOCK)
                        obj = pickle.loads(msg)  # noqa: S301
                        mapping[socket].put(obj)

            except zmq.Again:  # noqa: PERF203
                # No message ready, continue polling
                continue
            except zmq.ZMQError:
                # Socket closed or other error
                break
            except Exception:  # noqa: BLE001, S112
                # Log error but continue
                continue

    thread = threading.Thread(
        target=receive_loop,
        args=(mapping, stop_event),
        daemon=True,
    )
    thread.start()
    return thread
