# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from types import ModuleType
from typing import Any, cast

from marimo._runtime._wasm._concurrency._install import (
    install_wasm_threading_shims,
)
from tests.conftest import mock_pyodide


def _install_run_sync() -> None:
    pyodide_module = ModuleType("pyodide")
    ffi_module = ModuleType("pyodide.ffi")

    def run_sync(awaitable: object) -> object:
        return asyncio.run(cast(Any, awaitable))

    cast(Any, ffi_module).run_sync = run_sync
    cast(Any, pyodide_module).ffi = ffi_module
    sys.modules["pyodide"] = pyodide_module
    sys.modules["pyodide.ffi"] = ffi_module


def test_wasm_threading_patch_is_inert_outside_pyodide() -> None:
    original_thread = threading.Thread
    original_local = threading.local
    original_event = threading.Event

    unpatch = install_wasm_threading_shims()
    unpatch()

    assert threading.Thread is original_thread
    assert threading.local is original_local
    assert threading.Event is original_event


def test_wasm_threading_redundant_handle_does_not_unpatch_owner() -> None:
    original_thread = threading.Thread
    original_local = threading.local

    with mock_pyodide():
        _install_run_sync()
        owner_unpatch = install_wasm_threading_shims()
        redundant_unpatch = install_wasm_threading_shims()
        try:
            assert threading.Thread is not original_thread
            assert threading.local is not original_local

            redundant_unpatch()

            assert threading.Thread is not original_thread
            assert threading.local is not original_local
        finally:
            owner_unpatch()

    assert threading.Thread is original_thread
    assert threading.local is original_local


def test_wasm_threading_repairs_preimported_runtime_context_storage() -> None:
    from marimo._runtime.context import types as context_types

    context_types.teardown_context()
    parent_context = object()
    child_context = object()
    context_types.initialize_context(parent_context)  # type: ignore[arg-type]

    with mock_pyodide():
        _install_run_sync()
        unpatch = install_wasm_threading_shims()
        try:
            assert context_types.safe_get_context() is parent_context
            observed: list[object | None] = []

            def target() -> None:
                observed.append(context_types.safe_get_context())
                context_types.initialize_context(child_context)  # type: ignore[arg-type]
                observed.append(context_types.safe_get_context())
                context_types.teardown_context()
                observed.append(context_types.safe_get_context())

            thread = threading.Thread(target=target)
            thread.start()
            thread.join(timeout=1)

            assert not thread.is_alive()
            assert observed == [None, child_context, None]
            assert context_types.safe_get_context() is parent_context
        finally:
            unpatch()
            context_types.teardown_context()


def test_top_level_marimo_import_bootstraps_wasm_threading_first() -> None:
    code = """
import json
import sys
import types
import threading
import asyncio

sys.platform = "emscripten"
pyodide = types.ModuleType("pyodide")
ffi = types.ModuleType("pyodide.ffi")
def run_sync(awaitable):
    return asyncio.run(awaitable)
ffi.run_sync = run_sync
pyodide.ffi = ffi
sys.modules["pyodide"] = pyodide
sys.modules["pyodide.ffi"] = ffi

original_thread = threading.Thread
original_local = threading.local

import marimo
from marimo._runtime.context import types as context_types
from marimo._runtime._wasm._concurrency._threading import AsyncLocal

events = []
async def target():
    events.append("start")
    await asyncio.sleep(0)
    events.append("done")

thread = marimo.Thread(target=target)
thread.start()
thread.join(timeout=1)

print(json.dumps({
    "thread_patched": threading.Thread is not original_thread,
    "local_patched": threading.local is not original_local,
    "public_thread_uses_patched_base": issubclass(
        marimo.Thread,
        threading.Thread,
    ),
    "runtime_context_uses_patched_local": isinstance(
        context_types._THREAD_LOCAL_CONTEXT,
        AsyncLocal,
    ),
    "async_thread_events": events,
    "async_thread_alive": thread.is_alive(),
}))
"""
    repo_root = Path(__file__).parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root)
    result = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == {
        "thread_patched": True,
        "local_patched": True,
        "public_thread_uses_patched_base": True,
        "runtime_context_uses_patched_local": True,
        "async_thread_events": ["start", "done"],
        "async_thread_alive": False,
    }
