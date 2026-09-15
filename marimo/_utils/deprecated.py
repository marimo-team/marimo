# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import functools
import warnings
from typing import TYPE_CHECKING, ParamSpec, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

P = ParamSpec("P")
R = TypeVar("R")


def deprecated(reason: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """A decorator that emits a deprecation warning."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # stacklevel=2 shows the line number in the call site
            warnings.warn(
                message=reason,
                category=DeprecationWarning,
                stacklevel=2,
            )
            return func(*args, **kwargs)

        return wrapper

    return decorator
