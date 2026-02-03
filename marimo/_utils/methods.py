# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import types
from typing import Any, Callable, cast


def is_callable_method(obj: Any, attr: str) -> bool:
    """Check if an attribute is callable on an object."""
    if not hasattr(obj, attr):
        return False

    method = getattr(obj, attr)
    if inspect.isclass(obj) and not isinstance(method, (types.MethodType)):
        return False
    return callable(method)


def getcallable(obj: object, name: str) -> Callable[..., Any] | None:
    """Get a callable attribute from an object, or None if not callable.

    This safely handles objects that implement __getattr__ and return
    non-callable values for any attribute name.
    """
    if (attr := getattr(obj, name, None)) is not None:
        if callable(attr):
            return cast(Callable[..., Any], attr)
    return None
