# Copyright 2026 Marimo. All rights reserved.
"""Stub system for cache serialization."""

from __future__ import annotations

from typing import Any, Callable

from marimo._save.stubs.function_stub import FunctionStub
from marimo._save.stubs.module_stub import ModuleStub
from marimo._save.stubs.pydantic_stub import PydanticStub
from marimo._save.stubs.stubs import (
    CUSTOM_STUBS,
    CustomStub,
    register_stub,
)
from marimo._save.stubs.ui_element_stub import UIElementStub

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
    try:
        mro_list = value_type.mro()
    except BaseException:
        # Some exotic metaclasses or broken types may raise when calling mro
        mro_list = [value_type]

    for cls in mro_list:
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


def maybe_get_custom_stub(value: Any) -> CustomStub | None:
    """Get the registered stub for a value's type, if any.

    Args:
        value: The value to get the stub for

    Returns:
        A stub instance if registered, None otherwise
    """
    # Fallback to custom cases
    if maybe_register_stub(value):
        value_type = type(value)
        if value_type in CUSTOM_STUBS:
            return CUSTOM_STUBS[value_type](value)
    return None


__all__ = [
    "CUSTOM_STUBS",
    "CustomStub",
    "FunctionStub",
    "ModuleStub",
    "UIElementStub",
    "maybe_register_stub",
    "maybe_get_custom_stub",
    "register_stub",
]
