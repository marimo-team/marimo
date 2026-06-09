# Copyright 2026 Marimo. All rights reserved.
"""Run `ThreadPoolExecutor` work on one Pyodide event-loop lane.

Submitted callables are queued and drained one item at a time in the current
Pyodide interpreter. The adapter preserves future creation, result,
exception, callback, cancellation, and `map` behavior for the supported
contracts. Requested worker counts are accepted for API shape, but they do not
create parallel workers.
"""

from __future__ import annotations

import asyncio
import contextvars
import functools
import time
from collections import deque
from concurrent import futures as _futures
from dataclasses import dataclass
from itertools import islice
from typing import TYPE_CHECKING, Any

from marimo._runtime._wasm._concurrency import _state
from marimo._runtime._wasm._concurrency._state import (
    create_task_in_empty_wasm_context,
    current_thread_var,
    get_event_loop,
    live_threads,
    new_ident,
    run_until_complete_in_empty_wasm_context,
)
from marimo._runtime._wasm._concurrency._threading import (
    AsyncioThread,
    clear_thread_local_state,
)
from marimo._runtime._wasm._concurrency._wait import (
    UnsupportedWasmConcurrencyError,
    cooperative_wait,
    wait_with_timeout,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator


class AsyncioFuture(_futures.Future[Any]):
    def __init__(self) -> None:
        super().__init__()
        self._async_done: asyncio.Event | None = None

    def _done_event(self) -> asyncio.Event:
        if self._async_done is None:
            self._async_done = asyncio.Event()
        if self.done():
            self._async_done.set()
        return self._async_done

    def set_result(self, result: Any) -> None:
        super().set_result(result)
        if self._async_done is not None:
            self._async_done.set()

    def set_exception(self, exception: BaseException | None) -> None:
        if exception is None:
            raise TypeError("exception must be a BaseException")
        super().set_exception(exception)
        if self._async_done is not None:
            self._async_done.set()

    def cancel(self) -> bool:
        cancelled = super().cancel()
        if cancelled:
            if self._async_done is not None:
                self._async_done.set()
        return cancelled

    async def _wait_done(self, timeout: float | None) -> bool:
        if self.done():
            return True
        event = self._done_event()
        return await wait_with_timeout(event.wait(), timeout)

    def result(self, timeout: float | None = None) -> Any:
        if not self.done():
            if timeout is not None and timeout <= 0:
                return super().result(timeout=0)
            cooperative_wait(self._wait_done(timeout))
        return super().result(timeout=0)

    def exception(self, timeout: float | None = None) -> BaseException | None:
        if not self.done():
            if timeout is not None and timeout <= 0:
                return super().exception(timeout=0)
            cooperative_wait(self._wait_done(timeout))
        return super().exception(timeout=0)


class ExecutorThread(AsyncioThread):
    def __init__(self, name: str) -> None:
        super().__init__(target=None, name=name, daemon=True)
        self._ident = new_ident()
        self._native_id = self._ident
        self._started = True
        self._finished = False

    def is_alive(self) -> bool:
        return self._started and not self._finished


@dataclass
class WorkItem:
    future: AsyncioFuture
    fn: Callable[..., Any]
    args: tuple[Any, ...]
    kwargs: dict[str, Any]


class SerializedWasmExecutor(_futures.Executor):
    """Queue executor work onto one synthetic Pyodide worker lane.

    The lane gives callbacks and `current_thread()` a stable worker identity.
    It does not imply parallel execution.
    """

    def __init__(
        self,
        max_workers: int | None = None,
        thread_name_prefix: str = "",
        initializer: Callable[..., Any] | None = None,
        initargs: tuple[Any, ...] = (),
        *,
        api_name: str = "concurrent.futures.Executor",
    ) -> None:
        if max_workers is not None and max_workers <= 0:
            raise ValueError("max_workers must be greater than 0")
        if initializer is not None and not callable(initializer):
            raise TypeError("initializer must be a callable")
        self._max_workers = max_workers or 1
        self._api_name = api_name
        self._task_registry = _state.executor_task_registry()
        self._thread_name_prefix = thread_name_prefix or "WasmExecutor"
        self._initializer = initializer
        self._initargs = initargs
        self._shutdown = False
        self._initialized = False
        self._worker: ExecutorThread | None = None
        self._futures: set[AsyncioFuture] = set()
        self._queue: deque[WorkItem] = deque()
        self._runner_task: asyncio.Task[None] | None = None
        self._broken_initializer: BaseException | None = None
        _state.register_executor(self)

    def submit(
        self, fn: Callable[..., Any], /, *args: Any, **kwargs: Any
    ) -> AsyncioFuture:
        if self._shutdown:
            raise RuntimeError("cannot schedule new futures after shutdown")
        if self._broken_initializer is not None:
            raise RuntimeError(
                f"{self._api_name} initializer failed"
            ) from self._broken_initializer
        loop = get_event_loop()
        future = AsyncioFuture()
        self._futures.add(future)
        self._queue.append(
            WorkItem(
                future=future,
                fn=fn,
                args=args,
                kwargs=kwargs,
            )
        )
        self._start_runner(loop)
        if not loop.is_running() and not future.done():
            run_until_complete_in_empty_wasm_context(loop, self._drain_queue())
        return future

    def _start_runner(self, loop: asyncio.AbstractEventLoop) -> None:
        if self._runner_task is not None and not self._runner_task.done():
            return
        if loop.is_running():
            self._runner_task = create_task_in_empty_wasm_context(
                loop, self._drain_queue()
            )
            self._task_registry.add(self._runner_task)
            self._runner_task.add_done_callback(self._task_registry.discard)

    async def _drain_queue(self) -> None:
        while self._queue:
            item = self._queue.popleft()
            future = item.future
            if not future.set_running_or_notify_cancel():
                self._futures.discard(future)
                continue

            worker = self._worker_for_lane()
            token = current_thread_var.set(worker)
            try:
                if not self._initialized and self._initializer is not None:
                    try:
                        self._initializer(*self._initargs)
                    except BaseException as exc:
                        self._broken_initializer = exc
                        future.set_exception(exc)
                        self._fail_queued_work()
                        continue
                self._initialized = True
                fn, args, kwargs = _wrap_context_run_with_worker_identity(
                    item.fn,
                    item.args,
                    item.kwargs,
                    worker,
                )
                result = fn(*args, **kwargs)
                future.set_result(result)
            except BaseException as exc:
                future.set_exception(exc)
            finally:
                current_thread_var.reset(token)
                self._futures.discard(future)
        if self._shutdown:
            self._finish_worker_lane()
            if not self._queue and not self._futures:
                _state.unregister_executor(self)

    def _fail_queued_work(self) -> None:
        while self._queue:
            item = self._queue.popleft()
            if not item.future.cancelled():
                item.future.set_exception(
                    RuntimeError(f"{self._api_name} initializer failed")
                )
            self._futures.discard(item.future)

    def _worker_for_lane(self) -> ExecutorThread:
        if self._worker is None or not self._worker.is_alive():
            self._worker = ExecutorThread(
                f"{self._thread_name_prefix}_{new_ident()}"
            )
            live_threads.add(self._worker)
        return self._worker

    def _finish_worker_lane(self) -> None:
        if self._worker is None:
            return
        worker = self._worker
        worker._finished = True
        if worker.ident is not None:
            clear_thread_local_state(worker.ident)
        live_threads.discard(worker)
        self._worker = None

    def map(
        self,
        fn: Callable[..., Any],
        *iterables: Iterable[Any],
        timeout: float | None = None,
        chunksize: int = 1,
        buffersize: int | None = None,
    ) -> Iterator[Any]:
        _validate_map_buffersize(buffersize)
        del chunksize
        end_time = None if timeout is None else time.monotonic() + timeout

        def remaining_timeout() -> float | None:
            if end_time is None:
                return None
            return max(end_time - time.monotonic(), 0)

        args_iterator = zip(*iterables, strict=False)
        if buffersize is None:
            futures = [self.submit(fn, *args) for args in args_iterator]

            def eager_result_iterator() -> Iterator[Any]:
                try:
                    for future in futures:
                        yield future.result(timeout=remaining_timeout())
                finally:
                    for future in futures:
                        future.cancel()

            return eager_result_iterator()

        pending = deque(
            self.submit(fn, *args)
            for args in islice(args_iterator, buffersize)
        )

        def buffered_result_iterator() -> Iterator[Any]:
            try:
                while pending:
                    future = pending.popleft()
                    result = future.result(timeout=remaining_timeout())
                    try:
                        args = next(args_iterator)
                    except StopIteration:
                        pass
                    else:
                        pending.append(self.submit(fn, *args))
                    yield result
            finally:
                for future in pending:
                    future.cancel()

        return buffered_result_iterator()

    def shutdown(
        self, wait: bool = True, *, cancel_futures: bool = False
    ) -> None:
        self._shutdown = True
        self._discard_cancelled_queue_items()
        if cancel_futures:
            while self._queue:
                item = self._queue.pop()
                item.future.cancel()
                self._futures.discard(item.future)
        if wait:
            for future in list(self._futures):
                if not future.done():
                    try:
                        future.result()
                    except UnsupportedWasmConcurrencyError:
                        raise
                    except BaseException:
                        pass
        if wait or self._runner_task is None or self._runner_task.done():
            self._finish_worker_lane()
        if not self._queue and not self._futures:
            self._cancel_idle_runner_task()
        if self._worker is None and not self._queue and not self._futures:
            _state.unregister_executor(self)

    def shutdown_for_wasm_teardown(self) -> None:
        self.shutdown(wait=False, cancel_futures=True)

    def is_idle_for_wasm_teardown(self) -> bool:
        return (
            self._shutdown
            and self._worker is None
            and not self._queue
            and not self._futures
        )

    def _cancel_idle_runner_task(self) -> None:
        if self._runner_task is None or self._runner_task.done():
            return
        self._runner_task.cancel()
        self._task_registry.discard(self._runner_task)
        self._runner_task = None

    def _discard_cancelled_queue_items(self) -> None:
        if not self._queue:
            return
        pending: deque[WorkItem] = deque()
        while self._queue:
            item = self._queue.popleft()
            if item.future.cancelled():
                self._futures.discard(item.future)
            else:
                pending.append(item)
        self._queue = pending


class AsyncioThreadPoolExecutor(SerializedWasmExecutor):
    """`ThreadPoolExecutor` adapter with serialized Pyodide execution."""

    def __init__(
        self,
        max_workers: int | None = None,
        thread_name_prefix: str = "",
        initializer: Callable[..., Any] | None = None,
        initargs: tuple[Any, ...] = (),
    ) -> None:
        if max_workers is not None and max_workers <= 0:
            raise ValueError("max_workers must be greater than 0")
        super().__init__(
            max_workers=max_workers,
            thread_name_prefix=thread_name_prefix or "WasmThreadPool",
            initializer=initializer,
            initargs=initargs,
            api_name="concurrent.futures.ThreadPoolExecutor",
        )


def _wrap_context_run_with_worker_identity(
    fn: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    worker: ExecutorThread,
) -> tuple[Callable[..., Any], tuple[Any, ...], dict[str, Any]]:
    context_run = fn.func if isinstance(fn, functools.partial) else fn
    context = getattr(context_run, "__self__", None)
    if not (
        isinstance(context, contextvars.Context)
        and getattr(context_run, "__name__", None) == "run"
    ):
        return fn, args, kwargs

    partial_args = fn.args if isinstance(fn, functools.partial) else ()
    partial_kwargs = fn.keywords if isinstance(fn, functools.partial) else None
    run_args = (*partial_args, *args)
    if not run_args:
        return fn, args, kwargs

    target = run_args[0]
    target_args = run_args[1:]
    target_kwargs = {**(partial_kwargs or {}), **kwargs}
    return (
        _run_context_target_with_worker_identity,
        (context, target, target_args, target_kwargs, worker),
        {},
    )


def _run_context_target_with_worker_identity(
    context: contextvars.Context,
    target: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    worker: ExecutorThread,
) -> Any:
    def call_target() -> Any:
        token = current_thread_var.set(worker)
        try:
            return target(*args, **kwargs)
        finally:
            current_thread_var.reset(token)

    return context.run(call_target)


def _validate_map_buffersize(buffersize: int | None) -> None:
    if buffersize is None:
        return
    if not isinstance(buffersize, int):
        raise TypeError("buffersize must be an integer or None")
    if buffersize < 1:
        raise ValueError("buffersize must be None or > 0")
