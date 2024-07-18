# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Callable, Generic, TypeVar

from marimo import _loggers
from marimo._utils.disposable import Disposable
from marimo._utils.typed_connection import TypedConnection

if TYPE_CHECKING:
    from threading import Thread

LOGGER = _loggers.marimo_logger()

T = TypeVar("T")


class Distributor(Generic[T]):
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
        self.consumers: list[Callable[[T], None]] = []
        self.input_connection = input_connection
        self.thread: Thread | None = None

    def add_consumer(self, consumer: Callable[[T], None]) -> Disposable:
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
