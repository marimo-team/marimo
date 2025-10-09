# Copyright 2025 Marimo. All rights reserved.
"""msgspec schemas for lazystore, replacing protobuf definitions."""

from __future__ import annotations

import pickle
from enum import Enum
from typing import Any, Optional

import msgspec

from marimo._save.stores import get_store
from marimo._save.stubs.function_stub import FunctionStub
from marimo._save.stubs.module_stub import ModuleStub
from marimo._save.stubs.stubs import CustomStub
from marimo._save.stubs.ui_element_stub import UIElementStub


class CacheType(Enum):
    CONTEXT_EXECUTION_PATH = "ContextExecutionPath"
    CONTENT_ADDRESSED = "ContentAddressed"
    EXECUTION_PATH = "ExecutionPath"
    PURE = "Pure"
    DEFERRED = "Deferred"
    UNKNOWN = "Unknown"


class Item(msgspec.Struct):
    """Represents a cached item with different value types."""

    # Union field to represent the protobuf oneof
    primitive: Optional[Any] = None
    reference: Optional[str] = None
    module: Optional[str] = None
    function: Optional[str] = None
    unhashable: Optional[dict[str, str]] = None

    def __post_init__(self) -> None:
        # Ensure only one field is set (mimicking protobuf oneof behavior)
        fields_set = sum(
            1
            for field in [
                self.primitive,
                self.reference,
                self.module,
                self.function,
                self.unhashable,
            ]
            if field is not None
        )
        if fields_set > 1:
            raise ValueError("Item can only have one value field set")


class Meta(msgspec.Struct):
    """Metadata for cached items."""

    version: int
    return_value: Optional[Item] = None


class Cache(msgspec.Struct):
    """Main cache structure."""

    defs: dict[str, Item]
    hash: str
    cache_type: CacheType
    stateful_refs: list[str]
    meta: Meta
    ui_defs: list[str] = msgspec.field(default_factory=list)


# No longer needed with msgspec - direct serialization


class ReferenceStub:
    def __init__(self, name: str, loader: str | None = None) -> None:
        self.name = name
        self.loader = loader

    def load(self, glbls: dict[str, Any]) -> Any:
        """Load the reference from the store."""
        from marimo._save.cache import _restore_from_stub_if_needed
        blob = self.to_bytes()
        if blob is None:
            raise ValueError(f"Reference {self.name} not found in scope.")
        response = pickle.loads(blob)
        value = _restore_from_stub_if_needed(response, glbls)
        return value

    def to_bytes(self) -> bytes:
        if self.loader is None:
            self.loader = TYPE_LOOKUP.get(type(self), "pickle")
        maybe_bytes = get_store().get(self.name)
        return maybe_bytes if maybe_bytes else b""


class UnhashableStub:
    """Stub for variables that cannot be hashed or pickled.

    Used for graceful degradation when caching fails for certain objects
    like lambdas, threads, sockets, etc. The cache can still be saved
    with these stubs, and when a cell needs them, it can trigger a rerun.
    """

    def __init__(self, obj: Any, error: Optional[Exception] = None, var_name: str = "") -> None:
        self.obj_type = type(obj)
        self.type_name = f"{self.obj_type.__module__}.{self.obj_type.__name__}"
        self.error_msg = "<unknown>" if not error else str(error)
        self.var_name = var_name

    def load(self, glbls: dict[str, Any]) -> Any:
        """Cannot load unhashable stubs - need to rerun the cell."""
        del glbls  # Unused
        raise ValueError(
            f"Cannot load unhashable variable '{self.var_name}' "
            f"of type {self.type_name}. Original error: {self.error_msg}. "
            "Cell needs to be re-executed."
        )

    def to_bytes(self) -> bytes:
        """Unhashable stubs cannot be serialized."""
        return b""


TYPE_LOOKUP: dict[type, str] = {
    int: "txtpb",
    str: "txtpb",
    float: "txtpb",
    bool: "txtpb",
    bytes: "txtpb",
    type(None): "txtpb",
    FunctionStub: "txtpb",
    ModuleStub: "txtpb",
    UIElementStub: "ui",
    UnhashableStub: "unhashable",
}


class ImmediateReferenceStub(CustomStub):
    def __init__(self, reference: ReferenceStub) -> None:
        # Promotion from reference stub to immediate reference stub
        # So that cache value can be restored immediately
        self.reference = reference

    def load(self, glbls: dict[str, Any]) -> Any:
        return self.reference.load(glbls)

    @staticmethod
    def get_type() -> type:
        return ReferenceStub

    def to_bytes(self) -> bytes:
        return self.reference.to_bytes()
