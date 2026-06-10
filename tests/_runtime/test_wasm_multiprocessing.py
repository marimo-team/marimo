# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import concurrent.futures
import multiprocessing
import multiprocessing.context
import threading
from typing import Any

import pytest

from marimo._runtime._wasm._concurrency import _state
from marimo._runtime._wasm._concurrency._install import (
    install_wasm_concurrency_shims,
    install_wasm_process_shims,
    replace_loop_create_task,
)
from marimo._runtime._wasm._concurrency._wait import (
    UnsupportedWasmConcurrencyError,
)
from marimo._runtime._wasm._patches import WasmPatchSet
from tests._runtime._helpers.wasm import (
    install_wasm_process_test_shims,
    wait_until,
)
from tests.conftest import mock_pyodide


def test_wasm_process_runs_same_interpreter_target() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        values: list[tuple[str, str | None, int | None]] = []

        def worker(output: list[tuple[str, str | None, int | None]]) -> None:
            current = multiprocessing.current_process()
            parent = multiprocessing.parent_process()
            output.append(
                (
                    current.name,
                    None if parent is None else parent.name,
                    current.pid,
                )
            )

        def read_sentinel(process: Any) -> int:
            return process.sentinel

        try:
            process = multiprocessing.Process(
                target=worker, args=(values,), name="child"
            )
            assert process.pid is None
            assert process.exitcode is None
            assert not process.is_alive()

            process.start()
            process.join(timeout=1)

            assert process.pid is not None
            assert process.ident == process.pid
            assert not process.is_alive()
            assert process.exitcode == 0
            assert values == [("child", "MainProcess", process.pid)]
            assert multiprocessing.active_children() == []
            with pytest.raises(UnsupportedWasmConcurrencyError):
                read_sentinel(process)
        finally:
            unpatch()


def test_wasm_process_context_uses_spawn_process_factory() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        values: list[str] = []
        try:
            assert multiprocessing.cpu_count() == 1
            assert multiprocessing.get_all_start_methods() == ["spawn"]
            assert multiprocessing.get_start_method() == "spawn"
            multiprocessing.set_start_method("spawn")
            with pytest.raises(ValueError, match="only supports 'spawn'"):
                multiprocessing.set_start_method("fork")

            ctx = multiprocessing.get_context("spawn")
            assert ctx.cpu_count() == 1
            assert ctx.current_process().name == "MainProcess"
            assert ctx.current_process().ident == ctx.current_process().pid
            assert ctx.parent_process() is None
            assert isinstance(ctx.Process, type)
            assert ctx.Process is multiprocessing.context.SpawnProcess
            with pytest.raises(ValueError, match="only supports 'spawn'"):
                multiprocessing.get_context("fork")

            class CustomProcess(ctx.Process):
                pass

            process = CustomProcess(target=values.append, args=("ctx",))
            process.start()
            process.join(timeout=1)

            assert process.exitcode == 0
            assert values == ["ctx"]
        finally:
            unpatch()


def test_wasm_process_sets_exitcode_for_target_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(threading, "excepthook", lambda _args: None)

    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()

        def fail() -> None:
            raise ValueError("boom")

        def exit_with_code() -> None:
            raise SystemExit(3)

        try:
            failed = multiprocessing.Process(target=fail)
            failed.start()
            failed.join(timeout=1)

            exited = multiprocessing.Process(target=exit_with_code)
            exited.start()
            exited.join(timeout=1)

            assert failed.exitcode == 1
            assert exited.exitcode == 3
        finally:
            unpatch()


@pytest.mark.asyncio
async def test_wasm_active_children_is_scoped_to_current_process() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        started = asyncio.Event()
        release = asyncio.Event()
        child_seen_children: list[list[object]] = []

        async def worker() -> None:
            child_seen_children.append(multiprocessing.active_children())
            started.set()
            await release.wait()

        try:
            process = multiprocessing.Process(target=worker, name="child")
            process.start()
            await asyncio.wait_for(started.wait(), timeout=1)

            assert multiprocessing.active_children() == [process]
            assert child_seen_children == [[]]

            release.set()
            await wait_until(lambda: not process.is_alive())
            assert multiprocessing.active_children() == []
        finally:
            unpatch()


