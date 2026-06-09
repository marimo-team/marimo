# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import concurrent.futures
import contextvars
import functools
import threading
import time
from typing import Any, cast

import pytest

from marimo._runtime._wasm._concurrency._futures import AsyncioFuture
from marimo._runtime._wasm._concurrency._install import (
    install_wasm_concurrency_shims,
)
from marimo._runtime._wasm._concurrency._wait import (
    UnsupportedWasmConcurrencyError,
)
from tests._runtime._helpers.wasm import install_run_sync, wait_until
from tests.conftest import mock_pyodide


def _identity(value: int) -> int:
    return value


class _OrderedAsyncioFuture(AsyncioFuture):
    def __init__(self, order: int) -> None:
        super().__init__()
        self._order = order

    def __hash__(self) -> int:
        return self._order


class _OrderedFuture(concurrent.futures.Future[str]):
    def __init__(self, order: int) -> None:
        super().__init__()
        self._order = order

    def __hash__(self) -> int:
        return self._order


def _mixed_futures_with_done_shim_before_foreign() -> tuple[
    _OrderedAsyncioFuture, _OrderedFuture, _OrderedAsyncioFuture
]:
    for done_order in range(20):
        for foreign_order in range(20):
            for late_order in range(20):
                if len({done_order, foreign_order, late_order}) < 3:
                    continue
                shim_done = _OrderedAsyncioFuture(done_order)
                foreign = _OrderedFuture(foreign_order)
                shim_late = _OrderedAsyncioFuture(late_order)
                ordered = list({shim_done, foreign, shim_late})
                if ordered.index(shim_done) < ordered.index(foreign):
                    return shim_done, foreign, shim_late
    raise AssertionError("could not build ordered futures")


def _mixed_futures_with_late_shim_before_done_shim() -> tuple[
    _OrderedAsyncioFuture, _OrderedFuture, _OrderedAsyncioFuture
]:
    # Control set iteration so the generator has already skipped the late
    # shim before the caller completes it.
    for done_order in range(20):
        for foreign_order in range(20):
            for late_order in range(20):
                if len({done_order, foreign_order, late_order}) < 3:
                    continue
                shim_done = _OrderedAsyncioFuture(done_order)
                foreign = _OrderedFuture(foreign_order)
                shim_late = _OrderedAsyncioFuture(late_order)
                ordered = list({shim_done, foreign, shim_late})
                if ordered.index(shim_late) < ordered.index(shim_done):
                    return shim_done, foreign, shim_late
    raise AssertionError("could not build ordered futures")


def _wasm_futures_with_reversed_hash_order() -> tuple[
    _OrderedAsyncioFuture, _OrderedAsyncioFuture
]:
    for first_order in range(20):
        for second_order in range(20):
            if first_order == second_order:
                continue
            first = _OrderedAsyncioFuture(first_order)
            second = _OrderedAsyncioFuture(second_order)
            if list({first, second}) == [second, first]:
                return first, second
    raise AssertionError("could not build ordered futures")


def test_wasm_thread_pool_map_returns_ordered_results() -> None:
    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        try:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=2
            ) as executor:
                assert list(
                    executor.map(lambda value: value + 1, [1, 2, 3])
                ) == [2, 3, 4]
                assert list(
                    executor.map(
                        lambda value: value + 1,
                        [1, 2, 3],
                        chunksize=0,
                    )
                ) == [2, 3, 4]

                consumed: list[int] = []

                def values() -> object:
                    consumed.append(1)
                    yield 1
                    consumed.append(2)
                    yield 2

                iterator = executor.map(
                    lambda value: value,
                    values(),
                    buffersize=1,
                )
                assert consumed == [1]
                assert next(iterator) == 1
                assert consumed == [1, 2]
                assert list(iterator) == [2]
        finally:
            unpatch()


