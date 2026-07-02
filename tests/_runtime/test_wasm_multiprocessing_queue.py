# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import multiprocessing
import multiprocessing.queues
import queue
from typing import Any, cast

import pytest

from marimo._runtime._wasm._concurrency._wait import (
    UnsupportedWasmConcurrencyError,
)
from tests._runtime._helpers.wasm import install_wasm_process_test_shims
from tests.conftest import mock_pyodide


def test_wasm_queue_process_handoff_and_bounds() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        try:
            values: Any = multiprocessing.Queue()

            def worker(output: Any) -> None:
                output.put("ok")

            process = multiprocessing.Process(target=worker, args=(values,))
            process.start()
            process.join(timeout=1)

            assert process.exitcode == 0
            assert values.get(block=False) == "ok"
            assert values.empty()

            bounded: Any = multiprocessing.Queue(maxsize=1)
            bounded.put_nowait("first")
            assert bounded.full()
            with pytest.raises(queue.Full):
                bounded.put_nowait("second")
            with pytest.raises(queue.Full):
                bounded.put("second", timeout=0)
            with pytest.raises(queue.Full):
                bounded.put("negative", timeout=-1)
            assert bounded.get_nowait() == "first"
            bounded.put("second")
            assert bounded.get(timeout=-1) == "second"

            empty_values: Any = multiprocessing.Queue()
            with pytest.raises(queue.Empty):
                empty_values.get(timeout=0)
            with pytest.raises(queue.Empty):
                empty_values.get(timeout=-1)

            reference: list[str] = []
            values.put(reference)
            assert values.get() is reference

            bounded.put("closed")
            bounded.close()
            with pytest.raises(ValueError, match="closed"):
                bounded.put("after-close")
            with pytest.raises(ValueError, match="closed"):
                bounded.get()
            with pytest.raises(ValueError, match="closed"):
                bounded.empty()
        finally:
            unpatch()


def test_wasm_simple_queue_shape_and_close() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        try:
            with pytest.raises(TypeError):
                cast(Any, multiprocessing.SimpleQueue)(1)

            values: Any = multiprocessing.SimpleQueue()
            values.put("simple")
            assert values.get() == "simple"
            assert values.empty()
            for unsupported_attr in (
                "qsize",
                "full",
                "put_nowait",
                "get_nowait",
            ):
                assert not hasattr(values, unsupported_attr)
            with pytest.raises(TypeError):
                cast(Any, values).put("blocked", block=False)
            with pytest.raises(TypeError):
                cast(Any, values).get(block=False)

            values.put("closed")
            values.close()
            with pytest.raises(ValueError, match="closed"):
                values.put("after-close")
            with pytest.raises(ValueError, match="closed"):
                values.get()
            with pytest.raises(ValueError, match="closed"):
                values.empty()
        finally:
            unpatch()


def test_wasm_queue_child_close_preserves_parent_messages() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        try:
            values: Any = multiprocessing.Queue()
            simple_values: Any = multiprocessing.SimpleQueue()

            def worker(output: Any, simple_output: Any) -> None:
                output.put("queue")
                output.close()
                output.join_thread()
                simple_output.put("simple")
                simple_output.close()

                with pytest.raises(ValueError, match="closed"):
                    output.put("after-close")
                with pytest.raises(ValueError, match="closed"):
                    simple_output.put("after-close")

            process = multiprocessing.Process(
                target=worker, args=(values, simple_values)
            )
            process.start()
            process.join(timeout=1)

            assert process.exitcode == 0
            assert values.get(timeout=1) == "queue"
            assert simple_values.get() == "simple"
        finally:
            unpatch()


def test_wasm_queue_parent_close_preserves_child_messages() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        try:
            values: Any = multiprocessing.Queue()
            simple_values: Any = multiprocessing.SimpleQueue()
            observed: list[str] = []

            values.put("queue")
            simple_values.put("simple")

            def worker(input_queue: Any, simple_input: Any) -> None:
                observed.append(input_queue.get(timeout=1))
                observed.append(simple_input.get())

            async def close_parent_before_child_runs() -> None:
                process = multiprocessing.Process(
                    target=worker,
                    args=(values, simple_values),
                )
                process.start()
                values.close()
                values.join_thread()
                simple_values.close()
                await asyncio.sleep(0)
                await asyncio.sleep(0)
                assert process.exitcode == 0

            asyncio.run(close_parent_before_child_runs())

            assert observed == ["queue", "simple"]
            with pytest.raises(ValueError, match="closed"):
                values.get(block=False)
            with pytest.raises(ValueError, match="closed"):
                simple_values.get()
        finally:
            unpatch()


