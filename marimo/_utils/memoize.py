from __future__ import annotations

from typing import Any, Callable, Tuple, TypeVar, cast

T = TypeVar("T")

sentinel = object()  # Unique sentinel object


def memoize_last_value(func: Callable[..., T]) -> Callable[..., T]:
    last_input: Tuple[Tuple[Any, ...], frozenset[Tuple[str, Any]]] | None = (
        None
    )
    last_output: T = cast(T, sentinel)

    def wrapper(*args: Any, **kwargs: Any) -> T:
        nonlocal last_input, last_output

        current_input: Tuple[Tuple[Any, ...], frozenset[Tuple[str, Any]]] = (
            args,
            frozenset(kwargs.items()),
        )

        if current_input is last_input:
            assert last_output is not sentinel
            return last_output

        result: T = func(*args, **kwargs)

        last_input = current_input
        last_output = result

        return result

    return wrapper
