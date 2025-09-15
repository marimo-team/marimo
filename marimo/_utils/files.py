# Copyright 2025 Marimo. All rights reserved.
import fnmatch
import os
import re
from collections.abc import Generator
from pathlib import Path
from typing import Union


def natural_sort(filename: str) -> list[Union[int, str]]:
    def convert(text: str) -> Union[int, str]:
        return int(text) if text.isdigit() else text.lower()

    def alphanum_key(key: str) -> list[Union[int, str]]:
        return [convert(c) for c in re.split("([0-9]+)", key)]

    return alphanum_key(filename)


def get_files(folder: str) -> Generator[Path, None, None]:
    """Recursively get all files from a folder."""
    with os.scandir(folder) as scan:
        for item in scan:
            if item.is_file():
                yield Path(item.path)
            elif item.is_dir() and not item.name.startswith("."):
                yield from get_files(item.path)


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
            # Handle glob patterns by walking from root and filtering
            if "**" in pattern or "*" in pattern or "?" in pattern:
                # Extract root directory to walk from
                root = "."
                parts = pattern.split("/")
                for i, part in enumerate(parts):
                    if "*" in part or "?" in part:
                        root = "/".join(parts[:i]) if i > 0 else "."
                        break
                    elif os.path.isdir("/".join(parts[: i + 1])):
                        root = "/".join(parts[: i + 1])

                # Get all files from root and filter by pattern
                if os.path.isdir(root):
                    all_files = get_files(root)
                    matched_files = [
                        path
                        for path in all_files
                        if fnmatch.fnmatch(str(path), pattern)
                    ]
                    files_to_check.extend(matched_files)
            else:
                # Not a glob pattern but file doesn't exist, skip
                pass

    # Remove duplicates and sort
    return sorted(set(files_to_check))