def test_wasm_process_start_requires_creator_process() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        child = multiprocessing.Process(target=lambda: None)
        errors: list[str] = []

        async def worker() -> None:
            try:
                child.start()
            except AssertionError as exc:
                errors.append(str(exc))

        try:
            process = multiprocessing.Process(target=worker)
            process.start()
            process.join(timeout=1)

            assert process.exitcode == 0
            assert child.exitcode is None
            assert errors == [
                "can only start a process object created by current process"
            ]
        finally:
            unpatch()


def test_wasm_daemon_process_cannot_start_child_process() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        errors: list[str] = []
        child_daemon_defaults: list[bool] = []

        async def worker() -> None:
            child = multiprocessing.Process(target=lambda: None)
            child_daemon_defaults.append(child.daemon)
            try:
                child.start()
            except AssertionError as exc:
                errors.append(str(exc))

        try:
            process = multiprocessing.Process(target=worker, daemon=True)
            process.start()
            process.join(timeout=1)

            assert process.exitcode == 0
            assert child_daemon_defaults == [True]
            assert errors == [
                "daemonic processes are not allowed to have children"
            ]
        finally:
            unpatch()


def test_wasm_process_identity_reaches_synthetic_thread_lanes() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        seen: list[tuple[str, str | None]] = []

        def process_identity() -> tuple[str, str | None]:
            current = multiprocessing.current_process()
            parent = multiprocessing.parent_process()
            return current.name, None if parent is None else parent.name

        async def worker() -> None:
            def thread_target() -> None:
                seen.append(process_identity())

            thread = threading.Thread(target=thread_target)
            thread.start()
            await wait_until(lambda: bool(seen))

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(process_identity)
                await wait_until(future.done)
                seen.append(future.result(timeout=0))

        try:
            process = multiprocessing.Process(target=worker, name="child")
            process.start()
            process.join(timeout=1)

            assert process.exitcode == 0
            assert seen == [
                ("child", "MainProcess"),
                ("child", "MainProcess"),
            ]
        finally:
            unpatch()


def test_wasm_process_waits_for_owned_background_thread() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        events: list[str] = []

        async def worker() -> None:
            async def background() -> None:
                events.append("thread-start")
                await asyncio.sleep(0)
                events.append("thread-done")

            thread = threading.Thread(target=background)
            thread.start()
            events.append("target-returned")

        try:
            process = multiprocessing.Process(target=worker)
            process.start()
            process.join(timeout=1)

            assert process.exitcode == 0
            assert events == [
                "target-returned",
                "thread-start",
                "thread-done",
            ]
        finally:
            unpatch()


def test_wasm_process_cancels_owned_daemon_thread_on_exit() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        events: list[str] = []

        async def worker() -> None:
            async def background() -> None:
                events.append("daemon-start")
                await asyncio.Event().wait()
                events.append("daemon-after-exit")

            thread = threading.Thread(target=background, daemon=True)
            thread.start()
            await wait_until(lambda: bool(events))

        try:
            process = multiprocessing.Process(target=worker)
            process.start()
            process.join(timeout=1)

            assert process.exitcode == 0
            assert events == ["daemon-start"]
        finally:
            unpatch()


def test_wasm_process_exception_cleans_owned_daemon_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(threading, "excepthook", lambda _args: None)

    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        events: list[str] = []

        async def worker() -> None:
            async def background() -> None:
                events.append("daemon-start")
                await asyncio.Event().wait()
                events.append("daemon-after-exception")

            thread = threading.Thread(target=background, daemon=True)
            thread.start()
            await wait_until(lambda: bool(events))
            raise ValueError("boom")

        try:
            process = multiprocessing.Process(target=worker)
            process.start()
            process.join(timeout=1)

            assert process.exitcode == 1
            assert events == ["daemon-start"]
        finally:
            unpatch()


