# Copyright 2026 Marimo. All rights reserved.
"""Install Pyodide concurrency patches.

`install_wasm_concurrency_shims()` keeps code that calls `threading.Thread`,
`threading.Event`, `threading.local`, and `ThreadPoolExecutor` callable in
Pyodide. Started threads and executor work run on the browser-backed asyncio
loop with synthetic thread identities. They do not create OS threads or run
Python bytecode in parallel.

The installer must run before marimo runtime modules capture `threading.local`.
If those modules were already imported, the repair step replaces their captured
runtime context storage so a synthetic child cannot tear down its parent
context.
"""

from __future__ import annotations

import sys
import threading as _threading
from typing import Any

from marimo._runtime._wasm._concurrency import _state
from marimo._runtime._wasm._concurrency._futures import (
    AsyncioThreadPoolExecutor,
)
from marimo._runtime._wasm._concurrency._threading import (
    AsyncEvent,
    AsyncioThread,
    AsyncLocal,
)
from marimo._runtime._wasm._patches import Unpatch, WasmPatchSet
from marimo._utils.platform import is_pyodide


def install_wasm_concurrency_shims() -> Unpatch:
    """Patch thread-shaped concurrency APIs in Pyodide."""
    if not is_pyodide():
        return lambda: None
    if _state.active_unpatch() is not None:
        return lambda: None

    import concurrent.futures.thread as futures_thread
    from concurrent import futures

    _state.set_patch_state(
        _state.PatchState(
            original_thread_type=_threading.Thread,
            original_current_thread=_threading.current_thread,
            original_get_ident=_threading.get_ident,
            original_get_native_id=getattr(
                _threading, "get_native_id", _threading.get_ident
            ),
            original_enumerate=_threading.enumerate,
            original_active_count=_threading.active_count,
            original_excepthook=_threading.excepthook,
        )
    )

    patches = WasmPatchSet()
    added_get_native_id = False
    try:
        if not hasattr(_threading, "get_native_id"):
            added_get_native_id = True
            _threading.get_native_id = _state.current_native_id  # type: ignore[attr-defined]

        for owner, attr, replacement in (
            (_threading, "Thread", AsyncioThread),
            (_threading, "Event", AsyncEvent),
            (_threading, "local", AsyncLocal),
            (_threading, "current_thread", _state.current_thread),
            (_threading, "currentThread", _state.current_thread),
            (_threading, "get_ident", _state.current_ident),
            (_threading, "get_native_id", _state.current_native_id),
            (_threading, "enumerate", _state.active_threads),
            (_threading, "active_count", _state.active_count),
            (_threading, "activeCount", _state.active_count),
            (futures, "ThreadPoolExecutor", AsyncioThreadPoolExecutor),
            (futures_thread, "ThreadPoolExecutor", AsyncioThreadPoolExecutor),
        ):

            def replacement_factory(
                _original: object,
                replacement: Any = replacement,
            ) -> Any:
                return replacement

            patches.replace(owner, attr, replacement_factory)

        repair_preimported_runtime_context_storage(patches)
    except BaseException:
        patches.unpatch_all()()
        if (
            added_get_native_id
            and getattr(_threading, "get_native_id", None)
            is _state.current_native_id
        ):
            del _threading.get_native_id  # type: ignore[attr-defined]
        _state.reset_runtime_state()
        raise

    unpatch = patches.unpatch_all()

    def _run_unpatch() -> None:
        unpatch()
        if (
            added_get_native_id
            and getattr(_threading, "get_native_id", None)
            is _state.current_native_id
        ):
            del _threading.get_native_id  # type: ignore[attr-defined]
        _state.reset_runtime_state()

    _state.set_active_unpatch(_run_unpatch)

    def _guarded_unpatch() -> None:
        unpatch_wasm_concurrency_shims()

    return _guarded_unpatch


def repair_preimported_runtime_context_storage(
    patches: WasmPatchSet,
) -> None:
    """Replace runtime context storage captured before the threading patch."""
    context_types = sys.modules.get("marimo._runtime.context.types")
    if context_types is None:
        return

    original_storage = getattr(context_types, "_THREAD_LOCAL_CONTEXT", None)
    if isinstance(original_storage, AsyncLocal):
        return

    class WasmRuntimeContextStorage(AsyncLocal):
        def __init__(self) -> None:
            self.runtime_context = None

        def initialize(self, runtime_context: Any) -> None:
            self.runtime_context = runtime_context

    storage = WasmRuntimeContextStorage()
    storage.runtime_context = getattr(
        original_storage,
        "runtime_context",
        None,
    )

    def _sync_before_restore() -> None:
        if original_storage is not None:
            original_storage.runtime_context = storage.runtime_context

    patches.replace(
        context_types,
        "_THREAD_LOCAL_CONTEXT",
        lambda _original: storage,
        before_restore=_sync_before_restore,
    )


def unpatch_wasm_concurrency_shims() -> None:
    """Remove active Pyodide concurrency patches."""
    unpatch = _state.active_unpatch()
    if unpatch is None:
        return
    _state.discard_finished_runtime_records()
    if _state.has_live_core_work():
        raise RuntimeError(
            "Cannot unpatch while WASM concurrency work is live"
        )
    unpatch()
