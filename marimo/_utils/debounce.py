# Copyright 2024 Marimo. All rights reserved.
import time
from functools import wraps
from typing import Any, Callable, TypeVar, cast

F = TypeVar("F", bound=Callable[..., None])


def debounce(wait_time: float) -> Callable[[F], F]:
    """
    Decorator to prevent a function from being called more than once every
    wait_time seconds.
    """

    def decorator(func: F) -> F:
        last_called: float = 0

        @wraps(func)
        def wrapped(*args: Any, **kwargs: Any) -> None:
            nonlocal last_called
            current_time = time.time()
            if current_time - last_called >= wait_time:
                last_called = current_time
                func(*args, **kwargs)

        return cast(F, wrapped)

    return decorator
