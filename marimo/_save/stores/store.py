# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator


class Store(ABC):
    @abstractmethod
    def get(self, key: str) -> bytes | None:
        """Get the bytes of a cache from the store"""

    @abstractmethod
    def put(self, key: str, value: bytes) -> bool:
        """Put a cache into the store"""

    @abstractmethod
    def hit(self, key: str) -> bool:
        """Check if the cache is in the store"""

    def clear(self, key: str) -> bool:
        """Check if the cache is in the store"""
        del key
        return False


class WasmExportableStore(Store):
    """Interface for stores that support WASM export.

    Provides concurrent multi-key fetch (for WASM blob loading)
    and export manifest tracking (for --execute bundling).
    """

    @abstractmethod
    def get_batch(
        self, keys: Iterable[str]
    ) -> Iterator[tuple[str, bytes | None]]:
        """Yield (key, data) pairs, potentially fetching concurrently."""
        ...

    @abstractmethod
    def export_manifest(self) -> list[str]:
        """Return all store keys this session wrote or read.

        Used by --execute export to know exactly which files to copy
        to public/cache/ for WASM bundling.
        """
        ...


StoreType = type[Store]
