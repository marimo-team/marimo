# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import threading
from typing import TYPE_CHECKING, Any

from marimo._messaging.streams import ThreadSafeStream
from marimo._output.rich_help import mddoc
from marimo._runtime.cell_lifecycle_item import CellLifecycleItem
from marimo._runtime.cell_output_list import CellOutputList
from marimo._runtime.context.kernel_context import KernelRuntimeContext
from marimo._runtime.context.script_context import ScriptRuntimeContext
from marimo._runtime.context.types import (
    ExecutionContext,
    RuntimeContext,
    get_context,
    initialize_context,
    runtime_context_installed,
    safe_get_context,
    teardown_context,
)
from marimo._utils.platform import is_pyodide

if TYPE_CHECKING:
    from collections.abc import Awaitable

# Set of thread ids for running mo.Threads
THREADS: set[int] = set()


@mddoc
class Thread(threading.Thread):
    """A Thread subclass that can communicate with the frontend.

    `mo.Thread` has the same API as threading.Thread,
    but `mo.Thread`s are able to communicate with the marimo
    frontend, whereas `threading.Thread` can't.

    Threads can append to a cell's output using `mo.output.append`, or to the
    console output area using `print`. The corresponding outputs will be
    forwarded to the frontend.

    In Pyodide, `mo.Thread` keeps the `threading.Thread` call shape but runs on
    marimo's WASM threading patch. It has a synthetic thread identity, does not
    create an OS thread, and waits such as `join()` progress through Pyodide
    JSPI.

    Writing directly to sys.stdout or sys.stderr, or to file descriptors 1 and
    2, is not yet supported.

    **Thread lifecycle.** When the cell that spawned this thread is invalidated
    (re-run, deleted, interrupted, or otherwise errored), this thread's
    `should_exit` property will evaluate to `True`, at which point it
    is the developer's responsibility to clean up their thread.

    Examples:
        ```python
        def target():
            import time
            import marimo as mo

            thread = mo.current_thread()
            while not thread.should_exit:
                time.sleep(1)
                print("hello")
        ```

        ```python
        import marimo as mo

        mo.Thread(target=target).start()
        ```
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self._marimo_ctx: RuntimeContext | None = None
        exit_event = threading.Event()
        self._exit_event = exit_event

        if not runtime_context_installed():
            return

        class ThreadLifecycle(CellLifecycleItem):
            def create(self, context: RuntimeContext) -> None:
                del context

            def dispose(self, context: RuntimeContext, deletion: bool) -> bool:
                del context
                del deletion
                exit_event.set()
                return True

        ctx = get_context()
        ctx.cell_lifecycle_registry.add(ThreadLifecycle())

        if isinstance(ctx, KernelRuntimeContext):
            # Patch `print` lazily, only once a mo.Thread exists, to route
            # thread output to the spawning cell. Thread-free notebooks keep
            # the real builtin that libraries like numba require. See #9765.
            from marimo._messaging.print_override import print_override

            ctx.globals.setdefault("print", print_override)

            self._marimo_ctx = KernelRuntimeContext(**ctx.__dict__)
            # standard IO is not yet threadsafe
            self._marimo_ctx.stdout = None
            self._marimo_ctx.stderr = None
            if isinstance(ctx.stream, ThreadSafeStream):
                self._marimo_ctx.stream = type(ctx.stream)(
                    pipe=ctx.stream.pipe,
                    # TODO(akshayka): stdin is not threadsafe
                    input_queue=ctx.stream.input_queue,
                    cell_id=ctx.stream.cell_id,
                    redirect_console=False,
                )
            else:
                raise RuntimeError(
                    "Unsupported stream type " + str(type(ctx.stream))
                )
        elif isinstance(self._marimo_ctx, ScriptRuntimeContext):
            # Standard streams are not rerouted when running as a script, so no
            # need to set to None
            self._marimo_ctx = ScriptRuntimeContext(**ctx.__dict__)
            if isinstance(ctx.stream, ThreadSafeStream):
                self._marimo_ctx.stream = ThreadSafeStream(
                    pipe=ctx.stream.pipe,
                    input_queue=ctx.stream.input_queue,
                    cell_id=ctx.stream.cell_id,
                    redirect_console=False,
                )
            else:
                raise RuntimeError(
                    "Unsupported stream type " + str(type(ctx.stream))
                )

    @property
    def should_exit(self) -> bool:
        """Whether this thread should exit.

        Returns `True` when the cell that spawned this thread has been invalidated;
        for example, if the cell:

        - was re-run
        - was deleted
        - was interrupted

        then this property evaluates to True.

        It is the developer's responsibility to clean up and finish their
        thread when this flag is set. Retrieve the current `mo.Thread` with

        ```python
        import marimo as mo

        mo.current_thread()
        ```
        """
        return self._exit_event.is_set()

    async def _finish_awaitable_run(
        self,
        awaitable: Awaitable[Any],
        *,
        context_initialized: bool,
        thread_id: int,
    ) -> Any:
        try:
            return await awaitable
        finally:
            THREADS.discard(thread_id)
            if context_initialized:
                teardown_context()

    def run(self) -> Any:
        context_initialized = False
        defer_cleanup = False
        managed_thread = threading.current_thread() is self
        if managed_thread and self._marimo_ctx is not None:
            try:
                initialize_context(self._marimo_ctx)
                context_initialized = True
            except RuntimeError as exc:
                if is_pyodide() and safe_get_context() is not self._marimo_ctx:
                    raise RuntimeError(
                        "mo.Thread could not install its copied runtime "
                        "context under the WASM thread identity."
                    ) from exc

        output = CellOutputList()
        if self._marimo_ctx is not None:
            if (exec_ctx := self._marimo_ctx.execution_context) is not None:
                # Share the parent's CellOutputList so appends from threads
                # are visible to the main execution context.
                output = exec_ctx.output

        if isinstance(self._marimo_ctx, KernelRuntimeContext):
            self._marimo_ctx.execution_context = ExecutionContext(
                cell_id=self._marimo_ctx.stream.cell_id,  # type: ignore
                setting_element_value=False,
                output=output,
            )
        thread_id = threading.get_ident()
        try:
            if managed_thread:
                THREADS.add(thread_id)
            result = super().run()
            if is_pyodide() and managed_thread and inspect.isawaitable(result):
                defer_cleanup = True
                return self._finish_awaitable_run(
                    result,
                    context_initialized=context_initialized,
                    thread_id=thread_id,
                )
            return result
        finally:
            if not defer_cleanup:
                if managed_thread:
                    THREADS.discard(thread_id)
                if context_initialized:
                    teardown_context()


def current_thread() -> Thread:
    """Return the `marimo.Thread` object for the caller's thread of control.

    Returns:
        The current `marimo.Thread` object.

    Raises:
        RuntimeError: If the current thread of control is not a `marimo.Thread`.
    """
    thread = threading.current_thread()
    if not isinstance(thread, Thread):
        raise RuntimeError(
            "mo.current_thread() must be called from a "
            "thread created with mo.Thread."
        )
    return thread


def is_marimo_thread() -> bool:
    try:
        current_thread()
        return True
    except RuntimeError:
        return False
