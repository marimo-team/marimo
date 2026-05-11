# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import types
from collections.abc import Callable
from typing import Any, cast


def is_callable_method(obj: Any, attr: str) -> bool:
    """Check if an attribute is a real callable method on an object.

    Uses ``inspect.getattr_static`` so that attributes synthesized by
    ``__getattr__`` (e.g. ``pandas.api.typing.Expression``, which returns a
    new ``Expression`` for *any* attribute name) are not treated as protocol
    methods. Without this, dynamic-attribute objects appear to implement
    ``_display_`` / ``_mime_`` / ``_repr_*_`` and trigger infinite recursion
    in the formatter.
    """
    # Use getattr_static first so that we don't trigger __getattr__ traps
    # (e.g. pandas Expression returns a new Expression for any attribute).
    # Note this is a static lookup that also matches instance attributes —
    # it just bypasses __getattr__ / __getattribute__.
    try:
        inspect.getattr_static(obj, attr)
    except AttributeError:
        return False

    # Resolve the actual value so properties/descriptors still work. Swallow
    # any exception (e.g. property getters that raise) so protocol detection
    # stays robust and never crashes formatting.
    try:
        method = getattr(obj, attr)
    except Exception:
        return False

    if inspect.isclass(obj) and not isinstance(method, types.MethodType):
        return False
    return callable(method)


def getcallable(obj: object, name: str) -> Callable[..., Any] | None:
    """Get a callable attribute from an object, or None if not callable.

    This safely handles objects that implement __getattr__ and return
    non-callable values for any attribute name.
    """
    if (attr := getattr(obj, name, None)) is not None and callable(attr):
        return cast(Callable[..., Any], attr)
    return None
