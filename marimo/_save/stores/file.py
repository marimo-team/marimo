# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from marimo import _loggers
from marimo._runtime.runtime import notebook_dir
from marimo._save.stores.store import Store

LOGGER = _loggers.marimo_logger()


def _valid_path(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


class FileStore(Store):
    def __init__(self, save_path: Optional[str] = None) -> None:
        self.save_path = Path(save_path or self._default_save_path())
        # NB. construction may be called on store import, so do not create
        # directories until needed.
        self._initialized = False
        self._pending: list[threading.Thread] = []

    def _default_save_path(self) -> Path:
        if (root := notebook_dir()) is not None:
            return Path(root / "__marimo__" / "cache")
        # This can happen if the notebook file is unnamed.
        return Path("__marimo__", "cache")

    def _init_save_path(self) -> None:
        self.save_path.mkdir(parents=True, exist_ok=True)

    def get(self, key: str) -> Optional[bytes]:
        self.flush()
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
        t = threading.Thread(
            target=self._do_write,
            args=(path, value),
            daemon=False,
        )
        t.start()
        self._pending.append(t)
        return True

    def hit(self, key: str) -> bool:
        self.flush()
        path = self.save_path / key
        return _valid_path(path)

    def clear(self, key: str) -> bool:
        self.flush()
        path = self.save_path / key
        path.parent.mkdir(parents=True, exist_ok=True)
        if not _valid_path(path):
            return False
        path.unlink()
        return True

    def flush(self) -> None:
        for t in self._pending:
            t.join()
        self._pending.clear()

    @staticmethod
    def _do_write(path: Path, value: bytes) -> None:
        try:
            path.write_bytes(value)
        except Exception:
            LOGGER.exception("Background cache write failed for: %s", path)
