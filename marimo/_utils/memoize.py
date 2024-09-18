# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Callable, Tuple, TypeVar, cast

T = TypeVar("T")

sentinel = object()  # Unique sentinel object


def memoize_last_value(func: Callable[..., T]) -> Callable[..., T]:
    """
    This differs from functools.lru_cache in that is checks for
    object identity for positional arguments instead of equality
    which for functools requires the arguments to be hashable.
    """
    last_input: Tuple[Tuple[Any, ...], frozenset[Tuple[str, Any]]] = (
        (),
        frozenset(),
    )
    last_output: T = cast(T, sentinel)

    def wrapper(*args: Any, **kwargs: Any) -> T:
        nonlocal last_input, last_output

        current_input: Tuple[Tuple[Any, ...], frozenset[Tuple[str, Any]]] = (
            args,
            frozenset(kwargs.items()),
        )

        if (
            last_output is not sentinel
            and len(current_input[0]) == len(last_input[0])
            and all(
                current_input[0][i] is last_input[0][i]
                for i in range(len(current_input[0]))
                if i < len(last_input[0])
            )
            and current_input[1] == last_input[1]
        ):
            assert last_output is not sentinel
            return last_output

        result: T = func(*args, **kwargs)

        last_input = current_input
        last_output = result

        return result

    return wrapper
