# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import functools
import time
from typing import TYPE_CHECKING, ParamSpec, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

P = ParamSpec("P")
T = TypeVar("T")


def timer(func: Callable[P, T]) -> Callable[P, T]:
    """
    A decorator that measures and prints the execution time of a function.

    This should only be used for manual debugging.
    """

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        execution_time = end_time - start_time
        print(f"{func.__name__} took {execution_time:.4f} seconds to execute")  # noqa: T201
        return result

    return wrapper