def test_wasm_process_kills_owned_daemon_child_on_exit() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        events: list[str] = []
        children: list[multiprocessing.Process] = []

        async def child_worker() -> None:
            events.append("child-start")
            await asyncio.Event().wait()
            events.append("child-after-exit")

        async def parent_worker() -> None:
            child = multiprocessing.Process(target=child_worker, daemon=True)
            children.append(child)
            child.start()
            await wait_until(lambda: events == ["child-start"])
            events.append("parent-returned")

        try:
            process = multiprocessing.Process(target=parent_worker)
            process.start()
            process.join(timeout=1)

            assert process.exitcode == 0
            assert not children[0].is_alive()
            assert children[0].exitcode == -1
            assert events == ["child-start", "parent-returned"]
        finally:
            unpatch()


def test_wasm_process_cancels_owned_asyncio_task_on_exit() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        events: list[str] = []
        tasks: list[asyncio.Task[None]] = []

        async def worker() -> None:
            async def background() -> None:
                events.append("task-start")
                await asyncio.Event().wait()
                events.append("task-after-exit")

            tasks.append(asyncio.create_task(background()))
            await wait_until(lambda: events == ["task-start"])

        try:
            process = multiprocessing.Process(target=worker)
            process.start()
            process.join(timeout=1)

            assert process.exitcode == 0
            assert tasks[0].cancelled()
            assert events == ["task-start"]
        finally:
            unpatch()


@pytest.mark.asyncio
async def test_wasm_process_does_not_poison_loop_default_executor() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        events: list[str] = []

        async def worker() -> None:
            events.append(await asyncio.to_thread(lambda: "inside-process"))

        try:
            process = multiprocessing.Process(target=worker)
            process.start()
            await wait_until(lambda: not process.is_alive())

            assert process.exitcode == 0
            assert events == ["inside-process"]
            assert await asyncio.to_thread(lambda: "after-process") == (
                "after-process"
            )
        finally:
            loop = asyncio.get_running_loop()
            default_executor = getattr(loop, "_default_executor", None)
            if default_executor is not None:
                default_executor.shutdown(wait=False, cancel_futures=True)
                loop._default_executor = None
            unpatch()


def test_wasm_process_waits_for_owned_executor_work() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        events: list[str] = []
        executors: list[concurrent.futures.Executor] = []

        async def worker() -> None:
            executor = concurrent.futures.ThreadPoolExecutor()
            executors.append(executor)
            executor.submit(lambda: events.append("executor-done"))
            events.append("target-returned")

        try:
            process = multiprocessing.Process(target=worker)
            process.start()
            process.join(timeout=1)

            assert process.exitcode == 0
            assert events == ["target-returned", "executor-done"]
        finally:
            for executor in executors:
                executor.shutdown(wait=False, cancel_futures=True)
            unpatch()


def test_wasm_process_shuts_down_owned_executor_on_exit() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        events: list[str] = []
        executors: list[concurrent.futures.Executor] = []

        async def worker() -> None:
            executor = concurrent.futures.ThreadPoolExecutor()
            executors.append(executor)
            executor.submit(lambda: events.append("executor-done"))
            events.append("target-returned")

        try:
            process = multiprocessing.Process(target=worker)
            process.start()
            process.join(timeout=1)

            assert process.exitcode == 0
            assert events == ["target-returned", "executor-done"]
            with pytest.raises(RuntimeError, match="shutdown"):
                executors[0].submit(lambda: None)
        finally:
            unpatch()


def test_wasm_process_waits_for_reused_executor_submissions() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        executor = concurrent.futures.ThreadPoolExecutor()
        events: list[str] = []

        async def worker(label: str) -> None:
            executor.submit(lambda: events.append(label))

        try:
            first = multiprocessing.Process(target=worker, args=("first",))
            first.start()
            first.join(timeout=1)

            second = multiprocessing.Process(target=worker, args=("second",))
            second.start()
            second.join(timeout=1)

            assert first.exitcode == 0
            assert second.exitcode == 0
            assert events == ["first", "second"]
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
            unpatch()


