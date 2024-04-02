# Copyright 2024 Marimo. All rights reserved.
import functools
import warnings
from typing import Any, Callable


def deprecated(reason: str) -> Callable[[Any], Any]:
    """A decorator that emits a deprecation warning."""

    def decorator(func: Callable[[Any], Any]) -> Callable[[Any], Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Callable[[Any], Any]:
            # stacklevel=2 shows the line number in the call site
            warnings.warn(
                message=reason,
                category=DeprecationWarning,
                stacklevel=2,
            )
            return func(*args, **kwargs)  # type: ignore[no-any-return]

        return wrapper

    return decorator
