# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._output.rich_help import mddoc
from marimo._runtime.context import ContextNotInitializedError, get_context
from marimo._runtime.context.kernel_context import KernelRuntimeContext
from marimo._runtime.context.script_context import ScriptRuntimeContext


@mddoc
def running_in_notebook() -> bool:
    """Returns True if running in a marimo notebook, False otherwise"""

    try:
        ctx = get_context()
    except ContextNotInitializedError:
        return False
    else:
        return isinstance(ctx, KernelRuntimeContext)


def get_mode() -> str:
    """Returns the current mode of the marimo app.

    Returns:
        str: One of 'edit', 'run', 'script', or 'unknown'
    """
    try:
        context = get_context()
        if isinstance(context, KernelRuntimeContext):
            return context.session_mode
        if isinstance(context, ScriptRuntimeContext):
            return "script"
    except ContextNotInitializedError:
        pass
    return "unknown"
