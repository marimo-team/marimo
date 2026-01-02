# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import weakref
from functools import wraps
from typing import Any, Callable, TypeVar, cast

F = TypeVar("F", bound=Callable[..., Any])


def once(func: F) -> F:
    """
    Decorator to ensure a function is called only once.
    For methods, this is once per instance.
    For regular functions, this is once globally.
    """
    # For regular functions (no 'self' argument)
    called: bool = False
    # For methods (with 'self' argument) - track per instance
    instance_called: weakref.WeakKeyDictionary[Any, bool] = (
        weakref.WeakKeyDictionary()
    )

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
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

    return cast(F, wrapper)
