# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from pathlib import Path

from marimo import _loggers
from marimo._config.config import FileBrowserConfig
from marimo._server.models.files import FileRoot

LOGGER = _loggers.marimo_logger()


def resolve_file_roots(
    primary_root: str,
    config: FileBrowserConfig | None,
) -> list[FileRoot]:
    """Resolve the primary and configured roots for the file browser."""
    primary_path = _normalize_primary_root(primary_root)
    roots = [
        FileRoot(
            path=primary_path,
            name=_default_root_name(primary_path),
            is_primary=True,
        )
    ]
    seen = {_deduplication_key(primary_path)}

    if config is not None and not isinstance(config, dict):
        _warn_invalid_root(config, "file_browser must be a table")
        return roots
    folders = (config or {}).get("folders", [])
    if not isinstance(folders, list):
        _warn_invalid_root(folders, "folders must be a list")
        return roots

    for folder in folders:
        if not isinstance(folder, dict):
            _warn_invalid_root(folder, "folder must be a table")
            continue
        path = folder.get("path")
        if not isinstance(path, str) or not path:
            _warn_invalid_root(path, "path must be a non-empty string")
            continue

        candidate = Path(path)
        if not candidate.is_absolute():
            _warn_invalid_root(path, "path must be absolute")
            continue

        try:
            normalized = str(candidate.resolve(strict=True))
        except (OSError, RuntimeError) as error:
            _warn_invalid_root(path, str(error))
            continue

        if not Path(normalized).is_dir():
            _warn_invalid_root(path, "path is not a directory")
            continue
        if not os.access(normalized, os.R_OK | os.X_OK):
            _warn_invalid_root(path, "directory is not readable")
            continue

        key = _deduplication_key(normalized)
        if key in seen:
            _warn_invalid_root(path, "duplicate root")
            continue
        seen.add(key)

        configured_name = folder.get("name")
        name = (
            configured_name.strip()
            if isinstance(configured_name, str) and configured_name.strip()
            else _default_root_name(normalized)
        )
        roots.append(FileRoot(path=normalized, name=name, is_primary=False))

    return roots


def _normalize_primary_root(path: str) -> str:
    try:
        return str(Path(path).resolve(strict=True))
    except (OSError, RuntimeError):
        # The existing browser root is authoritative even if it becomes
        # unavailable after startup. Keep it visible so refreshes can recover.
        return os.path.abspath(path)


def _deduplication_key(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


def _default_root_name(path: str) -> str:
    name = Path(path).name
    return name or Path(path).anchor or path


def _warn_invalid_root(path: object, reason: str) -> None:
    LOGGER.warning("Ignoring file browser root %r: %s", path, reason)
