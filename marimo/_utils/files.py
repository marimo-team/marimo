# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import glob
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

from marimo._utils import async_path

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

_SPLIT_NUMBERS = re.compile(r"([0-9]+)").split


def natural_sort(filename: str) -> list[int | str]:
    return [
        int(c) if c.isdigit() else c.lower() for c in _SPLIT_NUMBERS(filename)
    ]


def get_files(folder: str) -> Generator[Path, None, None]:
    """Recursively get all files from a folder."""
    with os.scandir(folder) as scan:
        for item in scan:
            if item.is_file():
                yield Path(item.path)
            elif item.is_dir() and not item.name.startswith("."):
                yield from get_files(item.path)


async def async_get_files(folder: str) -> AsyncGenerator[Path, None]:
    """Asynchronously recursively get all files from a folder."""
    with os.scandir(folder) as scan:
        for item in scan:
            if item.is_file():
                yield Path(item.path)
            elif item.is_dir() and not item.name.startswith("."):
                async for file_path in async_get_files(item.path):
                    yield file_path


def expand_file_patterns(file_patterns: tuple[str, ...]) -> list[Path]:
    """Expand file patterns to actual file paths.

    Args:
        file_patterns: Tuple of file patterns (files, directories, or glob-like patterns)

    Returns:
        List of Path objects for all matching files
    """
    files_to_check = []
    for pattern in file_patterns:
        if os.path.isfile(pattern):
            files_to_check.append(Path(pattern))
        elif os.path.isdir(pattern):
            files_to_check.extend(get_files(pattern))
        else:
            if "**" in pattern or "*" in pattern or "?" in pattern:
                files_to_check.extend(
                    Path(match)
                    for match in glob.iglob(pattern, recursive=True)
                    if os.path.isfile(match)
                )
            else:
                # Not a glob pattern but file doesn't exist, skip
                pass

    # Remove duplicates and sort
    return sorted(set(files_to_check))


async def async_expand_file_patterns(
    file_patterns: tuple[str, ...],
) -> AsyncGenerator[Path, None]:
    """Asynchronously expand file patterns to file paths, yielding as discovered.

    Args:
        file_patterns: Tuple of file patterns (files, directories, or glob-like patterns)

    Yields:
        Path objects for matching files (including non-existent explicit files)
    """
    seen = set()

    for pattern in file_patterns:
        if await async_path.isfile(pattern):
            path = Path(pattern)
            if path not in seen:
                seen.add(path)
                yield path
        elif await async_path.isdir(pattern):
            async for file_path in async_get_files(pattern):
                if file_path not in seen:
                    seen.add(file_path)
                    yield file_path
        else:
            if "**" in pattern or "*" in pattern or "?" in pattern:
                # `iglob` already blocks the event loop. An async `isfile`
                # starts a thread for each match and doubles the time.
                for match in glob.iglob(pattern, recursive=True):
                    file_path = Path(match)
                    if file_path not in seen and os.path.isfile(match):  # noqa: ASYNC240
                        seen.add(file_path)
                        yield file_path
            else:
                # Not a glob pattern but file doesn't exist - yield it anyway for error handling
                path = Path(pattern)
                if path not in seen:
                    seen.add(path)
                    yield path
