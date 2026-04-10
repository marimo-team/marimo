# Copyright 2026 Marimo. All rights reserved.
"""Virtual file storage and management for marimo.

This module provides storage backends and file management for virtual files
created during notebook execution.
"""

from __future__ import annotations

from marimo._runtime.virtual_file.storage import (
    InMemoryStorage,
    SharedMemoryStorage,
    VirtualFileStorage,
    VirtualFileStorageManager,
)
from marimo._runtime.virtual_file.virtual_file import (
    EMPTY_VIRTUAL_FILE,
    VirtualFile,
    VirtualFileLifecycleItem,
    VirtualFileRegistry,
    VirtualFileRegistryItem,
    random_filename,
    read_virtual_file,
    read_virtual_file_chunked,
)

__all__ = [
    "EMPTY_VIRTUAL_FILE",
    "InMemoryStorage",
    "SharedMemoryStorage",
    # Virtual files
    "VirtualFile",
    "VirtualFileLifecycleItem",
    "VirtualFileRegistry",
    "VirtualFileRegistryItem",
    # Storage
    "VirtualFileStorage",
    "VirtualFileStorageManager",
    "random_filename",
    "read_virtual_file",
    "read_virtual_file_chunked",
]
