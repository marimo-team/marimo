# Copyright 2026 Marimo. All rights reserved.
"""Queue proxy for ZeroMQ sockets."""

from __future__ import annotations

import threading
import typing

import msgspec

from marimo import _loggers
from marimo._session.queue import QueueType

LOGGER = _loggers.marimo_logger()

T = typing.TypeVar("T")

if typing.TYPE_CHECKING:
    import zmq

    from marimo._ipc.connection import Channel


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
        self.socket.send(msgspec.msgpack.encode(obj))

    def put_nowait(self, obj: T) -> None:
        """Put an item into the queue without blocking."""
        self.put(obj, block=False)

    def get(self, block: bool = True, timeout: float | None = None) -> T:
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
    channels: list[Channel[typing.Any]],
) -> tuple[threading.Event, threading.Thread]:
    """Start receiver thread."""
    import zmq

    def receive_loop(
        channels: list[Channel[typing.Any]],
        stop_event: threading.Event,
    ) -> None:
        """Receive messages from sockets and put them in queues using polling."""
        poller = zmq.Poller()
        socket_to_channel: dict[zmq.Socket[bytes], Channel[typing.Any]] = {}
        for channel in channels:
            poller.register(channel.socket, zmq.POLLIN)
            socket_to_channel[channel.socket] = channel

        while not stop_event.is_set():
            try:
                # Poll with 100ms timeout
                socks = dict(poller.poll(100))
                for socket, event in socks.items():
                    if event & zmq.POLLIN:
                        ch = socket_to_channel[socket]
                        msg = socket.recv(flags=zmq.NOBLOCK)
                        assert ch.decoder is not None, (
                            "Pull channel must have a decoder"
                        )
                        ch.queue.put(ch.decoder.decode(msg))
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
        args=(channels, stop_event),
        daemon=True,
    )
    thread.start()
    return stop_event, thread
