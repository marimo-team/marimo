# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

T = TypeVar("T")
R = TypeVar("R")


async def bounded_map(
    function: Callable[[T], Awaitable[R]],
    items: Sequence[T],
    *,
    concurrency: int,
) -> list[R]:
    """Map in input order with bounded tasks and in-flight work.

    Failure or cancellation cancels and drains all workers before returning.
    Callers that need partial success should handle errors in `function`.
    """
    if concurrency < 1:
        raise ValueError("concurrency must be positive")

    pending = iter(enumerate(items))
    results: dict[int, R] = {}

    async def worker() -> None:
        for index, item in pending:
            results[index] = await function(item)

    tasks = [
        asyncio.create_task(worker())
        for _ in range(min(concurrency, len(items)))
    ]
    try:
        await asyncio.gather(*tasks)
        return [results[index] for index in range(len(items))]
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
