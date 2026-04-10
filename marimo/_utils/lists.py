# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from collections.abc import Iterable
from typing import TypeVar

T = TypeVar("T")


def first(iterable: Iterable[T] | T) -> T:
    if isinstance(iterable, Iterable):
        return next(iter(iterable))  # type: ignore[no-any-return]
    else:
        return iterable


def as_list(value: T | None | list[T]) -> list[T]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]  # type: ignore[no-any-return]