def test_wasm_queue_child_close_does_not_wake_parent_get_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        try:
            values: Any = multiprocessing.Queue()

            def close_child(handle: Any) -> None:
                handle.close()

            def wait_through_child_close(awaitable: object) -> bool:
                async def wait_and_put() -> bool:
                    task = asyncio.create_task(cast(Any, awaitable))
                    await asyncio.sleep(0)
                    process = multiprocessing.Process(
                        target=close_child,
                        args=(values,),
                    )
                    process.start()
                    await asyncio.sleep(0)
                    assert not task.done()
                    values.put("after-close")
                    return await asyncio.wait_for(task, timeout=1)

                return asyncio.run(wait_and_put())

            monkeypatch.setattr(
                "marimo._runtime._wasm._concurrency._mp_queue."
                "cooperative_wait",
                wait_through_child_close,
            )

            assert values.get(timeout=1) == "after-close"
        finally:
            unpatch()


def test_wasm_queue_child_close_does_not_wake_parent_put_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        try:
            values: Any = multiprocessing.Queue(maxsize=1)
            values.put("first")

            def close_child(handle: Any) -> None:
                handle.close()

            def wait_through_child_close(awaitable: object) -> bool:
                async def wait_and_drain() -> bool:
                    task = asyncio.create_task(cast(Any, awaitable))
                    await asyncio.sleep(0)
                    process = multiprocessing.Process(
                        target=close_child,
                        args=(values,),
                    )
                    process.start()
                    await asyncio.sleep(0)
                    assert not task.done()
                    assert values.get(block=False) == "first"
                    return await asyncio.wait_for(task, timeout=1)

                return asyncio.run(wait_and_drain())

            monkeypatch.setattr(
                "marimo._runtime._wasm._concurrency._mp_queue."
                "cooperative_wait",
                wait_through_child_close,
            )

            values.put("after-close", timeout=1)
            assert values.get(block=False) == "after-close"
        finally:
            unpatch()


def test_wasm_simple_queue_child_close_does_not_wake_parent_get_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        try:
            values: Any = multiprocessing.SimpleQueue()

            def close_child(handle: Any) -> None:
                handle.close()

            def wait_through_child_close(awaitable: object) -> bool:
                async def wait_and_put() -> bool:
                    task = asyncio.create_task(cast(Any, awaitable))
                    await asyncio.sleep(0)
                    process = multiprocessing.Process(
                        target=close_child,
                        args=(values,),
                    )
                    process.start()
                    await asyncio.sleep(0)
                    assert not task.done()
                    values.put("after-close")
                    return await asyncio.wait_for(task, timeout=1)

                return asyncio.run(wait_and_put())

            monkeypatch.setattr(
                "marimo._runtime._wasm._concurrency._mp_queue."
                "cooperative_wait",
                wait_through_child_close,
            )

            assert values.get() == "after-close"
        finally:
            unpatch()


def test_wasm_queue_context_and_submodule_factories() -> None:
    original_queue = multiprocessing.Queue
    original_submodule_queue = multiprocessing.queues.Queue

    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        try:
            assert multiprocessing.Queue is not original_queue
            assert multiprocessing.queues.Queue is not original_submodule_queue
            assert multiprocessing.queues.Empty is queue.Empty
            assert multiprocessing.queues.Full is queue.Full

            ctx = multiprocessing.get_context("spawn")
            values: Any = ctx.Queue()
            values.put("context")
            assert values.get(block=False) == "context"

            simple_values: Any = ctx.SimpleQueue()
            simple_values.put("context-simple")
            assert simple_values.get() == "context-simple"

            submodule_values: Any = multiprocessing.queues.Queue(1, ctx=ctx)
            assert isinstance(submodule_values, multiprocessing.queues.Queue)
            submodule_values.put("submodule")
            assert submodule_values.get(block=False) == "submodule"

            submodule_simple: Any = multiprocessing.queues.SimpleQueue(ctx=ctx)
            assert isinstance(
                submodule_simple, multiprocessing.queues.SimpleQueue
            )
            submodule_simple.put("submodule-simple")
            assert submodule_simple.get() == "submodule-simple"

            for call in (
                lambda: multiprocessing.JoinableQueue(),
                lambda: ctx.JoinableQueue(),
                lambda: multiprocessing.queues.JoinableQueue(),
            ):
                with pytest.raises(
                    UnsupportedWasmConcurrencyError,
                    match="JoinableQueue",
                ):
                    call()
        finally:
            unpatch()

    assert multiprocessing.Queue is original_queue
    assert multiprocessing.queues.Queue is original_submodule_queue


