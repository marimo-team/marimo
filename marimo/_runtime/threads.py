# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import threading
from typing import Any

from marimo._messaging.streams import ThreadSafeStream
from marimo._runtime.context.kernel_context import KernelRuntimeContext
from marimo._runtime.context.script_context import ScriptRuntimeContext
from marimo._runtime.context.types import (
    ExecutionContext,
    RuntimeContext,
    get_context,
    initialize_context,
    runtime_context_installed,
    teardown_context,
)

# Set of thread ids for running mo.Threads
THREADS = set()


class Thread(threading.Thread):
    """A Thread subclass that is aware of marimo internals.

    `mo.Thread` has the same API as threading.Thread,
    but `mo.Thread`s are able to communicate with the marimo
    frontend, whereas `threading.Thread` can't.

    Threads can append to a cell's output using `mo.output.append`, or to the
    console output area using `print`. The corresponding outputs will be
    forwarded to the frontend.

    Writing directly to sys.stdout or sys.stderr, or to file descriptors 1 and
    2, is not yet supported.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self._marimo_ctx: RuntimeContext | None = None
        self._stopped = False

        if not runtime_context_installed():
            return

        ctx = get_context()
        if isinstance(ctx, KernelRuntimeContext):
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

    def run(self) -> None:
        if self._marimo_ctx is not None:
            try:
                initialize_context(self._marimo_ctx)
            except RuntimeError:
                pass
        if isinstance(self._marimo_ctx, KernelRuntimeContext):
            self._marimo_ctx.execution_context = ExecutionContext(
                cell_id=self._marimo_ctx.stream.cell_id,  # type: ignore
                setting_element_value=False,
            )
        thread_id = threading.get_ident()
        THREADS.add(thread_id)
        try:
            super().run()
        except Exception as e:
            if not self._stopped:
                raise e
        finally:
            THREADS.remove(thread_id)
            teardown_context()

    def join(self, timeout: float | None = None) -> None:
        self._stopped = True
        super().join(timeout)

    def __del__(self) -> None:
        # If the thread is still alive, we need to remove it from the set of
        # threads
        if threading.get_ident() in THREADS:
            THREADS.remove(threading.get_ident())

        try:
            self._terminate()  # type: ignore
        except Exception:
            pass