@pytest.mark.asyncio
async def test_wasm_process_terminate_suppresses_requested_cancel_excepthook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    excepthook_types: list[type[BaseException]] = []
    monkeypatch.setattr(
        threading,
        "excepthook",
        lambda args: excepthook_types.append(args.exc_type),
    )

    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        started = asyncio.Event()

        async def worker() -> None:
            started.set()
            await asyncio.Event().wait()

        try:
            process = multiprocessing.Process(target=worker)
            process.start()
            await asyncio.wait_for(started.wait(), timeout=1)

            process.terminate()
            await wait_until(lambda: not process.is_alive())

            assert process.exitcode == -1
            assert excepthook_types == []
        finally:
            unpatch()


@pytest.mark.asyncio
async def test_wasm_process_terminate_cancels_owned_thread_work() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        started = asyncio.Event()
        events: list[str] = []

        async def worker() -> None:
            async def background() -> None:
                events.append("background-start")
                started.set()
                await asyncio.Event().wait()
                events.append("background-after-cancel")

            thread = threading.Thread(target=background)
            thread.start()
            await started.wait()
            await asyncio.Event().wait()

        try:
            process = multiprocessing.Process(target=worker)
            process.start()
            await asyncio.wait_for(started.wait(), timeout=1)

            process.terminate()
            await wait_until(lambda: not process.is_alive())
            await asyncio.sleep(0)

            assert process.exitcode == -1
            assert events == ["background-start"]
        finally:
            unpatch()


def test_wasm_process_task_tracking_patches_active_loop_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class CustomLoop:
        def create_task(self, coro: Any) -> Any:
            return coro

    loop = CustomLoop()
    original_create_task = CustomLoop.create_task
    monkeypatch.setattr(_state, "get_event_loop", lambda: loop)

    with mock_pyodide():
        patches = WasmPatchSet()
        try:
            replace_loop_create_task(patches)

            assert CustomLoop.create_task is not original_create_task
        finally:
            patches.unpatch_all()()

    assert CustomLoop.create_task is original_create_task


def test_wasm_process_install_requires_core_shims() -> None:
    original_process = multiprocessing.Process

    with mock_pyodide():
        with pytest.raises(RuntimeError, match="must be installed"):
            install_wasm_process_shims()

    assert multiprocessing.Process is original_process


def test_wasm_process_unpatch_restores_process_patches() -> None:
    original_process = multiprocessing.Process
    original_context_process = multiprocessing.context.Process
    base_context_descriptors = {
        name: vars(multiprocessing.context.BaseContext)[name]
        for name in (
            "current_process",
            "parent_process",
            "active_children",
        )
    }

    with mock_pyodide():
        core_unpatch = install_wasm_concurrency_shims()
        process_unpatch = install_wasm_process_shims()
        try:
            assert multiprocessing.Process is not original_process
            assert (
                multiprocessing.context.Process is not original_context_process
            )

            process_unpatch()

            assert multiprocessing.Process is original_process
            assert multiprocessing.context.Process is original_context_process
            assert {
                name: vars(multiprocessing.context.BaseContext)[name]
                for name in base_context_descriptors
            } == base_context_descriptors
            ctx = multiprocessing.get_context("spawn")
            assert ctx.current_process().name == "MainProcess"
            assert ctx.parent_process() is None
            assert ctx.active_children() == []
        finally:
            process_unpatch()
            core_unpatch()


def test_wasm_core_unpatch_requires_process_unpatch_first() -> None:
    with mock_pyodide():
        core_unpatch = install_wasm_concurrency_shims()
        process_unpatch = install_wasm_process_shims()
        try:
            with pytest.raises(RuntimeError, match="process shims"):
                core_unpatch()
        finally:
            process_unpatch()
            core_unpatch()


def test_wasm_runtime_bootstrap_installs_process_shim() -> None:
    from marimo._runtime._wasm import ensure_wasm_runtime_bootstrapped

    original_process = multiprocessing.Process
    values: list[str] = []

    with mock_pyodide():
        unpatch = ensure_wasm_runtime_bootstrapped()
        try:
            assert multiprocessing.Process is not original_process
            process = multiprocessing.Process(
                target=values.append, args=("bootstrapped",)
            )
            process.start()
            process.join(timeout=1)

            assert process.exitcode == 0
            assert values == ["bootstrapped"]
        finally:
            unpatch()

    assert multiprocessing.Process is original_process
