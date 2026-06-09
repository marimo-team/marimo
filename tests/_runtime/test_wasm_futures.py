# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import concurrent.futures
import contextvars
import functools
import threading

import pytest

from marimo._runtime._wasm._concurrency._install import (
    install_wasm_concurrency_shims,
)
from tests._runtime._helpers.wasm import wait_until
from tests.conftest import mock_pyodide


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
