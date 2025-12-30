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
)

__all__ = [
    # Storage
    "VirtualFileStorage",
    "SharedMemoryStorage",
    "InMemoryStorage",
    "VirtualFileStorageManager",
    # Virtual files
    "VirtualFile",
    "EMPTY_VIRTUAL_FILE",
    "VirtualFileLifecycleItem",
    "VirtualFileRegistryItem",
    "VirtualFileRegistry",
    "random_filename",
    "read_virtual_file",
]
