# Copyright 2025 Marimo. All rights reserved.
"""msgspec schemas for lazystore, replacing protobuf definitions."""

from __future__ import annotations

import pickle
from enum import Enum
from typing import Any, Optional

import msgspec

from marimo._save.stores import get_store
from marimo._save.stubs.stubs import CustomStub


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
    # filename, code, linenumber
    function: Optional[tuple[str, str, int]] = None
    unhashable: Optional[dict[str, str]] = None
    hash: Optional[str] = None

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


class ReferenceStub:
    def __init__(
        self, name: str, loader: str | None = None, hash_value: str = ""
    ) -> None:
        self.name = name
        self.loader = loader
        self.hash = hash_value

    def load(self, glbls: dict[str, Any]) -> dict[str, Any]:
        """Load the reference from the store, returning all variables.

        Returns:
            A dictionary mapping variable names to their loaded values.
        """
        from marimo._save.cache import _restore_from_stub_if_needed

        blob = self.to_bytes()
        if not blob:
            raise ValueError(f"Reference {self.name} not found in store.")

        # The blob is a pickled dict of {var_name: value, ...}
        pickled_dict = pickle.loads(blob)

        # Restore any nested stubs
        restored_dict = _restore_from_stub_if_needed(pickled_dict, glbls)

        return restored_dict

    def to_bytes(self) -> bytes:
        from marimo._save.stubs import LAZY_STUB_LOOKUP

        if self.loader is None:
            self.loader = LAZY_STUB_LOOKUP.get(type(self), "pickle")
        maybe_bytes = get_store().get(self.name)
        return maybe_bytes if maybe_bytes else b""


class UnhashableStub:
    """Stub for variables that cannot be hashed or pickled.

    Used for graceful degradation when caching fails for certain objects
    like lambdas, threads, sockets, etc. The cache can still be saved
    with these stubs, and when a cell needs them, it can trigger a rerun.
    """

    def __init__(
        self,
        obj: Any,
        error: Optional[Exception] = None,
        var_name: str = "",
        hash_value: str = "",
    ) -> None:
        self.obj_type = type(obj)
        self.type_name = f"{self.obj_type.__module__}.{self.obj_type.__name__}"
        # Unhashables come in 2 forms, either the serialization failed (and we
        # has an explicit error), or it's something like a scope function or
        # lambda (in which case, no error but unhashable)
        self.error_msg = "<scoped function>" if not error else str(error)
        self.var_name = var_name
        self.hash = hash_value

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
