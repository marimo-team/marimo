# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from marimo import _loggers
from marimo._runtime.context import get_context
from marimo._runtime.context.kernel_context import KernelRuntimeContext
from marimo._runtime.context.types import safe_get_context
from marimo._runtime.control_flow import MarimoInterrupt
from marimo._utils.signals import SigintHandler

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from collections.abc import Callable

    from marimo._runtime.runtime import Kernel


def construct_interrupt_handler() -> SigintHandler:
    def interrupt_handler(signum: int, frame: Any) -> None:
        """Interrupt the running cell.

        Python can run this handler nested inside itself when two
        SIGINTs arrive close together, so it does not write to the kernel
        stream. It does not send `InterruptedNotification`. The interrupted
        run reports the interruption after its running cell stops.
        """
        del signum
        del frame

        # Read the context that is installed now, not one captured when the
        # handler was installed, because an embedded app swaps in its own
        # child context.
        ctx = safe_get_context()
        if not isinstance(ctx, KernelRuntimeContext):
            return

        # `execution_context` is set only while one cell's body executes, so
        # it is `None` between cells and during the scheduler's own
        # bookkeeping. The active scheduler is set for the whole run, and it
        # indicates that a run is executing. `execution_context` is used
        # only for the duckdb interrupt below.
        sched = ctx.active_scheduler
        exec_ctx = ctx.execution_context
        if sched is None and exec_ctx is None:
            return

        # A SIGINT can leave a DuckDB connection in an inconsistent state,
        # so interrupt it through duckdb's own API.
        if exec_ctx is not None and exec_ctx.duckdb_connection is not None:
            try:
                exec_ctx.duckdb_connection.interrupt()
            except Exception as e:
                LOGGER.warning(
                    "Failed to interrupt running duckdb connection. This "
                    "may be a bug in duckdb or marimo. %s",
                    e,
                )

        if sched is not None and sched.has_active_tasks():
            interrupt = sched.interrupt_current_task()
            if interrupt is not None:
                raise interrupt
            # The signal arrived somewhere else in the async run, such as a
            # lifecycle hook, the loop itself, or a task left over from a
            # cell that already ended. A raise there escapes into asyncio
            # internals or skips lifecycle teardown, so cancel through the
            # loop instead.
            sched.cancel_all()
            return

        if sched is not None:
            sched.cancel_all()
        raise MarimoInterrupt

    return SigintHandler(interrupt_handler)


def construct_sigterm_handler(kernel: Kernel) -> Callable[[int, Any], None]:
    del kernel

    @dataclass
    class Bit:
        value: bool = False

    shutting_down = Bit()

    def sigterm_handler(signum: int, frame: Any) -> None:
        """Cleans up the kernel and exits."""
        del signum
        del frame

        if shutting_down.value:
            # give previous SIGTERM a chance to quit ... makes
            # sure this method is reentrant
            return
        shutting_down.value = True

        get_context().virtual_file_registry.shutdown()
        # Force this process to exit.
        #
        # We use os._exit() instead of sys.exit() because we don't want the
        # child process to also run atexit handlers, which may result in
        # undefined behavior. Using sys.exit() on Linux sometimes causes
        # the parent process to hang on shutdown, leading to orphaned
        # processes and port.
        #
        # TODO(akshayka): The Python docs say this method is appropriate
        # for processes created with fork(), but they don't say anything
        # about processes made with spawn. macOS and Windows default to
        # spawn. If we have further issues with clean exits, we might
        # investigate here.
        #
        # https://docs.python.org/3/library/os.html#os._exit
        # https://www.unixguide.net/unix/programming/1.1.3.shtml
        os._exit(0)

    return sigterm_handler
