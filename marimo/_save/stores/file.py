# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import re
from pathlib import Path

from marimo import _loggers
from marimo._runtime.runtime import notebook_dir
from marimo._save.cache_dirs import partial_write_name
from marimo._save.stores.store import Store
from marimo._utils.paths import MARIMO_DIR_NAME, notebook_output_dir

LOGGER = _loggers.marimo_logger()

# Resolves against the working directory as a fallback.
FALLBACK_SAVE_PATH = Path(MARIMO_DIR_NAME, "cache")


def export_manifest_name(notebook_filename: str | None) -> str:
    """Export-manifest filename for a notebook, from its filename stem.

    Kernel and exporter derive it identically so they agree on the file. A
    dotfile so it can't collide with a cache key. NB. only the stem is used, so
    two same-named notebooks writing to a shared cache dir would collide.
    """
    stem = Path(notebook_filename).stem if notebook_filename else "notebook"
    slug = re.sub(r"[^0-9A-Za-z._-]+", "-", stem).strip("-") or "notebook"
    return f".{slug}-export.json"


def _valid_path(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def _writable_dir(path: Path) -> bool:
    """Whether `path` is a writable directory. Creates it if absent."""
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    # NB. mkdir is a no-op on an existing directory, whatever its mode.
    return os.access(path, os.W_OK | os.X_OK)


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
        root = notebook_dir()
        if root is None:
            return FALLBACK_SAVE_PATH

        # Probe the write target, which `sys.pycache_prefix` can move out of
        # the notebook's directory.
        target = notebook_output_dir(root) / "cache"
        if _writable_dir(target):
            return target

        LOGGER.warning(
            "Could not write to the cache directory %s. Caching to %s instead.",
            target,
            FALLBACK_SAVE_PATH.resolve(),
        )
        return FALLBACK_SAVE_PATH

    def _init_save_path(self) -> None:
        self.save_path.mkdir(parents=True, exist_ok=True)

    def local_dir(self) -> Path | None:
        # NB. the already-resolved path, never `save_path`: resolving a
        # default probes writability by creating directories, and asking a
        # store where it keeps its entries must not create any.
        return self._resolved_save_path

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
        # A sibling keeps the rename on one filesystem, where it is atomic.
        tmp = path.with_name(partial_write_name(path.name))
        try:
            tmp.write_bytes(value)
            os.replace(tmp, path)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
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
