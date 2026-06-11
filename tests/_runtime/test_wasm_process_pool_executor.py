# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import concurrent.futures
import contextvars
import importlib
import multiprocessing.context
import sys
import threading

import pytest

from marimo._runtime._wasm._concurrency import _process_install
from marimo._runtime._wasm._concurrency._install import (
    install_wasm_concurrency_shims,
    install_wasm_process_shims,
)
from marimo._runtime._wasm._concurrency._wait import (
    UnsupportedWasmConcurrencyError,
)
from tests._runtime._helpers.wasm import (
    install_wasm_process_test_shims,
    wait_until,
)
from tests.conftest import mock_pyodide


def test_wasm_process_pool_executor_cleans_lazily_imported_submodule() -> None:
    missing = object()
    module_name = "concurrent.futures.process"
    saved_module = sys.modules.get(module_name, missing)
    saved_parent_attr = getattr(concurrent.futures, "process", missing)

    try:
        sys.modules.pop(module_name, None)
        if hasattr(concurrent.futures, "process"):
            del concurrent.futures.process

        with mock_pyodide():
            unpatch = install_wasm_process_test_shims()
            try:
                assert module_name in sys.modules
                assert hasattr(concurrent.futures, "process")
            finally:
                unpatch()

        assert module_name not in sys.modules
        assert not hasattr(concurrent.futures, "process")
    finally:
        sys.modules.pop(module_name, None)
        if saved_module is not missing:
            sys.modules[module_name] = saved_module  # type: ignore[assignment]
        if hasattr(concurrent.futures, "process"):
            del concurrent.futures.process
        if saved_parent_attr is not missing:
            concurrent.futures.process = saved_parent_attr


def test_wasm_process_pool_executor_installs_with_process_stub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing = object()
    module_name = "concurrent.futures.process"
    saved_module = sys.modules.get(module_name, missing)
    saved_parent_attr = getattr(concurrent.futures, "process", missing)
    saved_executor_attr = vars(concurrent.futures).get(
        "ProcessPoolExecutor",
        missing,
    )
    original_import_module = _process_install.import_module

    def import_or_block(name: str) -> object:
        if name == module_name:
            raise ImportError("blocked process module")
        return original_import_module(name)

    try:
        sys.modules.pop(module_name, None)
        if hasattr(concurrent.futures, "process"):
            del concurrent.futures.process
        if "ProcessPoolExecutor" in vars(concurrent.futures):
            del concurrent.futures.ProcessPoolExecutor
        monkeypatch.setattr(
            _process_install,
            "import_module",
            import_or_block,
        )

        with mock_pyodide():
            unpatch = install_wasm_process_test_shims()
            try:
                assert module_name in sys.modules
                assert (
                    concurrent.futures.ProcessPoolExecutor.__name__
                    == "AsyncioProcessPoolExecutor"
                )
            finally:
                unpatch()

        assert module_name not in sys.modules
        assert "ProcessPoolExecutor" not in vars(concurrent.futures)
    finally:
        sys.modules.pop(module_name, None)
        if saved_module is not missing:
            sys.modules[module_name] = saved_module  # type: ignore[assignment]
        if hasattr(concurrent.futures, "process"):
            del concurrent.futures.process
        if saved_parent_attr is not missing:
            concurrent.futures.process = saved_parent_attr
        if "ProcessPoolExecutor" in vars(concurrent.futures):
            del concurrent.futures.ProcessPoolExecutor
        if saved_executor_attr is not missing:
            concurrent.futures.ProcessPoolExecutor = saved_executor_attr


def test_wasm_process_pool_executor_factories_and_methods() -> None:
    process_module = importlib.import_module("concurrent.futures.process")
    original_executor = concurrent.futures.ProcessPoolExecutor
    original_submodule_executor = process_module.ProcessPoolExecutor

    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        try:
            assert (
                concurrent.futures.ProcessPoolExecutor is not original_executor
            )
            assert (
                process_module.ProcessPoolExecutor
                is concurrent.futures.ProcessPoolExecutor
            )

            with concurrent.futures.ProcessPoolExecutor(
                max_workers=2
            ) as executor:
                assert executor.submit(lambda: 42).result() == 42
                assert list(
                    executor.map(lambda value: value * 2, [1, 2, 3])
                ) == [2, 4, 6]
                with pytest.raises(RuntimeError, match="process boom"):
                    executor.submit(
                        lambda: (_ for _ in ()).throw(
                            RuntimeError("process boom")
                        )
                    ).result()
        finally:
            unpatch()

    assert concurrent.futures.ProcessPoolExecutor is original_executor
    assert process_module.ProcessPoolExecutor is original_submodule_executor


