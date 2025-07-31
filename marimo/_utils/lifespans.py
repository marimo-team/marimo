# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import contextlib
import sys
from collections.abc import AsyncIterator, Sequence
from contextlib import AbstractAsyncContextManager
from typing import Any, Generic, TypeVar

from marimo import _loggers
from marimo._types.lifespan import Lifespan

if sys.version_info < (3, 10):
    from typing_extensions import TypeAlias
else:
    from typing import TypeAlias

T = TypeVar("T", bound=Any)

LifespanList: TypeAlias = Sequence[Lifespan[T]]

LOGGER = _loggers.marimo_logger()


class Lifespans(Generic[T]):
    """
    A compound lifespan that runs a list of lifespans in order.
    """

    def __init__(
        self,
        lifespans: LifespanList[T],
    ) -> None:
        self._lifespans = lifespans

    def has_lifespans(self) -> bool:
        return bool(self._lifespans)

    @contextlib.asynccontextmanager
    async def _manager(
        self,
        app: T,
        lifespans: LifespanList[T],
    ) -> AsyncIterator[None]:
        exit_stack = contextlib.AsyncExitStack()
        try:
            async with exit_stack:
                for lifespan in lifespans:
                    LOGGER.debug(f"Setup: {lifespan.__name__}")
                    await exit_stack.enter_async_context(lifespan(app))
                yield
        except asyncio.CancelledError:
            pass

    def __call__(self, app: T) -> AbstractAsyncContextManager[None]:
        return self._manager(app, lifespans=self._lifespans)

    def __repr__(self) -> str:
        return f"Lifespans({self._lifespans})"
