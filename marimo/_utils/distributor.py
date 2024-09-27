# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import threading
import time
from typing import TYPE_CHECKING, Callable, Generic, TypeVar, Union

from marimo import _loggers
from marimo._utils.disposable import Disposable
from marimo._utils.typed_connection import TypedConnection

if TYPE_CHECKING:
    import queue

LOGGER = _loggers.marimo_logger()

T = TypeVar("T")


Consumer = Callable[[T], None]


class ConnectionDistributor(Generic[T]):
    """
    Used to distribute the response of a multiprocessing Connection to multiple
    consumers.

    This also handles adding and removing new consumers.

    NOTE: This class uses the `add_reader()` API, which requires the
    SelectorEventLoop to be used on Windows, not the default ProactorEventLoop.
    See

    https://bugs.python.org/issue37373#:~:text=On%20Windows%20there%20are%20two,subprocesses%20and%20generally%20lower%20scalability.

    for context.
    """

    def __init__(self, input_connection: TypedConnection[T]) -> None:
        self.consumers: list[Consumer[T]] = []
        self.input_connection = input_connection

    def add_consumer(self, consumer: Consumer[T]) -> Disposable:
        """Add a consumer to the distributor."""
        self.consumers.append(consumer)

        def _remove() -> None:
            if consumer in self.consumers:
                self.consumers.remove(consumer)

        return Disposable(_remove)

    def _on_change(self) -> None:
        """Distribute the response to all consumers."""
        retry_sleep_seconds = 0.001
        while self.input_connection.poll():
            try:
                # TODO: just recv_bytes (and change stream to send_bytes)
                # to eliminate pickling overhead/bugs
                response = self.input_connection.recv()
            except BlockingIOError as e:
                # recv() sporadically fails with EAGAIN, EDEADLK ...
                LOGGER.warning(
                    "BlockingIOError in distributor receive: %s", str(e)
                )
                time.sleep(retry_sleep_seconds)
                continue
            except (EOFError, StopIteration):
                break
            for consumer in self.consumers:
                consumer(response)

    def start(self) -> Disposable:
        """Start distributing the response."""
        asyncio.get_event_loop().add_reader(
            self.input_connection.fileno(), self._on_change
        )
        return Disposable(self.stop)

    def stop(self) -> None:
        """Stop distributing the response."""
        asyncio.get_event_loop().remove_reader(self.input_connection.fileno())
        if not self.input_connection.closed:
            self.input_connection.close()
        self.consumers.clear()

    def flush(self) -> None:
        """Flush the distributor."""
        while self.input_connection.poll():
            try:
                self.input_connection.recv()
            except EOFError:
                break


class QueueDistributor(Generic[T]):
    def __init__(self, queue: queue.Queue[Union[T, None]]) -> None:
        self.consumers: list[Consumer[T]] = []
        # distributor uses None as a signal to stop
        self.queue = queue
        self.thread: threading.Thread | None = None
        self._stop = False
        # protects the consumers list
        self._lock = threading.Lock()

    def add_consumer(self, consumer: Consumer[T]) -> Disposable:
        """Add a consumer to the distributor."""
        with self._lock:
            self.consumers.append(consumer)

        def _remove() -> None:
            with self._lock:
                if consumer in self.consumers:
                    self.consumers.remove(consumer)

        return Disposable(_remove)

    def _loop(self) -> None:
        while not self._stop:
            msg = self.queue.get()
            if msg is None:
                break

            with self._lock:
                for consumer in self.consumers:
                    consumer(msg)

    def start(self) -> threading.Thread:
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        return self.thread

    def stop(self) -> None:
        self.queue.put_nowait(None)

    def flush(self) -> None:
        """Flush the distributor."""
        pass
