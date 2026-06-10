# Copyright 2026 Marimo. All rights reserved.
"""Interpreter-wide state for Pyodide concurrency patches.

Pyodide runs notebook code on one Python interpreter. The patches therefore
create synthetic thread identities and store original stdlib objects in one
place so install, runtime lookup, and teardown agree.
"""

from __future__ import annotations

import asyncio
import contextvars
import functools
import itertools
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True)
class PatchState:
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
live_executors: set[Any] = set()
live_executor_tasks: set[asyncio.Task[Any]] = set()
live_processes: set[Any] = set()
live_process_tasks: dict[Any, set[asyncio.Task[Any]]] = {}
fallback_loop: asyncio.AbstractEventLoop | None = None
patch_state_value: PatchState | None = None
active_unpatch_value: Callable[[], None] | None = None
active_process_unpatch_value: Callable[[], None] | None = None
inherited_context_vars: list[contextvars.ContextVar[Any]] = []
process_owner_getter: Callable[[], Any | None] | None = None
process_task_tracking_suppressed: contextvars.ContextVar[bool] = (
    contextvars.ContextVar(
        "marimo_wasm_process_task_tracking_suppressed",
        default=False,
    )
)

_IDENTS = itertools.count(10_000)


def new_ident() -> int:
    return next(_IDENTS)


def new_thread_name(prefix: str) -> str:
    return f"{prefix}-{new_ident()}"


def set_patch_state(patch_state: PatchState | None) -> None:
    global patch_state_value
    patch_state_value = patch_state


def patch_state() -> PatchState:
    if patch_state_value is None:
        raise RuntimeError("WASM concurrency shim is not installed")
    return patch_state_value


def set_active_unpatch(unpatch: Callable[[], None] | None) -> None:
    global active_unpatch_value
    active_unpatch_value = unpatch


def active_unpatch() -> Callable[[], None] | None:
    return active_unpatch_value


def set_active_process_unpatch(unpatch: Callable[[], None] | None) -> None:
    global active_process_unpatch_value
    active_process_unpatch_value = unpatch


def active_process_unpatch() -> Callable[[], None] | None:
    return active_process_unpatch_value


def register_inherited_context_var(
    context_var: contextvars.ContextVar[Any],
) -> None:
    if context_var not in inherited_context_vars:
        inherited_context_vars.append(context_var)


def empty_wasm_context() -> contextvars.Context:
    context = contextvars.Context()
    for context_var in inherited_context_vars:
        try:
            value = context_var.get()
        except LookupError:
            continue
        context.run(context_var.set, value)
    return context


def set_process_owner_getter(getter: Callable[[], Any | None]) -> None:
    global process_owner_getter
    process_owner_getter = getter


def current_process_owner() -> Any | None:
    if process_owner_getter is None:
        return None
    return process_owner_getter()


def loop_create_task_wrapper(
    original: Callable[..., asyncio.Task[Any]],
) -> Callable[..., asyncio.Task[Any]]:
    @functools.wraps(original)
    def create_task(*args: Any, **kwargs: Any) -> asyncio.Task[Any]:
        task = original(*args, **kwargs)
        owner = current_process_owner()
        if owner is not None and not process_task_tracking_suppressed.get():
            register_process_task(owner, task)
        return task

    return create_task


def register_process_task(owner: Any, task: asyncio.Task[Any]) -> None:
    if task.done():
        return
    tasks = live_process_tasks.setdefault(owner, set())
    tasks.add(task)

    def _discard(done_task: asyncio.Task[Any]) -> None:
        owner_tasks = live_process_tasks.get(owner)
        if owner_tasks is None:
            return
        owner_tasks.discard(done_task)
        if not owner_tasks:
            live_process_tasks.pop(owner, None)

    task.add_done_callback(_discard)


def has_process_tasks(owner: Any) -> bool:
    tasks = live_process_tasks.get(owner)
    if tasks is None:
        return False
    for task in list(tasks):
        if task.done():
            tasks.discard(task)
    if not tasks:
        live_process_tasks.pop(owner, None)
        return False
    return True


def cancel_process_tasks(owner: Any) -> None:
    for task in list(live_process_tasks.get(owner, ())):
        if not task.done():
            task.cancel()


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
    context = empty_wasm_context()

    async def run_without_tracking_suppression() -> Any:
        nested_token = process_task_tracking_suppressed.set(False)
        try:
            return await coro
        finally:
            process_task_tracking_suppressed.reset(nested_token)

    token = process_task_tracking_suppressed.set(True)
    try:
        try:
            return loop.create_task(coro, context=context)
        except TypeError:

            def create_task() -> asyncio.Task[Any]:
                nested_token = process_task_tracking_suppressed.set(True)
                try:
                    return loop.create_task(run_without_tracking_suppression())
                finally:
                    process_task_tracking_suppressed.reset(nested_token)

            return context.run(create_task)
    finally:
        process_task_tracking_suppressed.reset(token)


def run_until_complete_in_empty_wasm_context(
    loop: asyncio.AbstractEventLoop, awaitable: Any
) -> Any:
    """Run fallback-loop shim work outside caller `ContextVar` values."""
    if asyncio.isfuture(awaitable):
        return loop.run_until_complete(awaitable)
    task = create_task_in_empty_wasm_context(loop, awaitable)
    return loop.run_until_complete(task)


def register_executor(executor: Any) -> None:
    live_executors.add(executor)


def unregister_executor(executor: Any) -> None:
    live_executors.discard(executor)


def executor_task_registry() -> set[asyncio.Task[Any]]:
    return live_executor_tasks


def discard_finished_runtime_records() -> None:
    for thread in list(live_threads):
        if not thread.is_alive():
            live_threads.discard(thread)
    for executor in list(live_executors):
        if _executor_is_idle(executor):
            unregister_executor(executor)
    for task in list(live_executor_tasks):
        if task.done():
            live_executor_tasks.discard(task)
    for process in list(live_processes):
        if not process.is_alive():
            live_processes.discard(process)
    for owner in list(live_process_tasks):
        has_process_tasks(owner)


def has_live_core_work() -> bool:
    return bool(live_threads or live_executors or live_executor_tasks)


def has_live_process_work() -> bool:
    return bool(live_processes or live_process_tasks)


def _executor_is_idle(executor: Any) -> bool:
    is_idle_for_wasm_teardown = getattr(
        executor, "is_idle_for_wasm_teardown", None
    )
    if not callable(is_idle_for_wasm_teardown):
        return False
    return bool(is_idle_for_wasm_teardown())


def reset_runtime_state() -> None:
    global fallback_loop
    live_threads.clear()
    live_executors.clear()
    live_executor_tasks.clear()
    live_processes.clear()
    live_process_tasks.clear()
    if fallback_loop is not None and not fallback_loop.is_closed():
        fallback_loop.close()
    fallback_loop = None
    set_patch_state(None)
    set_active_unpatch(None)
    set_active_process_unpatch(None)
