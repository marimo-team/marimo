# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from pathlib import Path


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

    def local_dir(self) -> Path | None:
        """Return the local directory holding this store's entries.

        Lets a caller report the disk a cache occupies without knowing which
        store it writes through. Defaults to `None`, which reads as "keeps
        nothing on this filesystem" and covers remote stores as well as a
        store with no resolved location yet.
        """
        return None

    def get_batch(
        self, keys: Iterable[str]
    ) -> Iterator[tuple[str, bytes | None]]:
        """Yield `(key, data)` pairs for `keys`.

        Defaults to a sequential `get` per key. Stores that can fetch
        concurrently (e.g. the WASM HTTP store) override this.
        """
        for key in keys:
            yield key, self.get(key)

    def export_keys(self) -> list[str]:
        """Return the keys this session wrote or read that should be
        bundled on `--execute` export.

        Defaults to none; stores that track usage override this. Returning `[]`
        keeps non-tracking stores inert.
        """
        return []


StoreType = type[Store]
