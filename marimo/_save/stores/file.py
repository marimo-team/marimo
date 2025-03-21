# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from marimo._save.cache import (
    Cache,
)
from marimo._save.stores.store import Store

if TYPE_CHECKING:
    from marimo._save.hash import HashKey
    from marimo._save.loaders import BasePersistenceLoader as Loader


def _valid_path(path: Path):
    return os.path.exists(path) and os.path.getsize(path) > 0


class FileStore(Store):
    def get(self, key: HashKey, loader: Loader) -> Optional[bytes]:
        path = loader.build_path(key)
        if not _valid_path(path):
            return None
        with open(path, "rb") as f:
            return f.read()

    def put(self, cache: Cache, loader: Loader) -> None:
        path = loader.build_path(cache.key)
        blob = loader.to_blob(cache)
        if blob is None:
            return
        with open(path, "wb") as f:
            f.write(blob)

    def hit(self, key: HashKey, loader: Loader) -> bool:
        path = loader.build_path(key)
        return _valid_path(path)
