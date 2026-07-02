# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import importlib
import multiprocessing
import multiprocessing.context
import sys
from types import ModuleType
from typing import Any, cast

import pytest

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


def _forbid_jspi_promising_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    pyodide_module = ModuleType("pyodide")
    ffi_module = ModuleType("pyodide.ffi")

    def run_sync(_awaitable: object) -> object:
        raise AssertionError("can_run_sync=False should avoid run_sync")

    cast(Any, ffi_module).run_sync = run_sync
    cast(Any, ffi_module).can_run_sync = lambda: False
    cast(Any, pyodide_module).ffi = ffi_module
    monkeypatch.setitem(sys.modules, "pyodide", pyodide_module)
    monkeypatch.setitem(sys.modules, "pyodide.ffi", ffi_module)


def _interrupt_jspi_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    pyodide_module = ModuleType("pyodide")
    ffi_module = ModuleType("pyodide.ffi")

    def run_sync(awaitable: object) -> object:
        close = getattr(awaitable, "close", None)
        if callable(close):
            close()
        raise KeyboardInterrupt("interrupted")

    cast(Any, ffi_module).run_sync = run_sync
    cast(Any, ffi_module).can_run_sync = lambda: True
    cast(Any, pyodide_module).ffi = ffi_module
    monkeypatch.setitem(sys.modules, "pyodide", pyodide_module)
    monkeypatch.setitem(sys.modules, "pyodide.ffi", ffi_module)


def test_wasm_pool_serialized_methods() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        try:
            with multiprocessing.Pool(2) as pool:
                assert pool.apply(lambda value: value + 1, (1,)) == 2
                assert pool.map(lambda value: value * 2, [1, 2, 3]) == [
                    2,
                    4,
                    6,
                ]
                assert pool.starmap(lambda a, b: a + b, [(1, 2), (3, 4)]) == [
                    3,
                    7,
                ]
                assert list(pool.imap(lambda value: value + 10, [1, 2])) == [
                    11,
                    12,
                ]
                assert sorted(
                    pool.imap_unordered(lambda value: value + 20, [1, 2])
                ) == [21, 22]
                assert pool.apply_async(lambda: "async").get() == "async"
        finally:
            unpatch()


def test_wasm_pool_context_and_submodule_factories() -> None:
    original_pool = multiprocessing.Pool

    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        try:
            pool_module = importlib.import_module("multiprocessing.pool")
            assert multiprocessing.Pool is not original_pool

            with pool_module.Pool(1) as pool:
                assert isinstance(pool, pool_module.Pool)
                assert pool.apply(lambda value: value + 1, (1,)) == 2

            ctx = multiprocessing.get_context("spawn")
            with ctx.Pool(1) as pool:
                assert pool.map(lambda value: value + 1, [1, 2]) == [2, 3]

            with pytest.raises(
                UnsupportedWasmConcurrencyError,
                match="multiprocessing.pool.ThreadPool",
            ):
                pool_module.ThreadPool(1)
        finally:
            unpatch()


def test_wasm_pool_rejects_unsupported_contexts() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        try:
            for context_name in ("ForkContext", "ForkServerContext"):
                context_type = getattr(
                    multiprocessing.context,
                    context_name,
                    None,
                )
                if context_type is None:
                    continue
                context = context_type()

                with pytest.raises(ValueError, match="spawn"):
                    multiprocessing.Pool(1, context=context)
                with pytest.raises(
                    UnsupportedWasmConcurrencyError,
                    match=f"{context_name}.Pool",
                ):
                    context.Pool(1)
        finally:
            unpatch()


