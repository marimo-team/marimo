# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar, cast

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T")

sentinel = object()  # Unique sentinel object


def memoize_last_value(func: Callable[..., T]) -> Callable[..., T]:
    """
    This differs from functools.lru_cache in that is checks for
    object identity for positional arguments instead of equality
    which for functools requires the arguments to be hashable.
    """
    last_args: tuple[Any, ...] = cast(tuple[Any, ...], sentinel)
    last_kwargs: dict[str, Any] = cast(dict[str, Any], sentinel)
    last_output: T = cast(T, sentinel)

    def wrapper(*args: Any, **kwargs: Any) -> T:
        nonlocal last_args, last_kwargs, last_output

        if last_output is not sentinel:
            # Check positional arguments by identity
            if len(args) == len(last_args):
                for i in range(len(args)):
                    if args[i] is not last_args[i]:
                        break
                else:
                    # Check keyword arguments by equality
                    if kwargs == last_kwargs:
                        return last_output

        result: T = func(*args, **kwargs)

        last_args = args
        last_kwargs = kwargs
        last_output = result

        return result

    return wrapper
