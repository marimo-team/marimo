from __future__ import annotations

from typing import Iterable, TypeVar, Union

T = TypeVar("T")


def first(iterable: Union[Iterable[T], T]) -> T:
    if isinstance(iterable, Iterable):
        return next(iter(iterable))  # type: ignore[no-any-return]
    else:
        return iterable
