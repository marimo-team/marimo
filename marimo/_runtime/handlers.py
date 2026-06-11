# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from marimo import _loggers
from marimo._messaging.notification import InterruptedNotification
from marimo._messaging.notification_utils import broadcast_notification
from marimo._runtime.context import get_context
from marimo._runtime.context.kernel_context import KernelRuntimeContext
from marimo._runtime.context.types import safe_get_context
from marimo._runtime.control_flow import MarimoInterrupt

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from collections.abc import Callable

    from marimo._runtime.runtime import Kernel


def construct_interrupt_handler() -> Callable[[int, Any], None]:
    def interrupt_handler(signum: int, frame: Any) -> None:
        """Tries to interrupt the kernel."""
        del signum
        del frame

        # Resolve the *currently installed* context, not one captured at
        # install time — embedded apps swap in their own child context.
        ctx = safe_get_context()
        if not isinstance(ctx, KernelRuntimeContext):
            return

        # `execution_context` is a plain attribute set only for the
        # duration of a single cell's body via `with_cell_id` (see
        # `kernel_context.py`); between cells, and around the scheduler's
        # own bookkeeping, it is `None`. The scheduler publication is the
        # authoritative "is a run in flight" signal that spans the whole
        # run; `execution_context` is opportunistic (only used for the
        # duckdb hook below).
        sched = ctx.active_scheduler
        exec_ctx = ctx.execution_context
        if sched is None and exec_ctx is None:
            return

        LOGGER.info("Interrupt request received")
        broadcast_notification(InterruptedNotification())

        # DuckDB connections are sometimes left in an inconsistent state
        # when interrupted by a SIGINT; route through duckdb's own API.
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
            # Async cell in flight: cancel via the loop. Raising from a
            # signal handler escapes into asyncio internals and surfaces
            # as an internal-error empty RunResult.
            sched.cancel_all()
            return

        if sched is not None:
            sched.cancel_all()
        raise MarimoInterrupt

    return interrupt_handler


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
