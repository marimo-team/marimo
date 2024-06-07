# Copyright 2024 Marimo. All rights reserved.

from __future__ import annotations

import inspect
import weakref
from copy import copy
from typing import (
    Any,
    Callable,
    Generic,
    Type,
    TypeVar,
    Union,
    cast,
)

T = TypeVar("T")

Ref = Union[weakref.ReferenceType[T], Callable[[], T]]


CellId_t = str


class CloneError(Exception):
    pass


class RoError(Exception):
    pass


class _Copy(Generic[T]):
    __ref__: Ref[T]


class ZeroCopy(_Copy[T]):
    pass


class ShallowCopy(_Copy[T]):
    pass


def ro_fail() -> None:
    raise RoError(
        "Weakly copied objects are directly read only."
        " Modification is not encouraged, but is"
        " possible by utilizing the __ref__() attribute."
    )


def shadow_wrap(ref_cls: Type[_Copy[T]], base: T) -> T:
    slots = set(dir(base) + ["__ref__"]) - set(
        [
            "__new__",
            "__setattr__",
            "__setitem__",
            "__doc__",
            "__class__",
            "__dict__",
            "__module__",
            "__slots__",
            "__dir__",
            "__init__",
            "__weakref__",
        ]
    )
    _fixed = [False]

    class ro(_Copy[T]):
        __doc__ = base.__class__.__doc__
        __slots__ = list(slots)
        __base = base
        __class__ = type(
            base.__class__.__name__, (base.__class__, ref_cls), {}
        )

        def __init__(self) -> None:
            pass

        def __setattr__(self, name: str, value: Any) -> None:
            if _fixed[0]:
                ro_fail()
            super.__setattr__(self, name, value)

        def __setitem__(self, name: str, value: Any) -> None:
            ro_fail()

        def __new__(cls) -> ro:
            instance = ref_cls.__new__(cls)
            for n, m in inspect.getmembers(base):
                if n != "__weakref__":
                    setattr(instance, n, m)
            # Not a weak ref, but reasonable fallback
            ref: Ref[T] = lambda: base  # noqa: E731
            if hasattr(base, "__weakref__"):
                maybe_ref = weakref.ref(base)
                if maybe_ref is not None:
                    ref = maybe_ref
            instance.__ref__ = ref
            _fixed[0] = True
            return instance

    return cast(T, ro())


def zero_copy(base: T) -> T:
    if isinstance(base, ShallowCopy):
        return cast(T, shadow_wrap(ZeroCopy, base.__ref__()))
    if isinstance(base, ZeroCopy):
        return cast(T, base)
    return cast(T, shadow_wrap(ZeroCopy, base))


def shallow_copy(base: T) -> T:
    if isinstance(base, (ShallowCopy, ZeroCopy)):
        return cast(T, shadow_wrap(ShallowCopy, copy(base.__ref__())))
    return cast(T, shadow_wrap(ShallowCopy, base))
