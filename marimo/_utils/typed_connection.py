# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from multiprocessing.connection import Connection

T = TypeVar("T")


class TypedConnection(Generic[T]):
    """Wrapper around a connection with strong typing."""

    def __init__(self, delegate: Connection):
        self._delegate = delegate

    @classmethod
    def of(
        cls,
        delegate: Connection,
    ) -> TypedConnection[T]:
        """Create a typed connection from a connection."""
        return delegate  # type: ignore[return-value]

    def send(self, obj: T) -> None:
        self._delegate.send(obj)

    def recv(self) -> T:
        return self._delegate.recv()  # type: ignore[no-any-return]

    def poll(self) -> bool:
        return self._delegate.poll()

    def fileno(self) -> int:
        return self._delegate.fileno()

    @property
    def closed(self) -> bool:
        return self._delegate.closed

    def close(self) -> None:
        self._delegate.close()
