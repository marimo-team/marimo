# Copyright 2025 Marimo. All rights reserved.
"""Async path operations similar to trio.Path.

This module provides async wrappers for common os.path and pathlib.Path
operations to avoid blocking the event loop in async contexts.

Each operation is executed in a thread pool via asyncio.to_thread(), which
yields control to the event loop while the blocking filesystem operation
completes in a background thread. This is the same approach used by trio.Path.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path


async def exists(path: str | Path) -> bool:
    """Check if a path exists asynchronously."""
    if isinstance(path, Path):
        return await asyncio.to_thread(path.exists)
    return await asyncio.to_thread(os.path.exists, path)


async def isfile(path: str | Path) -> bool:
    """Check if a path is a file asynchronously."""
    return await asyncio.to_thread(os.path.isfile, path)


async def isdir(path: str | Path) -> bool:
    """Check if a path is a directory asynchronously."""
    return await asyncio.to_thread(os.path.isdir, path)


async def abspath(path: str | Path) -> str:
    """Return absolute path asynchronously."""

    def _abspath() -> str:
        return os.path.abspath(path)

    return await asyncio.to_thread(_abspath)


async def realpath(path: str) -> str:
    """Return the canonical path asynchronously."""
    return await asyncio.to_thread(os.path.realpath, path)


async def normpath(path: str) -> str:
    """Normalize a pathname asynchronously."""
    return await asyncio.to_thread(os.path.normpath, path)


async def rglob(path: Path, pattern: str) -> list[Path]:
    """Recursively find all paths matching a pattern asynchronously."""

    def _rglob() -> list[Path]:
        return list(path.rglob(pattern))

    return await asyncio.to_thread(_rglob)


async def mkdir(
    path: Path,
    mode: int = 0o777,
    parents: bool = False,
    exist_ok: bool = False,
) -> None:
    """Create a directory asynchronously."""
    await asyncio.to_thread(path.mkdir, mode, parents, exist_ok)
