# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import weakref
from functools import wraps
from typing import TYPE_CHECKING, ParamSpec, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

P = ParamSpec("P")
T = TypeVar("T")


def once(func: Callable[P, T]) -> Callable[P, T | None]:
    """
    Decorator to ensure a function is called only once.
    For methods, this is once per instance.
    For regular functions, this is once globally.
    """
    # For regular functions (no 'self' argument)
    called: bool = False
    # For methods (with 'self' argument) - track per instance
    instance_called: weakref.WeakKeyDictionary[object, bool] = (
        weakref.WeakKeyDictionary()
    )

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T | None:
        nonlocal called

        # Check if this is a method call (has self as first argument)
        if args and hasattr(args[0], "__dict__"):
            # This is likely a method call with 'self'
            instance = args[0]
            if instance not in instance_called:
                instance_called[instance] = False

            if not instance_called[instance]:
                instance_called[instance] = True
                return func(*args, **kwargs)
        else:
            # This is a regular function call
            if not called:
                called = True
                return func(*args, **kwargs)

        return None

    return wrapper