def test_wasm_pool_unpatch_cleans_lazily_imported_pool_module() -> None:
    missing = object()
    module_name = "multiprocessing.pool"
    saved_module = sys.modules.get(module_name, missing)
    saved_parent_attr = getattr(multiprocessing, "pool", missing)

    try:
        sys.modules.pop(module_name, None)
        if hasattr(multiprocessing, "pool"):
            del multiprocessing.pool

        with mock_pyodide():
            unpatch = install_wasm_process_test_shims()
            try:
                assert module_name in sys.modules
                assert hasattr(multiprocessing, "pool")
            finally:
                unpatch()

        assert module_name not in sys.modules
        assert not hasattr(multiprocessing, "pool")
    finally:
        sys.modules.pop(module_name, None)
        if saved_module is not missing:
            sys.modules[module_name] = saved_module  # type: ignore[assignment]
        if hasattr(multiprocessing, "pool"):
            del multiprocessing.pool
        if saved_parent_attr is not missing:
            multiprocessing.pool = saved_parent_attr


def test_wasm_pool_validates_constructor_parameters() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        try:
            with pytest.raises(ValueError, match="number of processes"):
                multiprocessing.Pool(0)
            with pytest.raises(TypeError, match="initializer"):
                multiprocessing.Pool(1, initializer=object())
            for maxtasksperchild in (0, -1, 1.5, "bad"):
                with pytest.raises(ValueError, match="maxtasksperchild"):
                    multiprocessing.Pool(1, maxtasksperchild=maxtasksperchild)
            with pytest.raises(
                UnsupportedWasmConcurrencyError,
                match="maxtasksperchild",
            ):
                multiprocessing.Pool(1, maxtasksperchild=1)
        finally:
            unpatch()


def test_wasm_pool_rejects_invalid_chunksize() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        try:
            with multiprocessing.Pool(1) as pool:
                for chunksize in (0, 1.5, float("nan")):
                    with pytest.raises(
                        (TypeError, ValueError), match="Chunksize"
                    ):
                        pool.map(lambda value: value, [1], chunksize=chunksize)
                    with pytest.raises(
                        (TypeError, ValueError), match="Chunksize"
                    ):
                        pool.map_async(
                            lambda value: value, [1], chunksize=chunksize
                        )
                    with pytest.raises(
                        (TypeError, ValueError), match="Chunksize"
                    ):
                        pool.starmap(
                            lambda value: value, [(1,)], chunksize=chunksize
                        )
                    with pytest.raises(
                        (TypeError, ValueError), match="Chunksize"
                    ):
                        pool.starmap_async(
                            lambda value: value, [(1,)], chunksize=chunksize
                        )
                    with pytest.raises(
                        (TypeError, ValueError), match="Chunksize"
                    ):
                        pool.imap(
                            lambda value: value, [1], chunksize=chunksize
                        )
                    with pytest.raises(
                        (TypeError, ValueError), match="Chunksize"
                    ):
                        pool.imap_unordered(
                            lambda value: value, [1], chunksize=chunksize
                        )
        finally:
            unpatch()


def test_wasm_pool_imap_is_lazy() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        try:
            consumed: list[int] = []

            def values() -> Any:
                consumed.append(1)
                yield 1
                consumed.append(2)
                yield 2

            with multiprocessing.Pool(1) as pool:
                results = pool.imap(lambda value: value + 1, values())

                assert consumed == []
                assert next(results) == 2
                assert consumed == [1]
                assert next(results) == 3
                assert consumed == [1, 2]
        finally:
            unpatch()


@pytest.mark.asyncio
async def test_wasm_pool_map_async_defers_input_iteration() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        try:
            consumed: list[int] = []

            def values() -> Any:
                consumed.append(1)
                yield 1

            with multiprocessing.Pool(1) as pool:
                result = pool.map_async(lambda value: value + 1, values())

                assert consumed == []
                await wait_until(result.ready)
                assert result.get(timeout=0) == [2]
        finally:
            unpatch()


@pytest.mark.parametrize("method_name", ["imap", "imap_unordered"])
@pytest.mark.asyncio
async def test_wasm_pool_imap_next_timeout_keeps_pending_item(
    method_name: str,
) -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        try:
            with multiprocessing.Pool(1) as pool:
                results = getattr(pool, method_name)(
                    lambda value: value + 1,
                    [1],
                )

                with pytest.raises(multiprocessing.TimeoutError):
                    results.next(timeout=0)

                for _ in range(10):
                    await asyncio.sleep(0)
                    try:
                        assert results.next(timeout=0) == 2
                        break
                    except multiprocessing.TimeoutError:
                        continue
                else:
                    raise AssertionError("pending imap result did not finish")

                with pytest.raises(StopIteration):
                    results.next(timeout=0)
        finally:
            unpatch()