def test_wasm_thread_pool_initializer_state_persists_across_tasks() -> None:
    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        try:
            local = threading.local()

            def initialize() -> None:
                local.ready = True
                local.count = 0

            def work() -> tuple[str, bool, int]:
                local.count += 1
                return (
                    threading.current_thread().name,
                    local.ready,
                    local.count,
                )

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=2,
                thread_name_prefix="lane",
                initializer=initialize,
            ) as executor:
                first = executor.submit(work).result()
                second = executor.submit(work).result()

            assert first[0] == second[0]
            assert first[1:] == (True, 1)
            assert second[1:] == (True, 2)
        finally:
            unpatch()


def test_wasm_thread_pool_initializer_failure_breaks_executor() -> None:
    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        try:

            def initialize() -> None:
                raise RuntimeError("initializer failed")

            with concurrent.futures.ThreadPoolExecutor(
                initializer=initialize,
            ) as executor:
                future = executor.submit(lambda: "unreachable")
                with pytest.raises(RuntimeError, match="initializer failed"):
                    future.result()
                with pytest.raises(RuntimeError, match="initializer failed"):
                    executor.submit(lambda: "later")
        finally:
            unpatch()


def test_wasm_thread_pool_rejects_noncallable_initializer() -> None:
    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        try:
            with pytest.raises(TypeError, match="initializer"):
                concurrent.futures.ThreadPoolExecutor(initializer=object())
        finally:
            unpatch()


def test_wasm_thread_pool_map_validates_buffersize() -> None:
    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                for buffersize in (0, -1):
                    with pytest.raises(ValueError, match="buffersize"):
                        executor.map(
                            lambda value: value,
                            [1],
                            buffersize=buffersize,
                        )
                with pytest.raises(TypeError, match="buffersize"):
                    executor.map(
                        lambda value: value,
                        [1],
                        buffersize=object(),  # type: ignore[arg-type]
                    )
        finally:
            unpatch()


def test_wasm_thread_pool_preserves_awaitable_return_values() -> None:
    async def returned() -> str:
        return "awaited elsewhere"

    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                result = executor.submit(lambda: returned()).result()

            assert asyncio.iscoroutine(result)
            result.close()
        finally:
            unpatch()


def test_wasm_executor_current_thread_has_thread_surface() -> None:
    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        try:

            def worker() -> tuple[bool, bool, bool]:
                current = threading.current_thread()
                return (
                    isinstance(current, threading.Thread),
                    current.ident is not None,
                    current.is_alive(),
                )

            with concurrent.futures.ThreadPoolExecutor() as executor:
                assert executor.submit(worker).result() == (
                    True,
                    True,
                    True,
                )
        finally:
            unpatch()


def test_wasm_thread_pool_result_exception_and_callbacks() -> None:
    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        try:
            callback_results: list[tuple[str, int | str]] = []
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=2
            ) as executor:
                success = executor.submit(lambda: 7)
                success.add_done_callback(
                    lambda future: callback_results.append(
                        ("success", future.result())
                    )
                )
                assert success.result() == 7

                failure = executor.submit(
                    lambda: (_ for _ in ()).throw(ValueError("boom"))
                )
                failure.add_done_callback(
                    lambda future: callback_results.append(
                        ("error", type(future.exception()).__name__)
                    )
                )
                with pytest.raises(ValueError, match="boom"):
                    failure.result()

            assert callback_results == [
                ("success", 7),
                ("error", "ValueError"),
            ]
        finally:
            unpatch()


def test_wasm_thread_pool_wait_returns_done_futures() -> None:
    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        try:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=2
            ) as executor:
                futures = [
                    executor.submit(_identity, value) for value in range(3)
                ]
                done, not_done = concurrent.futures.wait(futures)

            assert done == set(futures)
            assert not not_done
        finally:
            unpatch()


def test_wasm_wait_accepts_stdlib_fs_keyword() -> None:
    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        future: concurrent.futures.Future[str] = AsyncioFuture()
        try:
            future.set_result("done")

            done, not_done = concurrent.futures.wait(fs=[future])

            assert done == {future}
            assert not not_done
        finally:
            unpatch()


def test_wasm_wait_first_exception_returns_all_done_without_exception() -> (
    None
):
    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [
                    executor.submit(_identity, value) for value in range(3)
                ]
                done, not_done = concurrent.futures.wait(
                    futures,
                    return_when=concurrent.futures.FIRST_EXCEPTION,
                )

            assert done == set(futures)
            assert not not_done
        finally:
            unpatch()


