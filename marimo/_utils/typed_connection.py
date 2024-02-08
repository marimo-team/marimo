# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from multiprocessing.connection import Connection
from typing import Generic, TypeVar

T = TypeVar("T")


class TypedConnection(Generic[T], Connection):
    """Wrapper around a connection with strong typing."""

    @classmethod
    def of(
        cls,
        delegate: Connection,
    ) -> TypedConnection[T]:
        """Create a typed connection from a connection."""
        return delegate  # type: ignore[return-value]

    def send(self, obj: T) -> None:
        super().send(obj)

    def recv(self) -> T:
        return super().recv()  # type: ignore[no-any-return]
