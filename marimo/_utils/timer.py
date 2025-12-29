# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import functools
import time
from typing import Any, Callable


def timer(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    A decorator that measures and prints the execution time of a function.

    This should only be used for manual debugging.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        execution_time = end_time - start_time
        print(f"{func.__name__} took {execution_time:.4f} seconds to execute")  # noqa: T201
        return result

    return wrapper