def test_wasm_wait_rejects_invalid_return_when() -> None:
    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(lambda: "done")

                with pytest.raises(
                    ValueError, match="Invalid return condition"
                ):
                    concurrent.futures.wait(
                        [future],
                        return_when="not-a-return-condition",
                    )
        finally:
            unpatch()


def test_wasm_future_timed_waits_honor_short_timeouts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        install_run_sync(monkeypatch)
        future: concurrent.futures.Future[str] = AsyncioFuture()
        try:
            with pytest.raises(concurrent.futures.TimeoutError):
                future.result(timeout=0.001)

            done, not_done = concurrent.futures.wait([future], timeout=0.001)

            assert done == set()
            assert not_done == {future}
        finally:
            future.cancel()
            unpatch()


def test_wasm_future_timed_waits_can_reuse_pending_future(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        install_run_sync(monkeypatch)
        future: concurrent.futures.Future[str] = AsyncioFuture()
        try:
            done, not_done = concurrent.futures.wait([future], timeout=0.001)
            assert done == set()
            assert not_done == {future}

            with pytest.raises(concurrent.futures.TimeoutError):
                future.result(timeout=0.001)
        finally:
            future.cancel()
            unpatch()


def test_wasm_thread_pool_as_completed_yields_finished_futures() -> None:
    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        try:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=2
            ) as executor:
                futures = [
                    executor.submit(_identity, value) for value in range(3)
                ]
                assert sorted(
                    future.result()
                    for future in concurrent.futures.as_completed(futures)
                ) == [0, 1, 2]
        finally:
            unpatch()


def test_wasm_as_completed_accepts_stdlib_fs_keyword() -> None:
    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        future: concurrent.futures.Future[str] = AsyncioFuture()
        try:
            future.set_result("done")

            assert list(concurrent.futures.as_completed(fs=[future])) == [
                future
            ]
        finally:
            unpatch()


def test_wasm_as_completed_preserves_completion_order_after_waiter_starts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        install_run_sync(monkeypatch)
        from pyodide import ffi

        first, second = _wasm_futures_with_reversed_hash_order()

        def run_sync(awaitable: object) -> object:
            async def run() -> object:
                loop = asyncio.get_running_loop()
                loop.call_soon(first.set_result, "first")
                loop.call_soon(second.set_result, "second")
                return await cast(Any, awaitable)

            return asyncio.run(run())

        monkeypatch.setattr(ffi, "run_sync", run_sync)
        try:
            iterator = concurrent.futures.as_completed(
                [first, second], timeout=1
            )

            assert next(iterator) is first
            assert next(iterator) is second
        finally:
            unpatch()


def test_wasm_as_completed_orders_callback_completion_after_trigger() -> None:
    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        first: concurrent.futures.Future[str] = AsyncioFuture()
        second: concurrent.futures.Future[str] = AsyncioFuture()
        try:
            first.add_done_callback(
                lambda _future: second.set_result("second")
            )

            first.set_result("first")

            assert list(concurrent.futures.as_completed([first, second])) == [
                first,
                second,
            ]
        finally:
            unpatch()


def test_wasm_as_completed_deduplicates_input_futures() -> None:
    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(lambda: "done")

                assert list(
                    concurrent.futures.as_completed(
                        [future, future], timeout=1
                    )
                ) == [future]
        finally:
            unpatch()


def test_wasm_as_completed_timeout_zero_yields_done_futures() -> None:
    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        done_future: concurrent.futures.Future[str] = AsyncioFuture()
        pending_future: concurrent.futures.Future[str] = AsyncioFuture()
        try:
            done_future.set_result("done")
            iterator = concurrent.futures.as_completed(
                [done_future, pending_future], timeout=0
            )

            assert next(iterator) is done_future
            with pytest.raises(concurrent.futures.TimeoutError):
                next(iterator)
        finally:
            pending_future.cancel()
            unpatch()


