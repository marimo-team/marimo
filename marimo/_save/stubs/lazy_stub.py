# Copyright 2026 Marimo. All rights reserved.
"""msgspec schemas for lazy cache serialization."""

from __future__ import annotations

import pickle
from enum import Enum
from typing import Any

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
    """Represents a cached item with different value types.

    Only one of the value fields should be set (oneof semantics).
    """

    primitive: Any | None = None
    reference: str | None = None
    module: str | None = None
    # (code, filename, linenumber)
    function: tuple[str, str, int] | None = None
    hash: str | None = None

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
    version: int
    return_value: Item | None = None


class Cache(msgspec.Struct):
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
        del glbls
        blob = self.to_bytes()
        if not blob:
            raise ValueError(f"Reference {self.name} not found in store.")
        return pickle.loads(blob)

    def to_bytes(self) -> bytes:
        maybe_bytes = get_store().get(self.name)
        return maybe_bytes if maybe_bytes else b""


class ImmediateReferenceStub(CustomStub):
    """Wraps a ReferenceStub for immediate return-value restoration."""

    def __init__(self, reference: ReferenceStub) -> None:
        self.reference = reference

    def load(self, glbls: dict[str, Any]) -> Any:
        return self.reference.load(glbls)

    @staticmethod
    def get_type() -> type:
        return ReferenceStub

    def to_bytes(self) -> bytes:
        return self.reference.to_bytes()
