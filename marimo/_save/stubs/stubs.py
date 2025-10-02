# Copyright 2025 Marimo. All rights reserved.
"""Lazy stub registration for cache serialization."""

from __future__ import annotations

from typing import Any, Callable

from marimo._save.stubs.base import CUSTOM_STUBS
from marimo._save.stubs.pydantic_stub import PydanticStub

# Track which class names we've already attempted to register
_REGISTERED_NAMES: set[str] = set()

# Dictionary mapping fully qualified class names to registration functions
STUB_REGISTRATIONS: dict[str, Callable[[Any], None]] = {
    "pydantic.main.BaseModel": PydanticStub.register,
}


def maybe_register_stub(value: Any) -> bool:
    """Lazily register a stub for a value's type if not already registered.

    This allows us to avoid importing third-party packages until they're
    actually used in the cache. Walks the MRO to check if any parent class
    matches a registered stub type.

    Returns:
        True if the value's type is in CUSTOM_STUBS (either already registered
        or newly registered), False otherwise.
    """
    value_type = type(value)

    # Already registered in CUSTOM_STUBS
    if value_type in CUSTOM_STUBS:
        return True

    # Walk MRO to find matching base class
    for cls in value_type.__mro__:
        if not (hasattr(cls, "__module__") and hasattr(cls, "__name__")):
            continue

        cls_name = f"{cls.__module__}.{cls.__name__}"

        if cls_name in STUB_REGISTRATIONS:
            if cls_name not in _REGISTERED_NAMES:
                _REGISTERED_NAMES.add(cls_name)
                STUB_REGISTRATIONS[cls_name](value)
            # After registration attempt, check if now in CUSTOM_STUBS
            return value_type in CUSTOM_STUBS

    return False