def test_wasm_as_completed_deadline_excludes_late_completions() -> None:
    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        first: concurrent.futures.Future[str] = AsyncioFuture()
        second: concurrent.futures.Future[str] = AsyncioFuture()
        try:
            first.set_result("first")
            iterator = concurrent.futures.as_completed(
                [first, second], timeout=0.001
            )

            assert next(iterator) is first
            time.sleep(0.01)
            second.set_result("late")

            with pytest.raises(concurrent.futures.TimeoutError):
                next(iterator)
        finally:
            second.cancel()
            unpatch()


def test_wasm_mixed_pending_wait_raises_clear_error() -> None:
    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        shim_future: concurrent.futures.Future[str] = AsyncioFuture()
        foreign_future: concurrent.futures.Future[str] = (
            concurrent.futures.Future()
        )
        try:
            with pytest.raises(
                UnsupportedWasmConcurrencyError, match="mixed pending"
            ):
                concurrent.futures.wait([shim_future, foreign_future])
        finally:
            shim_future.cancel()
            foreign_future.cancel()
            unpatch()


def test_wasm_mixed_as_completed_yields_done_before_clear_error() -> None:
    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        shim_done: concurrent.futures.Future[str] = AsyncioFuture()
        foreign_pending: concurrent.futures.Future[str] = (
            concurrent.futures.Future()
        )
        try:
            shim_done.set_result("shim")
            iterator = concurrent.futures.as_completed(
                [shim_done, foreign_pending]
            )

            assert next(iterator) is shim_done
            with pytest.raises(
                UnsupportedWasmConcurrencyError, match="mixed pending"
            ):
                next(iterator)
        finally:
            foreign_pending.cancel()
            unpatch()


def test_wasm_mixed_as_completed_accepts_foreign_completion_between_yields() -> (
    None
):
    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        shim_done: concurrent.futures.Future[str] = AsyncioFuture()
        foreign_future: concurrent.futures.Future[str] = (
            concurrent.futures.Future()
        )
        try:
            shim_done.set_result("shim")
            iterator = concurrent.futures.as_completed(
                [shim_done, foreign_future]
            )

            assert next(iterator) is shim_done
            foreign_future.set_result("foreign")
            assert next(iterator) is foreign_future
            with pytest.raises(StopIteration):
                next(iterator)
        finally:
            unpatch()


def test_wasm_mixed_as_completed_does_not_repeat_foreign_future() -> None:
    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        shim_done, foreign_future, shim_late = (
            _mixed_futures_with_done_shim_before_foreign()
        )
        try:
            shim_done.set_result("shim")
            iterator = concurrent.futures.as_completed(
                [shim_done, foreign_future, shim_late]
            )

            assert next(iterator) is shim_done
            foreign_future.set_result("foreign")
            assert next(iterator) is foreign_future
            shim_late.set_result("late")
            assert next(iterator) is shim_late
            with pytest.raises(StopIteration):
                next(iterator)
        finally:
            unpatch()


def test_wasm_mixed_as_completed_yields_late_wasm_before_foreign_error() -> (
    None
):
    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        shim_done, foreign_pending, shim_late = (
            _mixed_futures_with_late_shim_before_done_shim()
        )
        try:
            shim_done.set_result("shim")
            iterator = concurrent.futures.as_completed(
                [shim_done, foreign_pending, shim_late]
            )

            assert next(iterator) is shim_done
            shim_late.set_result("late")
            assert next(iterator) is shim_late
            with pytest.raises(
                UnsupportedWasmConcurrencyError, match="mixed pending"
            ):
                next(iterator)
        finally:
            foreign_pending.cancel()
            unpatch()


@pytest.mark.asyncio
async def test_wasm_thread_pool_cancelled_queue_allows_immediate_unpatch() -> (
    None
):
    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        executor = concurrent.futures.ThreadPoolExecutor()
        try:
            future = executor.submit(lambda: "unreachable")

            executor.shutdown(wait=True, cancel_futures=True)

            assert future.cancelled()
            unpatch()
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
            unpatch()
            await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_wasm_thread_pool_cancelled_future_allows_immediate_unpatch() -> (
    None
):
    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        executor = concurrent.futures.ThreadPoolExecutor()
        try:
            future = executor.submit(lambda: "unreachable")

            assert future.cancel()
            executor.shutdown(wait=True)

            unpatch()
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
            unpatch()
            await asyncio.sleep(0)


