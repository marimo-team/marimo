# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Optional, Protocol, TypeVar, Union

T = TypeVar("T")


class QueueType(Protocol[T]):
    """
    Minimal queue protocol used by Marimo.

    Defines the common subset of methods shared by `multiprocessing.Queue` and
    `queue.Queue` that Marimo depends on. Keeping this protocol minimal makes it
    straightforward to stub in `marimo-lsp` and to substitute alternative queue
    implementations (e.g., wrapping a ZeroMQ socket).

    If additional queue behavior becomes necessary, expand this protocol so that
    stubs and implementations stay aligned.
    """

    def get(
        self, block: bool = True, timeout: Union[float, None] = None
    ) -> T: ...
    def put(
        self, obj: T, /, block: bool = True, timeout: Union[float, None] = None
    ) -> None: ...
    def get_nowait(self) -> T: ...
    def put_nowait(self, item: T, /) -> None: ...
    def empty(self) -> bool: ...


class ProcessLike(Protocol):
    """Protocol for process-like objects."""

    @property
    def pid(self) -> int | None: ...

    def is_alive(self) -> bool: ...

    def terminate(self) -> None: ...

    def join(self, timeout: Optional[float] = None) -> None: ...