def test_wasm_queue_close_rejects_blocked_put_after_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        try:
            values: Any = multiprocessing.Queue(maxsize=1)
            values.put("first")

            def close_during_wait(awaitable: object) -> bool:
                async def wait_and_close() -> bool:
                    task = asyncio.create_task(cast(Any, awaitable))
                    await asyncio.sleep(0)
                    values.close()
                    return await asyncio.wait_for(task, timeout=1)

                return asyncio.run(wait_and_close())

            monkeypatch.setattr(
                "marimo._runtime._wasm._concurrency._mp_queue."
                "cooperative_wait",
                close_during_wait,
            )

            with pytest.raises(ValueError, match="closed"):
                values.put("after-close", timeout=1)
            with pytest.raises(ValueError, match="closed"):
                values.empty()
        finally:
            unpatch()


def test_wasm_queue_close_rejects_blocked_get_after_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        try:
            values: Any = multiprocessing.Queue()

            def close_during_wait(awaitable: object) -> bool:
                async def wait_and_close() -> bool:
                    task = asyncio.create_task(cast(Any, awaitable))
                    await asyncio.sleep(0)
                    values.close()
                    return await asyncio.wait_for(task, timeout=1)

                return asyncio.run(wait_and_close())

            monkeypatch.setattr(
                "marimo._runtime._wasm._concurrency._mp_queue."
                "cooperative_wait",
                close_during_wait,
            )

            with pytest.raises(ValueError, match="closed"):
                values.get()
            with pytest.raises(ValueError, match="closed"):
                values.empty()
        finally:
            unpatch()


def test_wasm_queue_closed_waiter_does_not_consume_later_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        try:
            values: Any = multiprocessing.Queue()
            observed: list[str] = []

            def put_child(handle: Any) -> None:
                handle.put("child")

            def read_child(handle: Any) -> None:
                observed.append(handle.get(timeout=1))

            def close_and_put_during_wait(awaitable: object) -> bool:
                async def wait_and_put() -> bool:
                    task = asyncio.create_task(cast(Any, awaitable))
                    await asyncio.sleep(0)
                    values.close()
                    process = multiprocessing.Process(
                        target=put_child,
                        args=(values,),
                    )
                    process.start()
                    await asyncio.sleep(0)
                    await asyncio.sleep(0)
                    assert process.exitcode == 0
                    return await asyncio.wait_for(task, timeout=1)

                return asyncio.run(wait_and_put())

            monkeypatch.setattr(
                "marimo._runtime._wasm._concurrency._mp_queue."
                "cooperative_wait",
                close_and_put_during_wait,
            )

            with pytest.raises(ValueError, match="closed"):
                values.get(timeout=1)

            reader = multiprocessing.Process(target=read_child, args=(values,))
            reader.start()
            reader.join(timeout=1)

            assert reader.exitcode == 0
            assert observed == ["child"]
        finally:
            unpatch()


def test_wasm_simple_queue_closed_waiter_does_not_consume_later_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        try:
            values: Any = multiprocessing.SimpleQueue()
            observed: list[str] = []

            def put_child(handle: Any) -> None:
                handle.put("child")

            def read_child(handle: Any) -> None:
                observed.append(handle.get())

            def close_and_put_during_wait(awaitable: object) -> bool:
                async def wait_and_put() -> bool:
                    task = asyncio.create_task(cast(Any, awaitable))
                    await asyncio.sleep(0)
                    values.close()
                    process = multiprocessing.Process(
                        target=put_child,
                        args=(values,),
                    )
                    process.start()
                    await asyncio.sleep(0)
                    await asyncio.sleep(0)
                    assert process.exitcode == 0
                    return await asyncio.wait_for(task, timeout=1)

                return asyncio.run(wait_and_put())

            monkeypatch.setattr(
                "marimo._runtime._wasm._concurrency._mp_queue."
                "cooperative_wait",
                close_and_put_during_wait,
            )

            with pytest.raises(ValueError, match="closed"):
                values.get()

            reader = multiprocessing.Process(target=read_child, args=(values,))
            reader.start()
            reader.join(timeout=1)

            assert reader.exitcode == 0
            assert observed == ["child"]
        finally:
            unpatch()
