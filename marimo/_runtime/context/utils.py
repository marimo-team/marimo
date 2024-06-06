# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._output.rich_help import mddoc
from marimo._runtime.context import ContextNotInitializedError, get_context
from marimo._runtime.context.kernel_context import KernelRuntimeContext


@mddoc
def running_in_notebook() -> bool:
    """Returns True if running in a marimo notebook, False otherwise"""

    try:
        ctx = get_context()
    except ContextNotInitializedError:
        return False
    else:
        return isinstance(ctx, KernelRuntimeContext)
