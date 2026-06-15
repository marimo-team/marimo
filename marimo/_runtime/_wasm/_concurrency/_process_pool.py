# Copyright 2026 Marimo. All rights reserved.
"""Same-interpreter `ProcessPoolExecutor` adapter for Pyodide."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from marimo._runtime._wasm._concurrency._futures import (
    SerializedWasmExecutor,
)
from marimo._runtime._wasm._concurrency._mp_context import (
    validate_start_method,
)
from marimo._runtime._wasm._concurrency._wait import (
    UnsupportedWasmConcurrencyError,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator


class AsyncioProcessPoolExecutor(SerializedWasmExecutor):
    """Run `ProcessPoolExecutor` work in the current Pyodide interpreter."""

    _wasm_process_pool_executor = True

    def __init__(
        self,
        max_workers: int | None = None,
        mp_context: Any | None = None,
        initializer: Callable[..., Any] | None = None,
        initargs: tuple[Any, ...] = (),
        *,
        max_tasks_per_child: int | None = None,
    ) -> None:
        _validate_mp_context(mp_context)
        _validate_max_tasks_per_child(max_tasks_per_child)
        super().__init__(
            max_workers=max_workers,
            thread_name_prefix="WasmProcessPool",
            initializer=initializer,
            initargs=initargs,
            api_name="concurrent.futures.ProcessPoolExecutor",
        )

    def map(
        self,
        fn: Callable[..., Any],
        *iterables: Iterable[Any],
        timeout: float | None = None,
        chunksize: int = 1,
        buffersize: int | None = None,
    ) -> Iterator[Any]:
        _validate_chunksize(chunksize)
        return super().map(
            fn,
            *iterables,
            timeout=timeout,
            chunksize=chunksize,
            buffersize=buffersize,
        )


def _validate_mp_context(mp_context: Any | None) -> None:
    if mp_context is None:
        return
    get_start_method = getattr(mp_context, "get_start_method", None)
    if callable(get_start_method):
        validate_start_method(get_start_method())


def _validate_max_tasks_per_child(value: int | None) -> None:
    if value is None:
        return
    if not isinstance(value, int):
        raise TypeError("max_tasks_per_child must be an integer")
    if value <= 0:
        raise ValueError("max_tasks_per_child must be greater than 0")
    raise UnsupportedWasmConcurrencyError(
        "ProcessPoolExecutor.max_tasks_per_child is not supported in Pyodide"
    )


def _validate_chunksize(chunksize: int) -> None:
    if not isinstance(chunksize, int):
        raise TypeError("chunksize must be an integer")
    if chunksize < 1:
        raise ValueError("chunksize must be >= 1")
