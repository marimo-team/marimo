# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import abc
from typing import Any, Generic, Literal, TypeVar

import msgspec

from marimo._types.ids import VariableName


# Note: We may want to consolidate with FileInfo from _server/models/files.py
class StorageEntry(msgspec.Struct, rename="camel"):
    """A storage entry is a file, directory, or object for external storage systems

    Attributes:
        path: The path of the storage entry.
        kind: The kind of the storage entry.
        size: The size of the storage entry.
        last_modified: The last modified time of the storage entry.
        metadata: The metadata of the storage entry.
    """

    path: str
    kind: Literal["file", "directory", "object"]
    size: int
    last_modified: float | None
    metadata: dict[str, Any] = msgspec.field(default_factory=dict)


class StorageNamespace(msgspec.Struct, rename="camel"):
    """Represents external storage systems (filesystems and object storage)

    Attributes:
        name: The variable name of the storage namespace.
        display_name: The display name of the storage namespace.
        source: The source of the storage namespace. E.g. S3, GCS, Google Drive, etc.
        root_path: The root path of the storage namespace.
        storage_entries: The storage entries in the storage namespace.
    """

    name: VariableName | None
    display_name: str
    source: str
    root_path: str
    storage_entries: list[StorageEntry]


DEFAULT_FETCH_LIMIT = 50

Backend = TypeVar("Backend")


class StorageBackend(abc.ABC, Generic[Backend]):
    def __init__(
        self, store: Backend, variable_name: VariableName | None
    ) -> None:
        self.store = store
        self.variable_name = variable_name

    @abc.abstractmethod
    def list_entries(
        self,
        prefix: str | None,
        *,
        limit: int = DEFAULT_FETCH_LIMIT,
        offset: str | None = None,
    ) -> list[StorageEntry]:
        """
        List the entries at the given prefix. If no prefix is provided, list the root entries.
        """

    @abc.abstractmethod
    async def get_entry(self, path: str) -> StorageEntry:
        """Get the entry at the given path."""

    @abc.abstractmethod
    async def download(self, path: str) -> bytes:
        """Download the file at the given path."""

    @property
    @abc.abstractmethod
    def protocol(self) -> str:
        """Return the protocol of the storage backend."""

    @property
    @abc.abstractmethod
    def root_path(self) -> str | None:
        """Return the root path of the storage backend. None if in-memory or cannot be found"""

    @staticmethod
    @abc.abstractmethod
    def is_compatible(var: Any) -> bool:
        """Check if the backend is compatible with the given variable."""
