from __future__ import annotations

import functools
import threading
from typing import Any

from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.ops import CellOp
from marimo._runtime.context.types import (
    ContextNotInitializedError,
    get_context,
)
from marimo._runtime.threads import THREADS

_original_print = print


@functools.wraps(print)
def print_override(*args: Any, **kwargs: Any) -> None:
    """Override print to be aware of marimo threads.

    When running marimo without mo.Threads, this just forwards to the built-in
    print. When running with mo.Threads, it gets the threads cell ID and
    forwards the print message to the appropriate cell.

    This method is only necessary because the file descriptors for standard
    out and standard in are currently redirected, and sys.stdout is not
    always patched / is not aware of mo.Threads.
    """
    tid = threading.get_ident()
    if tid not in THREADS:
        _original_print(*args, **kwargs)
        return

    try:
        ctx = get_context()
    except ContextNotInitializedError:
        _original_print(*args, **kwargs)
        return

    execution_context = ctx.execution_context
    if execution_context is None:
        _original_print(*args, **kwargs)
        return

    cell_id = execution_context.cell_id

    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    msg = sep.join([str(arg) for arg in args]) + end

    CellOp(
        cell_id=cell_id,
        console=CellOutput(
            channel=CellChannel.STDOUT,
            mimetype="text/plain",
            data=msg,
        ),
    ).broadcast(ctx.stream)