def test_wasm_process_pool_executor_validates_parameters() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        try:
            with pytest.raises(ValueError, match="max_workers"):
                concurrent.futures.ProcessPoolExecutor(max_workers=0)
            with pytest.raises(TypeError, match="initializer"):
                concurrent.futures.ProcessPoolExecutor(initializer=object())
            with pytest.raises(TypeError, match="max_tasks_per_child"):
                concurrent.futures.ProcessPoolExecutor(
                    max_tasks_per_child="bad",  # type: ignore[arg-type]
                )
            with pytest.raises(ValueError, match="max_tasks_per_child"):
                concurrent.futures.ProcessPoolExecutor(max_tasks_per_child=0)
            with pytest.raises(
                UnsupportedWasmConcurrencyError,
                match="max_tasks_per_child",
            ):
                concurrent.futures.ProcessPoolExecutor(max_tasks_per_child=1)

            fork_context_type = getattr(
                multiprocessing.context,
                "ForkContext",
                None,
            )
            if fork_context_type is not None:
                with pytest.raises(ValueError, match="spawn"):
                    concurrent.futures.ProcessPoolExecutor(
                        mp_context=fork_context_type(),
                    )

            with concurrent.futures.ProcessPoolExecutor() as executor:
                assert list(
                    executor.map(
                        lambda value: value,
                        [1, 2],
                        buffersize=1,
                    )
                ) == [1, 2]
                for chunksize in (0, 1.5, float("nan")):
                    with pytest.raises(
                        (TypeError, ValueError),
                        match="chunksize",
                    ):
                        list(
                            executor.map(
                                lambda value: value,
                                [1],
                                chunksize=chunksize,
                            )
                        )
                with pytest.raises(ValueError, match="buffersize"):
                    list(
                        executor.map(
                            lambda value: value,
                            [1],
                            buffersize=0,
                        )
                    )
        finally:
            unpatch()


def test_wasm_process_pool_initializer_state_persists_across_tasks() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
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

            with concurrent.futures.ProcessPoolExecutor(
                max_workers=2,
                initializer=initialize,
            ) as executor:
                first = executor.submit(work).result()
                second = executor.submit(work).result()

            assert first[0] == second[0]
            assert first[1:] == (True, 1)
            assert second[1:] == (True, 2)
        finally:
            unpatch()


def test_wasm_process_pool_initializer_failure_breaks_executor() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        try:

            def initialize() -> None:
                raise RuntimeError("process initializer failed")

            with concurrent.futures.ProcessPoolExecutor(
                initializer=initialize,
            ) as executor:
                future = executor.submit(lambda: "unreachable")
                with pytest.raises(
                    RuntimeError,
                    match="process initializer failed",
                ):
                    future.result()
                with pytest.raises(RuntimeError, match="initializer failed"):
                    executor.submit(lambda: "later")
        finally:
            unpatch()


@pytest.mark.asyncio
async def test_wasm_process_pool_does_not_inherit_ambient_contextvars() -> (
    None
):
    ambient = contextvars.ContextVar("ambient", default="unset")
    ambient.set("parent")

    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        try:
            with concurrent.futures.ProcessPoolExecutor() as executor:
                future = executor.submit(lambda: ambient.get())
                await wait_until(future.done)

                assert future.result(timeout=0) == "unset"
                assert ambient.get() == "parent"
        finally:
            unpatch()


def test_wasm_process_unpatch_rejects_live_process_pool_executor() -> None:
    with mock_pyodide():
        core_unpatch = install_wasm_concurrency_shims()
        process_unpatch = install_wasm_process_shims()
        executor = concurrent.futures.ProcessPoolExecutor()
        try:
            with pytest.raises(RuntimeError, match="process work"):
                process_unpatch()
        finally:
            executor.shutdown(cancel_futures=True)
            process_unpatch()
            core_unpatch()
