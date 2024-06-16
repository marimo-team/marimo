# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import sys
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
if sys.version_info < (3, 9):
    # Future does not seem to work for this in CI.
    Ref = Union["weakref.ReferenceType[T]", Callable[[], T]]
else:
    Ref = Union[weakref.ReferenceType[T], Callable[[], T]]


class CloneError(Exception):
    """Thrown when strict execution fail to deep copy or clone."""


class ReadOnlyError(Exception):
    """Thrown when attempting to modify a read-only object."""


class _Copy(Generic[T]):
    """Base wrapper class for strict execution."""

    __ref__: Ref[T]


class ZeroCopy(_Copy[T]):
    """Wrapper class for strict execution (stops deepcopy)."""


class ShallowCopy(_Copy[T]):
    """Wrapper class for strict execution (does copy over deepcopy)."""


def _ro_fail() -> None:
    raise ReadOnlyError(
        "Weakly copied objects are directly read only."
        " Modification is not encouraged, but is"
        " possible by utilizing the marimo.unwrap_copy() function."
    )


def shadow_wrap(ref_cls: Type[_Copy[T]], base: T) -> T:
    """
    Wraps the base object by copying all attributes over to slots, and the then
    restricting write access to the object attributes / items directly. This is
    very agrressive and makes the wrapped object difficult to tell apart from
    the base object without inspect.

    However, there are some limitations, e.g. some operations of the wrapped
    object may not be associative if they are not defined for both the left
    and right operations. For instance:

    >>> a = shadow_wrap(ZeroCopy, [1, 2, 3])
    >>> b = [4, 5, 6]
    >>> a + b
    [1, 2, 3, 4, 5, 6]

    will work, but:

    >>> b + a

    will not work, as the `__add__` method is not defined for custom objects in
    the right operand. However, The original wrapped object can still be
    accessed with unwrap_copy(). The internal class is named as a hint for this
    reason, although most times this will be invisible.
    """

    # Apply attributes as slots reflection, but remove the attributes that are
    # set explicitly by the wrapper class (or not allowed like __dict__).
    slots = set(dir(base)) - set(
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
            "__ref__",
        ]
    )
    # pointer off the class to lock attributes / items.
    _fixed = [False]

    # Not seeing a non-verbose work around for mypy, as this needs to inherit
    # from the provided class and not some generic for this to work.
    class ReadOnly_try_marimo_unwrap_copy(ref_cls):  # type: ignore
        __doc__ = base.__class__.__doc__
        __slots__ = list(slots)
        # ensure reference for gc
        __base = base
        __class__ = type(
            base.__class__.__name__, (base.__class__, ref_cls), {}
        )

        def __init__(self) -> None:
            """No-op constructor to prevent parent constructor from running."""

        def __setattr__(self, name: str, value: Any) -> None:
            # Has to be read only as wouldn't actually mutate the underlying
            # object. Easier to defer and require and an unwrap then trying to
            # manage it,
            if _fixed[0]:
                _ro_fail()
            super.__setattr__(self, name, value)

        def __setitem__(self, name: str, value: Any) -> None:
            _ro_fail()

        def __new__(cls) -> ReadOnly_try_marimo_unwrap_copy:
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

    return cast(T, ReadOnly_try_marimo_unwrap_copy())


def unwrap_copy(base: T) -> T:
    """
    Given a ZeroCopy or ShallowCopy object, returns the original object.
    """
    for cls in [ZeroCopy, ShallowCopy]:
        if isinstance(base, cls):
            # It's pretty hidden, but it's there
            ref: Ref[T] = super(cls, base).__dict__["__ref__"]  # type: ignore
            return cast(T, ref())
    return base


def zero_copy(base: T) -> T:
    """
    Wraps object in a ZeroCopy wrapper to mark the object for no copying /
    cloning when running in strict execution mode.
    """
    if isinstance(base, ShallowCopy):
        return cast(T, shadow_wrap(ZeroCopy, unwrap_copy(base)))
    if isinstance(base, ZeroCopy):
        return cast(T, base)
    return cast(T, shadow_wrap(ZeroCopy, base))


def shallow_copy(base: T) -> T:
    """
    Wraps object in a ShallowCopy wrapper to mark the object for "copy" over
    "deepcopy" when running in strict execution mode.
    """
    if isinstance(base, _Copy):
        return cast(T, shadow_wrap(ShallowCopy, copy(unwrap_copy(base))))
    return cast(T, shadow_wrap(ShallowCopy, copy(base)))
