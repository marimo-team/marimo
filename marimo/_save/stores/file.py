# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from pathlib import Path
from typing import Optional

from marimo._runtime.runtime import notebook_dir
from marimo._save.stores.store import Store


def _valid_path(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


class FileStore(Store):
    def __init__(self, save_path: Optional[str] = None) -> None:
        self.save_path = Path(save_path or self._default_save_path())
        self._init_save_path()

    def _default_save_path(self) -> Path:
        if (root := notebook_dir()) is not None:
            return Path(root / "__marimo__" / "cache")
        # This can happen if the notebook file is unnamed.
        return Path("__marimo__", "cache")

    def _init_save_path(self) -> None:
        self.save_path.mkdir(parents=True, exist_ok=True)

    def get(self, key: str) -> Optional[bytes]:
        path = self.save_path / key
        if not _valid_path(path):
            return None
        return path.read_bytes()

    def put(self, key: str, value: bytes) -> bool:
        path = self.save_path / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
        return True

    def hit(self, key: str) -> bool:
        path = self.save_path / key
        return _valid_path(path)
