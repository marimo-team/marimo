# Copyright 2026 Marimo. All rights reserved.
"""Lazy stub registration for cache serialization."""

from __future__ import annotations

import abc
from typing import Any

__all__ = ["CustomStub", "CUSTOM_STUBS", "register_stub"]


class CustomStub(abc.ABC):
    """Base class for custom stubs that can be registered in the cache."""

    __slots__ = ()

    @abc.abstractmethod
    def __init__(self, _obj: Any) -> None:
        """Initializes the stub with the object to be stubbed."""

    @abc.abstractmethod
    def load(self, glbls: dict[str, Any]) -> Any:
        """Loads the stub, restoring the original object."""
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def get_type() -> type:
        """Get the type this stub handles.

        May raise ImportError if the required package is not available.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def to_bytes(self) -> bytes:
        """Serialize the stub to bytes."""
        raise NotImplementedError

    @classmethod
    def register(cls, value: Any) -> None:
        """Register this stub for its target type.

        Handles the common registration pattern: get type, check isinstance,
        and register the stub. Catches ImportError if the target type's
        package is not available.

        Registers both the base type and the specific value's type to handle
        subclasses correctly.
        """
        try:
            target_type = cls.get_type()
            if isinstance(value, target_type):
                register_stub(target_type, cls)
                # Also register the specific subclass type
                value_type = type(value)
                if value_type != target_type:
                    register_stub(value_type, cls)
        except ImportError:
            pass


CUSTOM_STUBS: dict[type, type[CustomStub]] = {}


def register_stub(cls: type | None, stub: type[CustomStub]) -> None:
    """Register a custom stub for a given class type.

    Args:
        cls: The class type to register a stub for
        stub: The stub class to use for serialization
    """
    if cls is not None:
        CUSTOM_STUBS[cls] = stub