@pytest.mark.parametrize("method_name", ["imap", "imap_unordered"])
def test_wasm_pool_imap_drains_after_close(method_name: str) -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        pool = multiprocessing.Pool(1)
        try:
            results = getattr(pool, method_name)(
                lambda value: value + 1,
                [1, 2],
            )

            pool.close()

            assert sorted(results) == [2, 3]
        finally:
            pool.join()
            unpatch()


@pytest.mark.parametrize("method_name", ["imap", "imap_unordered"])
def test_wasm_pool_imap_results_survive_close_and_join(
    method_name: str,
) -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        pool = multiprocessing.Pool(1)
        try:
            results = getattr(pool, method_name)(
                lambda value: value + 1,
                [1, 2],
            )

            pool.close()
            pool.join()

            assert sorted(results) == [2, 3]
        finally:
            unpatch()


@pytest.mark.parametrize("method_name", ["imap", "imap_unordered"])
def test_wasm_pool_imap_source_errors_survive_join(
    method_name: str,
) -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        pool = multiprocessing.Pool(1)
        try:

            def values() -> Any:
                yield 1
                raise RuntimeError("source failed")

            results = getattr(pool, method_name)(
                lambda value: value + 1,
                values(),
            )

            pool.close()
            pool.join()

            assert next(results) == 2
            with pytest.raises(RuntimeError, match="source failed"):
                next(results)
        finally:
            unpatch()


def test_wasm_pool_rejects_closed_work_before_consuming_iterables() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        pool = multiprocessing.Pool(1)
        try:
            pool.close()
            consumed: list[str] = []

            def values(label: str) -> Any:
                consumed.append(label)
                yield 1

            with pytest.raises(ValueError, match="Pool not running"):
                pool.map_async(lambda value: value, values("map"))
            with pytest.raises(ValueError, match="Pool not running"):
                pool.starmap_async(
                    lambda value: value,
                    ((value,) for value in values("starmap")),
                )
            with pytest.raises(ValueError, match="Pool not running"):
                list(pool.imap(lambda value: value, [1], chunksize=0))

            assert consumed == []
        finally:
            pool.join()
            unpatch()


def test_wasm_pool_callbacks() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        try:
            callbacks: list[tuple[str, int | str]] = []
            with multiprocessing.Pool(1) as pool:
                result = pool.apply_async(
                    lambda: 10,
                    callback=lambda value: callbacks.append(("ok", value)),
                )
                assert result.get() == 10
                assert result.ready()
                assert result.successful()

                failed = pool.apply_async(
                    lambda: (_ for _ in ()).throw(ValueError("bad")),
                    error_callback=lambda exc: callbacks.append(
                        ("error", type(exc).__name__)
                    ),
                )
                with pytest.raises(ValueError, match="bad"):
                    failed.get()
                assert failed.ready()
                assert not failed.successful()

                user_timeout = pool.apply_async(
                    lambda: (_ for _ in ()).throw(TimeoutError("user timeout"))
                )
                with pytest.raises(TimeoutError, match="user timeout"):
                    user_timeout.get()

            assert callbacks == [("ok", 10), ("error", "ValueError")]
        finally:
            unpatch()


def test_wasm_pool_starmap_async_reports_malformed_rows() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        try:
            callbacks: list[str] = []
            with multiprocessing.Pool(1) as pool:
                result = pool.starmap_async(
                    lambda left, right: left + right,
                    [1],
                    error_callback=lambda exc: callbacks.append(
                        type(exc).__name__
                    ),
                )

                with pytest.raises(TypeError):
                    result.get()

            assert callbacks == ["TypeError"]
        finally:
            unpatch()


