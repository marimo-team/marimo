# Copyright 2026 Marimo. All rights reserved.
"""msgspec schemas for lazy cache serialization."""

from __future__ import annotations

import pickle
from enum import Enum
from typing import Any, Optional

import msgspec

from marimo._save.stores import get_store
from marimo._save.stubs.stubs import CustomStub


class CacheType(Enum):
    """Enumeration of supported cache entry types."""

    CONTEXT_EXECUTION_PATH = "ContextExecutionPath"
    CONTENT_ADDRESSED = "ContentAddressed"
    EXECUTION_PATH = "ExecutionPath"
    PURE = "Pure"
    DEFERRED = "Deferred"
    UNKNOWN = "Unknown"


class Item(msgspec.Struct):
    """Represents a cached item with different value types.

    Only one of the value fields should be set (oneof semantics).
    """

    primitive: Optional[Any] = None
    reference: Optional[str] = None
    module: Optional[str] = None
    # (code, filename, linenumber)
    function: Optional[tuple[str, str, int]] = None
    hash: Optional[str] = None

    def __post_init__(self) -> None:
        fields_set = sum(
            1
            for field in [
                self.primitive,
                self.reference,
                self.module,
                self.function,
            ]
            if field is not None
        )
        if fields_set > 1:
            raise ValueError("Item can only have one value field set")


class Meta(msgspec.Struct):
    """Metadata stored alongside a lazy cache entry, including the schema version and optional return value."""

    version: int
    return_value: Optional[Item] = None


class Cache(msgspec.Struct):
    """Top-level msgspec schema for a serialized lazy cache entry."""

    hash: str
    cache_type: CacheType
    defs: dict[str, Item]
    stateful_refs: list[str]
    meta: Meta
    ui_defs: list[str] = msgspec.field(default_factory=list)


class ReferenceStub:
    """Deferred blob reference — loads from store on access."""

    def __init__(
        self, name: str, loader: str | None = None, hash_value: str = ""
    ) -> None:
        self.name = name
        self.loader = loader
        self.hash = hash_value

    def load(self, glbls: dict[str, Any]) -> Any:
        """Unpickle and return the referenced blob from the store."""
        del glbls
        blob = self.to_bytes()
        if not blob:
            raise ValueError(f"Reference {self.name} not found in store.")
        return pickle.loads(blob)

    def to_bytes(self) -> bytes:
        """Fetch the raw bytes for this reference from the store."""
        maybe_bytes = get_store().get(self.name)
        return maybe_bytes if maybe_bytes else b""


class ImmediateReferenceStub(CustomStub):
    """Wraps a ReferenceStub for immediate return-value restoration."""

    def __init__(self, reference: ReferenceStub) -> None:
        self.reference = reference

    def load(self, glbls: dict[str, Any]) -> Any:
        """Delegate loading to the wrapped ReferenceStub."""
        return self.reference.load(glbls)

    @staticmethod
    def get_type() -> type:
        """Return the underlying stub type (ReferenceStub) for stub registry lookup."""
        return ReferenceStub

    def to_bytes(self) -> bytes:
        """Return the raw bytes of the wrapped reference stub."""
        return self.reference.to_bytes()
