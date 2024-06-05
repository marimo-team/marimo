# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import functools
import sys
from typing import Callable, TypeVar

from marimo._output.rich_help import mddoc
from marimo._runtime.context import ContextNotInitializedError, get_context
from marimo._runtime.context.kernel_context import KernelRuntimeContext

if sys.version_info < (3, 10):
    from typing_extensions import ParamSpec
else:
    from typing import ParamSpec

T = TypeVar("T")
P = ParamSpec("P")


@mddoc
def running_in_notebook() -> bool:
    """Returns True if running in a marimo notebook, False otherwise"""

    try:
        ctx = get_context()
    except ContextNotInitializedError:
        return False
    else:
        return isinstance(ctx, KernelRuntimeContext)


def lock_globals(f: Callable[P, T]) -> Callable[P, T]:
    @functools.wraps(f)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            ctx = get_context()
        except ContextNotInitializedError:
            return f(*args, **kwargs)

        if not isinstance(ctx, KernelRuntimeContext):
            return f(*args, **kwargs)

        with ctx.globals_lock:
            return f(*args, **kwargs)

    return wrapper
