# Copyright 2026 Marimo. All rights reserved.
"""Same-interpreter `multiprocessing.Process` adapter for Pyodide."""

from __future__ import annotations

import asyncio
import contextvars
import inspect
from typing import TYPE_CHECKING, Any

from marimo._runtime._wasm._concurrency import _state
from marimo._runtime._wasm._concurrency._state import (
    live_processes,
    new_thread_name,
)
from marimo._runtime._wasm._concurrency._threading import AsyncioThread
from marimo._runtime._wasm._concurrency._wait import (
    UnsupportedWasmConcurrencyError,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable


class AsyncProcess:
    """Run a process-shaped target in the current Pyodide interpreter."""

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
        self._parent_process: AsyncProcess | MainProcess = (
            _CURRENT_PROCESS.get() or MAIN_PROCESS
        )
        self._thread = AsyncioThread(
            target=self._run_target,
            name=name or new_thread_name("Process"),
            daemon=(self._parent_process.daemon if daemon is None else daemon),
        )
        self.exitcode: int | None = None
        self.pid: int | None = None
        self._started = False
        self._closed = False
        self._kill_requested = False

    async def _finish_target(
        self,
        result: Any,
        token: contextvars.Token[Any],
        exception: BaseException | None = None,
    ) -> Any:
        try:
            try:
                if exception is not None:
                    raise exception
                if inspect.isawaitable(result):
                    result = await result
                return result
            finally:
                await self._wait_for_owned_work()
        finally:
            _CURRENT_PROCESS.reset(token)

    def _run_target(self) -> Any:
        if self.pid is None:
            self.pid = self._thread.ident
        token = _CURRENT_PROCESS.set(self)
        try:
            result = self.run()
        except BaseException as exc:
            return self._finish_target(None, token, exc)
        return self._finish_target(result, token)

    def run(self) -> Any:
        if self._target is None:
            return None
        return self._target(*self._args, **self._kwargs)

    @property
    def name(self) -> str:
        return self._thread.name

    @name.setter
    def name(self, name: str) -> None:
        self._thread.name = name

    @property
    def ident(self) -> int | None:
        return self.pid

    @property
    def daemon(self) -> bool:
        return self._thread.daemon

    @daemon.setter
    def daemon(self, daemon: bool) -> None:
        self._thread.daemon = daemon

    @property
    def authkey(self) -> bytes:
        raise UnsupportedWasmConcurrencyError(
            "multiprocessing.Process.authkey is not supported in Pyodide"
        )

    @property
    def sentinel(self) -> int:
        raise UnsupportedWasmConcurrencyError(
            "multiprocessing.Process.sentinel is not supported in Pyodide"
        )

    def start(self) -> None:
        self._check_closed()
        if self._started:
            raise RuntimeError("process can only be started once")
        current_process = _CURRENT_PROCESS.get() or MAIN_PROCESS
        if current_process is not self._parent_process:
            raise AssertionError(
                "can only start a process object created by current process"
            )
        if current_process.daemon:
            raise AssertionError(
                "daemonic processes are not allowed to have children"
            )
        self._started = True
        try:
            self._thread.start()
        except BaseException:
            self._started = False
            self.pid = None
            self.exitcode = None
            raise
        self.pid = self._thread.ident
        live_processes.add(self)
        if self._thread._done_future is not None:
            self._thread._done_future.add_done_callback(
                lambda _future: self._mark_finished()
            )
        self._mark_finished()

    def join(self, timeout: float | None = None) -> None:
        self._check_closed()
        self._thread.join(timeout)
        self._mark_finished()

    def _mark_finished(self) -> None:
        if not self._started:
            return
        if not self._thread.is_alive():
            if self._kill_requested:
                self._cancel_owned_work()
            if self._has_process_owned_work():
                return
            if self.exitcode is None:
                if self._kill_requested:
                    self.exitcode = -1
                else:
                    self.exitcode = _process_exitcode(self._thread._exception)
            live_processes.discard(self)

    def is_alive(self) -> bool:
        self._check_closed()
        if not self._started:
            return False
        if self.exitcode is not None:
            return False
        if self._thread.is_alive():
            return True
        self._mark_finished()
        return self.exitcode is None and self._has_process_owned_work()

    def close(self) -> None:
        if self.is_alive():
            raise ValueError("cannot close a running process")
        self._closed = True

    def terminate(self) -> None:
        self.kill()

    def kill(self) -> None:
        self._check_closed()
        if not self._started:
            raise ValueError("process has not started")
        if self.exitcode is not None or not self.is_alive():
            return
        self._kill_requested = True
        self._thread._suppress_excepthook_for = (asyncio.CancelledError,)
        task = self._thread._task
        if task is not None and not task.done():
            task.cancel()
        self._cancel_owned_work()
        self._mark_finished()

    def _check_closed(self) -> None:
        if self._closed:
            raise ValueError("process object is closed")

    async def _wait_for_owned_work(self) -> None:
        while self._has_process_owned_work():
            await _yield_to_process_work()
        _state.cancel_process_tasks(self)
        while _state.has_process_tasks(self):
            await _yield_to_process_work()
        self._shutdown_owned_executors()
        self._cancel_owned_daemon_threads()
        self._kill_owned_daemon_processes()
        while (
            self._has_process_owned_daemon_threads()
            or self._has_process_owned_daemon_processes()
        ):
            await _yield_to_process_work()
        self._shutdown_owned_executors()

    def _has_process_owned_work(self) -> bool:
        for thread in list(_state.live_threads):
            if (
                getattr(thread, "_wasm_process_owner", None) is self
                and thread.is_alive()
                and not thread.daemon
            ):
                return True
        for executor in list(_state.live_executors):
            has_pending_work = getattr(
                executor, "has_pending_wasm_work_for_owner", None
            )
            if not callable(has_pending_work):
                continue
            if has_pending_work(self):
                return True
        for process in list(live_processes):
            if process is self or process._parent_process is not self:
                continue
            if process.daemon:
                continue
            if process.is_alive():
                return True
            live_processes.discard(process)
        return False

    def _has_process_owned_daemon_threads(self) -> bool:
        return any(
            getattr(thread, "_wasm_process_owner", None) is self
            and thread.is_alive()
            and thread.daemon
            for thread in list(_state.live_threads)
        )

    def _has_process_owned_daemon_processes(self) -> bool:
        for process in list(live_processes):
            if process is self or process._parent_process is not self:
                continue
            if not process.daemon:
                continue
            if process.is_alive():
                return True
            live_processes.discard(process)
        return False

    def _cancel_owned_daemon_threads(self) -> None:
        for thread in list(_state.live_threads):
            if not isinstance(thread, AsyncioThread):
                continue
            if (
                getattr(thread, "_wasm_process_owner", None) is self
                and thread.is_alive()
                and thread.daemon
            ):
                thread._suppress_excepthook_for = (asyncio.CancelledError,)
                if thread._task is not None and not thread._task.done():
                    thread._task.cancel()

    def _kill_owned_daemon_processes(self) -> None:
        for process in list(live_processes):
            if (
                process is not self
                and process._parent_process is self
                and process.daemon
                and process.is_alive()
            ):
                process.kill()

    def _shutdown_owned_executors(self) -> None:
        for executor in list(_state.live_executors):
            shutdown_executor = getattr(
                executor, "shutdown_wasm_executor_for_owner", None
            )
            if callable(shutdown_executor):
                shutdown_executor(self)

    def _cancel_owned_work(self) -> None:
        for thread in list(_state.live_threads):
            if (
                not isinstance(thread, AsyncioThread)
                or getattr(thread, "_wasm_process_owner", None) is not self
            ):
                continue
            thread._suppress_excepthook_for = (asyncio.CancelledError,)
            if thread._task is not None and not thread._task.done():
                thread._task.cancel()
        for executor in list(_state.live_executors):
            cancel_work = getattr(executor, "cancel_wasm_work_for_owner", None)
            if callable(cancel_work):
                cancel_work(self)
        _state.cancel_process_tasks(self)
        self._shutdown_owned_executors()
        for process in list(live_processes):
            if process is not self and process._parent_process is self:
                process.kill()


class MainProcess:
    name = "MainProcess"
    pid = 1
    ident = 1
    daemon = False
    exitcode = None
    authkey = b""

    def is_alive(self) -> bool:
        return True


MAIN_PROCESS = MainProcess()
_CURRENT_PROCESS: contextvars.ContextVar[AsyncProcess | None] = (
    contextvars.ContextVar("marimo_wasm_current_process", default=None)
)
_state.register_inherited_context_var(_CURRENT_PROCESS)
_state.set_process_owner_getter(_CURRENT_PROCESS.get)


def _process_exitcode(exception: BaseException | None) -> int:
    if exception is None:
        return 0
    if isinstance(exception, SystemExit):
        if exception.code is None:
            return 0
        if isinstance(exception.code, int):
            return exception.code
    return 1


def current_process() -> AsyncProcess | MainProcess:
    return _CURRENT_PROCESS.get() or MAIN_PROCESS


def parent_process() -> AsyncProcess | MainProcess | None:
    current_process = _CURRENT_PROCESS.get()
    if current_process is not None:
        return current_process._parent_process
    return None


def active_children() -> list[AsyncProcess]:
    current = current_process()
    children: list[AsyncProcess] = []
    for process in list(live_processes):
        if not process.is_alive():
            live_processes.discard(process)
            continue
        if process is not current and process._parent_process is current:
            children.append(process)
    return children


async def _yield_to_process_work() -> None:
    await asyncio.sleep(0)
