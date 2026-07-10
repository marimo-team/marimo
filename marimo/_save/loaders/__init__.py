# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from marimo._save.loaders.json import JsonLoader
from marimo._save.loaders.lazy import (
    LazyLoader,
    WasmLazyLoader,
    dump_cache_manifests,
    flush_active_caches,
)
from marimo._save.loaders.loader import (
    BasePersistenceLoader,
    Loader,
    LoaderPartial,
    LoaderType,
)
from marimo._save.loaders.memory import MemoryLoader
from marimo._save.loaders.pickle import PickleLoader
from marimo._utils.platform import is_pyodide

LoaderKey = Literal["memory", "pickle", "json", "lazy"]


@dataclass(frozen=True)
class DualLoader:
    """A loader registered as a native/WASM pair under one name.

    `resolve()` performs the *single* environment check and returns the
    concrete loader class, so nothing downstream re-checks the platform.
    Any loader can opt into dual behavior by registering one of these.
    """

    native: LoaderType
    wasm: LoaderType

    def resolve(self) -> LoaderType:
        return self.wasm if is_pyodide() else self.native


def resolve_loader(entry: LoaderType | DualLoader) -> LoaderType:
    """Resolve a registry entry to a concrete loader class."""
    return entry.resolve() if isinstance(entry, DualLoader) else entry


PERSISTENT_LOADERS: dict[LoaderKey, LoaderType | DualLoader] = {
    "pickle": PickleLoader,
    "json": JsonLoader,
    "lazy": DualLoader(native=LazyLoader, wasm=WasmLazyLoader),
}

__all__ = [
    "PERSISTENT_LOADERS",
    "BasePersistenceLoader",
    "DualLoader",
    "JsonLoader",
    "LazyLoader",
    "Loader",
    "LoaderKey",
    "LoaderPartial",
    "LoaderType",
    "MemoryLoader",
    "PickleLoader",
    "WasmLazyLoader",
    "dump_cache_manifests",
    "flush_active_caches",
    "resolve_loader",
]