@pytest.mark.parametrize("method_name", ["map_async", "starmap_async"])
def test_wasm_pool_async_map_reports_source_iteration_errors(
    method_name: str,
) -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        try:
            callbacks: list[str] = []

            def values() -> Any:
                yield (1, 2) if method_name == "starmap_async" else 1
                raise RuntimeError("source failed")

            with multiprocessing.Pool(1) as pool:
                result = getattr(pool, method_name)(
                    lambda *args: sum(args),
                    values(),
                    error_callback=lambda exc: callbacks.append(
                        type(exc).__name__
                    ),
                )

                with pytest.raises(RuntimeError, match="source failed"):
                    result.get()

            assert callbacks == ["RuntimeError"]
        finally:
            unpatch()


def test_wasm_pool_wait_suppresses_worker_unsupported_error() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        try:
            with multiprocessing.Pool(1) as pool:
                result = pool.apply_async(
                    lambda: (_ for _ in ()).throw(
                        UnsupportedWasmConcurrencyError("worker")
                    )
                )

                result.wait()

                assert result.ready()
                with pytest.raises(
                    UnsupportedWasmConcurrencyError,
                    match="worker",
                ):
                    result.get()
        finally:
            unpatch()


def test_wasm_pool_join_suppresses_worker_unsupported_error() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        unpatched = False
        pool = multiprocessing.Pool(1)
        try:
            result = pool.apply_async(
                lambda: (_ for _ in ()).throw(
                    UnsupportedWasmConcurrencyError("worker")
                )
            )

            pool.close()
            pool.join()

            assert result.ready()
            with pytest.raises(
                UnsupportedWasmConcurrencyError,
                match="worker",
            ):
                result.get()
            unpatch()
            unpatched = True
        finally:
            if not unpatched:
                try:
                    pool.terminate()
                    pool.join()
                except BaseException:
                    pass
                unpatch()


@pytest.mark.asyncio
async def test_wasm_pool_async_get_timeout_uses_multiprocessing_error() -> (
    None
):
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        try:
            with multiprocessing.Pool(processes=1) as pool:
                result = pool.apply_async(lambda: "released")

                with pytest.raises(multiprocessing.TimeoutError):
                    result.get(timeout=0)

                await wait_until(result.ready)
                assert result.get(timeout=0) == "released"
        finally:
            unpatch()


@pytest.mark.asyncio
async def test_wasm_pool_async_wait_reports_missing_jspi_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        _forbid_jspi_promising_frame(monkeypatch)
        try:
            with multiprocessing.Pool(processes=1) as pool:
                result = pool.apply_async(lambda: "released")

                with pytest.raises(
                    UnsupportedWasmConcurrencyError,
                    match="JSPI promising frame",
                ):
                    result.wait(timeout=1)

                await wait_until(result.ready)
                assert result.get(timeout=0) == "released"
        finally:
            unpatch()


@pytest.mark.asyncio
async def test_wasm_pool_async_wait_reraises_pending_wait_interrupt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        _interrupt_jspi_wait(monkeypatch)
        try:
            with multiprocessing.Pool(processes=1) as pool:
                result = pool.apply_async(lambda: "released")

                with pytest.raises(KeyboardInterrupt, match="interrupted"):
                    result.wait(timeout=1)

                await wait_until(result.ready)
                assert result.get(timeout=0) == "released"
        finally:
            unpatch()


def test_wasm_pool_close_and_join_lifecycle() -> None:
    with mock_pyodide():
        unpatch = install_wasm_process_test_shims()
        pool = multiprocessing.Pool(1)
        try:
            with pytest.raises(ValueError, match="still running"):
                pool.join()

            pool.close()
            with pytest.raises(ValueError, match="Pool not running"):
                pool.apply(lambda: None)
            pool.join()
        finally:
            unpatch()


def test_wasm_process_unpatch_rejects_live_pool_executor() -> None:
    with mock_pyodide():
        core_unpatch = install_wasm_concurrency_shims()
        process_unpatch = install_wasm_process_shims()
        pool = multiprocessing.Pool(1)
        try:
            with pytest.raises(RuntimeError, match="process work"):
                process_unpatch()

            pool.close()
            pool.join()
        finally:
            try:
                pool.terminate()
                pool.join()
            except BaseException:
                pass
            process_unpatch()
            core_unpatch()
