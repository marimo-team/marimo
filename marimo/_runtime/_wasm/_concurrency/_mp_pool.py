# Copyright 2026 Marimo. All rights reserved.
"""Same-interpreter `multiprocessing.Pool` adapter for Pyodide."""

from __future__ import annotations

import multiprocessing as _multiprocessing
from collections import deque
from concurrent import futures as _futures
from typing import TYPE_CHECKING, Any

from marimo._runtime._wasm._concurrency._futures import (
    AsyncioFuture,
    SerializedWasmExecutor,
)
from marimo._runtime._wasm._concurrency._mp_context import (
    validate_start_method,
)
from marimo._runtime._wasm._concurrency._wait import (
    UnsupportedWasmConcurrencyError,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from typing_extensions import Self


class AsyncPoolResult:
    def __init__(
        self,
        future: AsyncioFuture,
        *,
        callback: Callable[[Any], Any] | None = None,
        error_callback: Callable[[BaseException], Any] | None = None,
    ) -> None:
        self._future = future
        if callback is not None or error_callback is not None:
            future.add_done_callback(
                lambda done: self._dispatch_callback(
                    done, callback, error_callback
                )
            )

    @staticmethod
    def _dispatch_callback(
        future: _futures.Future[Any],
        callback: Callable[[Any], Any] | None,
        error_callback: Callable[[BaseException], Any] | None,
    ) -> None:
        if future.cancelled():
            if error_callback is not None:
                error_callback(_futures.CancelledError())
            return
        exception = future.exception(timeout=0)
        if exception is not None:
            if error_callback is not None:
                error_callback(exception)
            return
        if callback is not None:
            callback(future.result(timeout=0))

    def get(self, timeout: float | None = None) -> Any:
        try:
            return self._future.result(timeout=timeout)
        except _futures.TimeoutError as exc:
            if self._future.done():
                return self._future.result(timeout=0)
            raise _multiprocessing.TimeoutError from exc

    def wait(self, timeout: float | None = None) -> None:
        try:
            self._future.result(timeout=timeout)
        except _futures.TimeoutError:
            return
        except UnsupportedWasmConcurrencyError:
            if self._future.done():
                return
            raise
        except BaseException:
            if not self._future.done():
                raise
            return

    def ready(self) -> bool:
        return self._future.done()

    def successful(self) -> bool:
        if not self.ready():
            raise ValueError("result is not ready")
        return (
            not self._future.cancelled()
            and self._future.exception(timeout=0) is None
        )


class AsyncPoolIterator:
    def __init__(
        self,
        pool: AsyncPool,
        func: Callable[[Any], Any],
        iterable: Iterable[Any],
    ) -> None:
        self._pool = pool
        self._func = func
        self._iterator = iter(iterable)
        self._submitted: deque[AsyncioFuture] = deque()
        self._drained = False
        pool._register_iterator(self)

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> Any:
        return self.next()

    def next(self, timeout: float | None = None) -> Any:
        self._pool._check_not_terminated()
        if not self._submitted and not self._submit_next():
            raise StopIteration
        future = self._submitted[0]
        try:
            return future.result(timeout=timeout)
        except _futures.TimeoutError as exc:
            if future.done():
                return future.result(timeout=0)
            raise _multiprocessing.TimeoutError from exc
        finally:
            if future.done():
                self._submitted.popleft()
                self._unregister_if_finished()

    def _submit_next(self) -> bool:
        if self._drained:
            return False
        try:
            item = next(self._iterator)
        except StopIteration:
            self._drained = True
            self._unregister_if_finished()
            return False
        except Exception as exc:
            self._drained = True
            future = AsyncioFuture()
            future.set_exception(exc)
            self._submitted.append(future)
            return True
        self._submitted.append(self._pool._executor.submit(self._func, item))
        return True

    def _drain_pending_submissions(self) -> None:
        while self._submit_next():
            pass

    def _cancel_submitted(self) -> None:
        self._drained = True
        for future in self._submitted:
            future.cancel()
        self._submitted.clear()
        self._pool._unregister_iterator(self)

    def _unregister_if_finished(self) -> None:
        if self._drained and not self._submitted:
            self._pool._unregister_iterator(self)


class AsyncPool:
    """Run `multiprocessing.Pool` work in the current Pyodide interpreter."""

    def __init__(
        self,
        processes: int | None = None,
        initializer: Callable[..., Any] | None = None,
        initargs: tuple[Any, ...] = (),
        maxtasksperchild: int | None = None,
        context: Any | None = None,
    ) -> None:
        if processes is not None and processes <= 0:
            raise ValueError("number of processes must be at least 1")
        if initializer is not None and not callable(initializer):
            raise TypeError("initializer must be a callable")
        if maxtasksperchild is not None and (
            not isinstance(maxtasksperchild, int) or maxtasksperchild <= 0
        ):
            raise ValueError("maxtasksperchild must be a positive int or None")
        if maxtasksperchild is not None:
            raise UnsupportedWasmConcurrencyError(
                "multiprocessing.Pool.maxtasksperchild is not supported in "
                "Pyodide"
            )
        _validate_context(context)
        self._closed = False
        self._terminated = False
        self._iterators: set[AsyncPoolIterator] = set()
        self._executor = PoolWasmExecutor(
            max_workers=processes,
            thread_name_prefix="WasmPool",
            initializer=initializer,
            initargs=initargs,
            api_name="multiprocessing.Pool",
        )

    def _check_running(self) -> None:
        if self._closed:
            raise ValueError("Pool not running")
        self._check_not_terminated()

    def _check_not_terminated(self) -> None:
        if self._terminated:
            raise ValueError("Pool has been terminated")

    def _register_iterator(self, iterator: AsyncPoolIterator) -> None:
        self._iterators.add(iterator)

    def _unregister_iterator(self, iterator: AsyncPoolIterator) -> None:
        self._iterators.discard(iterator)

    def _drain_iterators(self) -> None:
        for iterator in tuple(self._iterators):
            iterator._drain_pending_submissions()

    def _cancel_iterators(self) -> None:
        for iterator in tuple(self._iterators):
            iterator._cancel_submitted()

    def apply(
        self,
        func: Callable[..., Any],
        args: Iterable[Any] = (),
        kwds: dict[str, Any] | None = None,
    ) -> Any:
        self._check_running()
        return self._executor.submit(
            func, *tuple(args), **(kwds or {})
        ).result()

    def apply_async(
        self,
        func: Callable[..., Any],
        args: Iterable[Any] = (),
        kwds: dict[str, Any] | None = None,
        callback: Callable[[Any], Any] | None = None,
        error_callback: Callable[[BaseException], Any] | None = None,
    ) -> AsyncPoolResult:
        self._check_running()
        future = self._executor.submit(func, *tuple(args), **(kwds or {}))
        return AsyncPoolResult(
            future, callback=callback, error_callback=error_callback
        )

    def map(
        self,
        func: Callable[[Any], Any],
        iterable: Iterable[Any],
        chunksize: int | None = None,
    ) -> list[Any]:
        self._check_running()
        _validate_map_chunksize(chunksize)
        return list(self._executor.map(func, iterable))

    def map_async(
        self,
        func: Callable[[Any], Any],
        iterable: Iterable[Any],
        chunksize: int | None = None,
        callback: Callable[[Any], Any] | None = None,
        error_callback: Callable[[BaseException], Any] | None = None,
    ) -> AsyncPoolResult:
        self._check_running()
        _validate_map_chunksize(chunksize)
        future = self._executor.submit(
            lambda: [func(item) for item in iterable]
        )
        return AsyncPoolResult(
            future,
            callback=callback,
            error_callback=error_callback,
        )

    def starmap(
        self,
        func: Callable[..., Any],
        iterable: Iterable[Iterable[Any]],
        chunksize: int | None = None,
    ) -> list[Any]:
        self._check_running()
        _validate_map_chunksize(chunksize)
        return [
            self._executor.submit(func, *tuple(args)).result()
            for args in iterable
        ]

    def starmap_async(
        self,
        func: Callable[..., Any],
        iterable: Iterable[Iterable[Any]],
        chunksize: int | None = None,
        callback: Callable[[Any], Any] | None = None,
        error_callback: Callable[[BaseException], Any] | None = None,
    ) -> AsyncPoolResult:
        self._check_running()
        _validate_map_chunksize(chunksize)
        future = self._executor.submit(
            lambda: [func(*args) for args in iterable]
        )
        return AsyncPoolResult(
            future,
            callback=callback,
            error_callback=error_callback,
        )

    def imap(
        self,
        func: Callable[[Any], Any],
        iterable: Iterable[Any],
        chunksize: int = 1,
    ) -> AsyncPoolIterator:
        self._check_running()
        _validate_imap_chunksize(chunksize)
        return AsyncPoolIterator(self, func, iterable)

    def imap_unordered(
        self,
        func: Callable[[Any], Any],
        iterable: Iterable[Any],
        chunksize: int = 1,
    ) -> AsyncPoolIterator:
        self._check_running()
        _validate_imap_chunksize(chunksize)
        return AsyncPoolIterator(self, func, iterable)

    def close(self) -> None:
        self._closed = True

    def terminate(self) -> None:
        self._terminated = True
        self._cancel_iterators()
        self._executor.terminate_wasm_work()

    def join(self) -> None:
        if not self._closed and not self._terminated:
            raise ValueError("Pool is still running")
        try:
            if self._closed and not self._terminated:
                self._drain_iterators()
        finally:
            self._executor.shutdown(wait=True)

    def __enter__(self) -> Self:
        self._check_running()
        return self

    def __exit__(self, *exc: Any) -> None:
        del exc
        self.terminate()


class PoolWasmExecutor(SerializedWasmExecutor):
    _wasm_process_pool = True


def pool_factory(
    _ctx: Any | None = None,
    processes: int | None = None,
    initializer: Callable[..., Any] | None = None,
    initargs: tuple[Any, ...] = (),
    maxtasksperchild: int | None = None,
) -> AsyncPool:
    return AsyncPool(
        processes=processes,
        initializer=initializer,
        initargs=initargs,
        maxtasksperchild=maxtasksperchild,
        context=_ctx,
    )


def direct_pool_factory(
    processes: int | None = None,
    initializer: Callable[..., Any] | None = None,
    initargs: tuple[Any, ...] = (),
    maxtasksperchild: int | None = None,
    context: Any | None = None,
) -> AsyncPool:
    return AsyncPool(
        processes=processes,
        initializer=initializer,
        initargs=initargs,
        maxtasksperchild=maxtasksperchild,
        context=context,
    )


def _validate_imap_chunksize(chunksize: int) -> None:
    if not isinstance(chunksize, int):
        raise TypeError("Chunksize must be an integer")
    if chunksize < 1:
        raise ValueError(f"Chunksize must be 1+, not {chunksize}")


def _validate_map_chunksize(chunksize: int | None) -> None:
    if chunksize is None:
        return
    if not isinstance(chunksize, int):
        raise TypeError("Chunksize must be an integer")
    if chunksize < 1:
        raise ValueError(f"Chunksize must be 1+, not {chunksize}")


def _validate_context(context: Any | None) -> None:
    if context is None:
        return
    get_start_method = getattr(context, "get_start_method", None)
    if callable(get_start_method):
        validate_start_method(get_start_method())