def test_wasm_thread_pool_reuses_worker_local_state_until_shutdown() -> None:
    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        try:
            local = threading.local()

            def write_value() -> str:
                local.value = "worker"
                return local.value

            def read_value() -> bool:
                return hasattr(local, "value")

            with concurrent.futures.ThreadPoolExecutor() as executor:
                assert executor.submit(write_value).result() == "worker"
                assert executor.submit(read_value).result() is True
            assert not hasattr(local, "value")
        finally:
            unpatch()


@pytest.mark.asyncio
async def test_wasm_thread_pool_does_not_inherit_ambient_contextvars() -> None:
    ambient = contextvars.ContextVar("ambient", default="unset")
    ambient.set("parent")

    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(lambda: ambient.get())
                await wait_until(future.done)

                assert future.result(timeout=0) == "unset"
                assert ambient.get() == "parent"
        finally:
            unpatch()


@pytest.mark.asyncio
async def test_asyncio_to_thread_keeps_its_contextvars_contract() -> None:
    ambient = contextvars.ContextVar("ambient", default="unset")
    ambient.set("parent")

    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        try:
            assert await asyncio.to_thread(lambda: ambient.get()) == "parent"
            assert ambient.get() == "parent"
        finally:
            await asyncio.get_running_loop().shutdown_default_executor()
            unpatch()


@pytest.mark.asyncio
async def test_asyncio_to_thread_uses_worker_thread_local_identity() -> None:
    ambient = contextvars.ContextVar("ambient", default="unset")
    ambient.set("parent")

    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        try:
            local = threading.local()
            local.value = "parent"

            def worker() -> tuple[str, bool, str]:
                return (
                    ambient.get(),
                    hasattr(local, "value"),
                    threading.current_thread().name,
                )

            (
                ambient_value,
                saw_parent_local,
                thread_name,
            ) = await asyncio.to_thread(worker)

            assert ambient_value == "parent"
            assert saw_parent_local is False
            assert thread_name != "MainThread"
            assert local.value == "parent"
        finally:
            await asyncio.get_running_loop().shutdown_default_executor()
            unpatch()


def test_context_run_executor_keeps_worker_identity_temporary() -> None:
    ambient = contextvars.ContextVar("ambient", default="unset")
    ambient.set("parent")
    context = contextvars.copy_context()

    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        try:
            local = threading.local()
            local.value = "parent"

            def worker() -> tuple[str, bool, str]:
                return (
                    ambient.get(),
                    hasattr(local, "value"),
                    threading.current_thread().name,
                )

            with concurrent.futures.ThreadPoolExecutor() as executor:
                ambient_value, saw_parent_local, thread_name = executor.submit(
                    context.run, worker
                ).result()

            assert ambient_value == "parent"
            assert saw_parent_local is False
            assert thread_name != "MainThread"
            assert context.run(lambda: threading.current_thread().name) == (
                "MainThread"
            )
            assert local.value == "parent"
        finally:
            unpatch()


def test_partial_context_run_executor_keeps_worker_identity_temporary() -> (
    None
):
    ambient = contextvars.ContextVar("ambient", default="unset")
    ambient.set("parent")
    context = contextvars.copy_context()

    with mock_pyodide():
        unpatch = install_wasm_concurrency_shims()
        try:
            local = threading.local()
            local.value = "parent"

            def worker() -> tuple[str, bool, str]:
                return (
                    ambient.get(),
                    hasattr(local, "value"),
                    threading.current_thread().name,
                )

            with concurrent.futures.ThreadPoolExecutor() as executor:
                ambient_value, saw_parent_local, thread_name = executor.submit(
                    functools.partial(context.run, worker)
                ).result()

            assert ambient_value == "parent"
            assert saw_parent_local is False
            assert thread_name != "MainThread"
            assert context.run(lambda: threading.current_thread().name) == (
                "MainThread"
            )
            assert local.value == "parent"
        finally:
            unpatch()
