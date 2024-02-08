# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from threading import Thread
from typing import Callable, Generic, TypeVar

from marimo import _loggers
from marimo._utils.disposable import Disposable
from marimo._utils.typed_connection import TypedConnection

LOGGER = _loggers.marimo_logger()

T = TypeVar("T")


class Distributor(Generic[T]):
    """
    Used to distribute the response of a multiprocessing Connection to multiple
    consumers.

    This also handles adding and removing new consumers.
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
        while self.input_connection.poll():
            try:
                response = self.input_connection.recv()
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
