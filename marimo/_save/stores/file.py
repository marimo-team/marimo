# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from pathlib import Path

from marimo._runtime.runtime import notebook_dir
from marimo._save.stores.store import Store
from marimo._utils.paths import notebook_output_dir


def _valid_path(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


class FileStore(Store):
    def __init__(self, save_path: str | None = None) -> None:
        # Defer default path resolution until first use so that the runtime
        # context (and __file__) is available.
        self._resolved_save_path: Path | None = (
            Path(save_path) if save_path is not None else None
        )
        self._initialized = False

    @property
    def save_path(self) -> Path:
        if self._resolved_save_path is None:
            self._resolved_save_path = self._default_save_path()
        return self._resolved_save_path

    def _default_save_path(self) -> Path:
        if (root := notebook_dir()) is not None:
            return notebook_output_dir(root) / "cache"
        # This can happen if the notebook file is unnamed.
        return Path("__marimo__", "cache")

    def _init_save_path(self) -> None:
        self.save_path.mkdir(parents=True, exist_ok=True)

    def get(self, key: str) -> bytes | None:
        if not self._initialized:
            self._init_save_path()
        self._initialized = True
        path = self.save_path / key
        if not _valid_path(path):
            return None
        return path.read_bytes()

    def put(self, key: str, value: bytes) -> bool:
        path = self.save_path / key
        path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = True
        path.write_bytes(value)
        return True

    def hit(self, key: str) -> bool:
        path = self.save_path / key
        return _valid_path(path)

    def clear(self, key: str) -> bool:
        path = self.save_path / key
        path.parent.mkdir(parents=True, exist_ok=True)
        if not _valid_path(path):
            return False
        path.unlink()
        return True
