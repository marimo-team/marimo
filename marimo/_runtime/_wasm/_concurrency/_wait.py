# Copyright 2026 Marimo. All rights reserved.
"""Run blocking WASM waits through Pyodide JSPI."""

from __future__ import annotations

import importlib
import inspect
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable


class UnsupportedWasmThreadingError(RuntimeError):
    """Raised when a threading wait needs missing Pyodide runtime support."""


def cooperative_wait(awaitable: Awaitable[Any]) -> Any:
    try:
        ffi = importlib.import_module("pyodide.ffi")
        run_sync = ffi.run_sync
    except (ImportError, AttributeError) as exc:
        _close_coroutine(awaitable)
        raise UnsupportedWasmThreadingError(
            "Blocking WASM threading waits require pyodide.ffi.run_sync"
        ) from exc

    can_run_sync = getattr(ffi, "can_run_sync", None)
    if callable(can_run_sync) and not can_run_sync():
        _close_coroutine(awaitable)
        raise UnsupportedWasmThreadingError(
            "Blocking WASM threading waits require a JSPI promising frame"
        )

    return run_sync(awaitable)


async def wait_for_future(
    future: Any,
    timeout: float | None,
) -> bool:
    if timeout is None:
        await future
        return True
    if timeout <= 0:
        return future.done()

    import asyncio

    wait_task = asyncio.ensure_future(asyncio.shield(future))
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
