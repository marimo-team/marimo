from __future__ import annotations

from multiprocessing.connection import Connection
from typing import Generic, TypeVar

T = TypeVar("T")


class TypedConnection(Generic[T], Connection):
    """Wrapper around a connection with strong typing."""

    @staticmethod
    def of(
        delegate: Connection,
    ) -> TypedConnection[T]:
        """Create a typed connection from a connection."""
        return delegate  # type: ignore

    def send(self, obj: T) -> None:
        super().send(obj)

    def recv(self) -> T:
        return super().recv()
