# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import time
from functools import wraps
from typing import TYPE_CHECKING, ParamSpec

if TYPE_CHECKING:
    from collections.abc import Callable

P = ParamSpec("P")


def debounce(
    wait_time: float,
) -> Callable[[Callable[P, None]], Callable[P, None]]:
    """
    Decorator to prevent a function from being called more than once every
    wait_time seconds.
    """

    def decorator(func: Callable[P, None]) -> Callable[P, None]:
        last_called: float = 0

        @wraps(func)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> None:
            nonlocal last_called
            current_time = time.time()
            if current_time - last_called >= wait_time:
                last_called = current_time
                func(*args, **kwargs)

        return wrapped

    return decorator
