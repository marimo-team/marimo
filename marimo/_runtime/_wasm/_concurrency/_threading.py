# Copyright 2026 Marimo. All rights reserved.
"""Map a minimal `threading` surface to Pyodide asyncio tasks.

The patch keeps `threading.Thread`, `threading.Event`, and `threading.local`
callable in WASM notebooks. It does not create OS threads. Each started thread
receives a synthetic identity so `threading.local` and marimo runtime context
storage stay isolated.
"""

from __future__ import annotations

import asyncio
import inspect
import threading as _threading
import traceback
import weakref
from typing import TYPE_CHECKING, Any, cast

from marimo._runtime._wasm._concurrency._state import (
    ThreadIdentity,
    create_task_in_empty_wasm_context,
    current_ident,
    current_identity,
    current_process_owner,
    current_thread,
    current_thread_var,
    get_event_loop,
    live_threads,
    new_ident,
    new_thread_name,
    patch_state,
    run_until_complete_in_empty_wasm_context,
)
from marimo._runtime._wasm._concurrency._wait import (
    cooperative_wait,
    wait_for_future,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable


_ASYNC_LOCALS: weakref.WeakSet[AsyncLocal] = weakref.WeakSet()


def clear_thread_local_state(ident: int) -> None:
    """Remove per-thread storage when a synthetic thread finishes."""
    for local in list(_ASYNC_LOCALS):
        storage: dict[int, dict[str, Any]] = object.__getattribute__(
            local, "_storage"
        )
        initialized: set[int] = object.__getattribute__(
            local, "_initialized_idents"
        )
        initializing: set[int] = object.__getattribute__(
            local, "_initializing_idents"
        )
        storage.pop(ident, None)
        initialized.discard(ident)
        initializing.discard(ident)


class AsyncLocal:
    """`threading.local` backed by the current synthetic thread identity."""

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        if cls is AsyncLocal and (args or kwargs):
            raise TypeError("Initialization arguments are not supported")
        self = super().__new__(cls)
        object.__setattr__(self, "_storage", {})
        object.__setattr__(self, "_local_args", args)
        object.__setattr__(self, "_local_kwargs", kwargs)
        object.__setattr__(self, "_initialized_idents", {current_ident()})
        object.__setattr__(self, "_initializing_idents", set())
        _ASYNC_LOCALS.add(self)
        return self

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if args or kwargs:
            raise TypeError("Initialization arguments are not supported")

    def _namespace(self) -> dict[str, Any]:
        storage: dict[int, dict[str, Any]] = object.__getattribute__(
            self, "_storage"
        )
        ident = current_ident()
        namespace = storage.setdefault(ident, {})
        initialized: set[int] = object.__getattribute__(
            self, "_initialized_idents"
        )
        initializing: set[int] = object.__getattribute__(
            self, "_initializing_idents"
        )
        if ident in initialized or ident in initializing:
            return namespace

        initializing.add(ident)
        try:
            type(self).__init__(
                self,
                *object.__getattribute__(self, "_local_args"),
                **object.__getattribute__(self, "_local_kwargs"),
            )
        finally:
            initializing.remove(ident)
        initialized.add(ident)
        return namespace

    def __getattribute__(self, name: str) -> Any:
        if name in {
            "_storage",
            "_local_args",
            "_local_kwargs",
            "_initialized_idents",
            "_initializing_idents",
            "_namespace",
            "_data_descriptor",
        }:
            return object.__getattribute__(self, name)
        if name == "__dict__":
            return self._namespace()
        if self._data_descriptor(name) is not None:
            return object.__getattribute__(self, name)

        namespace = self._namespace()
        if name in namespace:
            return namespace[name]
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            raise AttributeError(name) from None

    def _data_descriptor(self, name: str) -> Any:
        for cls in type(self).__mro__:
            class_attribute = vars(cls).get(name)
            if hasattr(class_attribute, "__get__") and (
                hasattr(class_attribute, "__set__")
                or hasattr(class_attribute, "__delete__")
            ):
                return class_attribute
        return None

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_storage" or self._data_descriptor(name) is not None:
            object.__setattr__(self, name, value)
            return
        self._namespace()[name] = value

    def __delattr__(self, name: str) -> None:
        if self._data_descriptor(name) is not None:
            object.__delattr__(self, name)
            return
        namespace = self._namespace()
        try:
            del namespace[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


class AsyncEvent:
    """`threading.Event` with cooperative waits in Pyodide."""

    def __init__(self) -> None:
        self._flag = False
        self._async_events: list[asyncio.Event] = []

    def is_set(self) -> bool:
        return self._flag

    isSet = is_set

    def set(self) -> None:
        self._flag = True
        for event in list(self._async_events):
            event.set()

    def clear(self) -> None:
        self._flag = False
        self._async_events = [
            event for event in self._async_events if not event.is_set()
        ]

    async def _wait(self, timeout: float | None) -> bool:
        if self._flag:
            return True
        event = asyncio.Event()
        self._async_events.append(event)
        try:
            if timeout is None:
                await event.wait()
                return True
            if timeout <= 0:
                return self._flag
            try:
                await asyncio.wait_for(event.wait(), timeout)
            except TimeoutError:
                return self._flag
            return True
        finally:
            try:
                self._async_events.remove(event)
            except ValueError:
                pass

    def wait(self, timeout: float | None = None) -> bool:
        if self._flag:
            return True
        if timeout is not None and timeout <= 0:
            return False
        return bool(cooperative_wait(self._wait(timeout)))


class AsyncioThreadMeta(type):
    def __instancecheck__(cls, instance: object) -> bool:
        if type.__instancecheck__(cls, instance):
            return True
        if cls is not AsyncioThread:
            return False
        try:
            original_thread_type = patch_state().original_thread_type
        except RuntimeError:
            return False
        return isinstance(instance, original_thread_type)


class AsyncioThread(ThreadIdentity, metaclass=AsyncioThreadMeta):
    """`threading.Thread` adapter that runs on the Pyodide event loop."""

    def __init__(
        self,
        group: None = None,
        target: Callable[..., Any] | None = None,
        name: str | None = None,
        args: Iterable[Any] = (),
        kwargs: dict[str, Any] | None = None,
        *,
        daemon: bool | None = None,
    ) -> None:
        if group is not None:
            raise AssertionError("group argument must be None")
        self._target = target
        self._args = tuple(args)
        self._kwargs = dict(kwargs or {})
        self.name = name or new_thread_name("Thread")
        current = current_thread()
        self._started = False
        self._daemon = bool(
            current.daemon
            if daemon is None and current is not None
            else daemon
        )
        self._ident: int | None = None
        self._native_id: int | None = None
        self._finished = False
        self._done_future: asyncio.Future[None] | None = None
        self._task: asyncio.Task[None] | None = None
        self._exception: BaseException | None = None
        self._suppress_excepthook_for: tuple[type[BaseException], ...] = ()
        self._wasm_process_owner: Any | None = None

    @property
    def daemon(self) -> bool:
        return self._daemon

    @daemon.setter
    def daemon(self, daemon: bool) -> None:
        if self._started:
            raise RuntimeError("cannot set daemon status of active thread")
        self._daemon = bool(daemon)

    def start(self) -> None:
        if self._started:
            raise RuntimeError("threads can only be started once")
        try:
            self._ident = new_ident()
            self._native_id = self._ident
            self._started = True
            self._wasm_process_owner = current_process_owner()
            loop = get_event_loop()
            self._done_future = loop.create_future()
            live_threads.add(self)
            if loop.is_running():
                self._task = create_task_in_empty_wasm_context(
                    loop, self._run_in_context()
                )
                self._task.add_done_callback(lambda _task: self._finish())
                return
            run_until_complete_in_empty_wasm_context(
                loop, self._run_in_context()
            )
        except BaseException:
            self._started = False
            self._ident = None
            self._native_id = None
            live_threads.discard(self)
            raise

    async def _run_in_context(self) -> None:
        token = current_thread_var.set(self)
        try:
            result = self.run()
            if inspect.isawaitable(result):
                await result
        except asyncio.CancelledError as exc:
            self._exception = exc
            if not isinstance(exc, self._suppress_excepthook_for):
                self._call_excepthook(exc)
        except BaseException as exc:
            self._exception = exc
            if not isinstance(exc, self._suppress_excepthook_for):
                self._call_excepthook(exc)
        finally:
            current_thread_var.reset(token)
            self._finish()

    def _finish(self) -> None:
        if self._finished:
            return
        self._finished = True
        live_threads.discard(self)
        if self.ident is not None:
            clear_thread_local_state(self.ident)
        if self._done_future is not None and not self._done_future.done():
            self._done_future.set_result(None)

    def _call_excepthook(self, exc: BaseException) -> None:
        hook = cast("Callable[[Any], object]", _threading.excepthook)
        args = _threading.ExceptHookArgs(
            (type(exc), exc, exc.__traceback__, self)
        )
        try:
            hook(args)
        except Exception:
            traceback.print_exc()

    def run(self) -> Any:
        if self._target is None:
            return None
        return self._target(*self._args, **self._kwargs)

    def join(self, timeout: float | None = None) -> None:
        if not self._started:
            raise RuntimeError("cannot join thread before it is started")
        if current_identity() is self:
            raise RuntimeError("cannot join current thread")
        if self._finished or self._done_future is None:
            return
        if timeout is not None and timeout <= 0:
            return
        cooperative_wait(wait_for_future(self._done_future, timeout))

    def is_alive(self) -> bool:
        return self._started and not self._finished

    def getName(self) -> str:
        return self.name

    def setName(self, name: str) -> None:
        self.name = name

    def isDaemon(self) -> bool:
        return self.daemon

    def setDaemon(self, daemon: bool) -> None:
        self.daemon = daemon
