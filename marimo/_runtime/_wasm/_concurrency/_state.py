# Copyright 2026 Marimo. All rights reserved.
"""Interpreter-wide state for the Pyodide threading patch.

Pyodide runs notebook code on one Python interpreter. The threading patch
therefore creates synthetic thread identities and stores the original stdlib
threading objects in one place so install, runtime lookup, and teardown agree.
"""

from __future__ import annotations

import asyncio
import contextvars
import itertools
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True)
class ThreadingPatchState:
    original_thread_type: type[Any]
    original_current_thread: Callable[[], Any]
    original_get_ident: Callable[[], int]
    original_get_native_id: Callable[[], int]
    original_enumerate: Callable[[], list[Any]]
    original_active_count: Callable[[], int]
    original_excepthook: Callable[[Any], object]


class ThreadIdentity:
    name: str = ""
    daemon: bool = False
    _ident: int | None = None
    _native_id: int | None = None

    @property
    def ident(self) -> int | None:
        return self._ident

    @property
    def native_id(self) -> int | None:
        return self._native_id

    def is_alive(self) -> bool:
        return False


current_thread_var: contextvars.ContextVar[ThreadIdentity | None] = (
    contextvars.ContextVar("marimo_wasm_current_thread", default=None)
)
live_threads: set[ThreadIdentity] = set()
fallback_loop: asyncio.AbstractEventLoop | None = None
patch_state_value: ThreadingPatchState | None = None
active_unpatch_value: Callable[[], None] | None = None

_IDENTS = itertools.count(10_000)


def new_ident() -> int:
    return next(_IDENTS)


def new_thread_name(prefix: str) -> str:
    return f"{prefix}-{new_ident()}"


def set_patch_state(patch_state: ThreadingPatchState | None) -> None:
    global patch_state_value
    patch_state_value = patch_state


def patch_state() -> ThreadingPatchState:
    if patch_state_value is None:
        raise RuntimeError("WASM threading patch is not installed")
    return patch_state_value


def set_active_unpatch(unpatch: Callable[[], None] | None) -> None:
    global active_unpatch_value
    active_unpatch_value = unpatch


def active_unpatch() -> Callable[[], None] | None:
    return active_unpatch_value


def current_identity() -> ThreadIdentity | None:
    return current_thread_var.get()


def current_ident() -> int:
    current = current_identity()
    if current is not None and current.ident is not None:
        return current.ident
    return patch_state().original_get_ident()


def current_native_id() -> int:
    current = current_identity()
    if current is not None and current.native_id is not None:
        return current.native_id
    return patch_state().original_get_native_id()


def current_thread() -> Any:
    current = current_identity()
    if current is not None:
        return current
    return patch_state().original_current_thread()


def active_threads() -> list[Any]:
    originals = patch_state().original_enumerate()
    seen = {getattr(thread, "ident", id(thread)) for thread in originals}
    active = list(originals)
    for thread in list(live_threads):
        if thread.ident not in seen and thread.is_alive():
            active.append(thread)
            seen.add(thread.ident)
    return active


def active_count() -> int:
    return len(active_threads())


def get_event_loop() -> asyncio.AbstractEventLoop:
    global fallback_loop
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        if fallback_loop is None or fallback_loop.is_closed():
            fallback_loop = asyncio.new_event_loop()
        return fallback_loop


def create_task_in_empty_wasm_context(
    loop: asyncio.AbstractEventLoop, coro: Any
) -> asyncio.Task[Any]:
    """Schedule shim work without inheriting caller `ContextVar` values."""
    context = contextvars.Context()
    try:
        return loop.create_task(coro, context=context)
    except TypeError:
        return context.run(loop.create_task, coro)


def run_until_complete_in_empty_wasm_context(
    loop: asyncio.AbstractEventLoop, awaitable: Any
) -> Any:
    """Run fallback-loop shim work outside caller `ContextVar` values."""
    return contextvars.Context().run(loop.run_until_complete, awaitable)


def reset_threading_state() -> None:
    global fallback_loop
    live_threads.clear()
    set_patch_state(None)
    set_active_unpatch(None)
    if fallback_loop is not None and not fallback_loop.is_closed():
        fallback_loop.close()
    fallback_loop = None
