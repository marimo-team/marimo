# Copyright 2026 Marimo. All rights reserved.
"""Bridge blocking-looking waits to Pyodide `run_sync`."""

from __future__ import annotations

import asyncio
import importlib
import inspect
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable


class UnsupportedWasmConcurrencyError(RuntimeError):
    """Raised when a shimmed API needs unsupported WASM runtime support."""


def cooperative_wait(awaitable: Awaitable[Any]) -> Any:
    try:
        ffi = importlib.import_module("pyodide.ffi")
        run_sync = ffi.run_sync
    except (ImportError, AttributeError) as exc:
        _close_coroutine(awaitable)
        raise UnsupportedWasmConcurrencyError(
            "Blocking WASM concurrency operations require pyodide.ffi.run_sync"
        ) from exc

    can_run_sync = getattr(ffi, "can_run_sync", None)
    if callable(can_run_sync) and not can_run_sync():
        _close_coroutine(awaitable)
        raise UnsupportedWasmConcurrencyError(
            "Blocking WASM concurrency operations require a JSPI promising frame"
        )

    return run_sync(awaitable)


async def wait_for_future(
    future: asyncio.Future[Any], timeout: float | None
) -> bool:
    return await wait_with_timeout(asyncio.shield(future), timeout)


async def wait_with_timeout(
    awaitable: Awaitable[Any], timeout: float | None
) -> bool:
    """Wait for an awaitable without scheduling absolute deadlines.

    Pyodide's web loop rejects `call_at()` deadlines that have already elapsed.
    A sleep task keeps timed waits relative to the moment the coroutine runs.
    """
    if timeout is None:
        await awaitable
        return True
    if timeout <= 0:
        _close_coroutine(awaitable)
        return False

    wait_task = asyncio.ensure_future(awaitable)
    timeout_task = asyncio.create_task(asyncio.sleep(timeout))
    try:
        done, _pending = await asyncio.wait(
            (wait_task, timeout_task),
            return_when=asyncio.FIRST_COMPLETED,
        )
        if wait_task in done:
            await wait_task
            return True
        return False
    finally:
        for task in (wait_task, timeout_task):
            if not task.done():
                task.cancel()
        await asyncio.gather(wait_task, timeout_task, return_exceptions=True)


def _close_coroutine(awaitable: Awaitable[Any]) -> None:
    if inspect.iscoroutine(awaitable):
        awaitable.close()
