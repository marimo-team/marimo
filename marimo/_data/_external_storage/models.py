# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any, Generic, Literal, TypeVar, get_args

import msgspec

from marimo._types.ids import VariableName
from marimo._utils.assert_never import log_never

KNOWN_STORAGE_TYPES = Literal[
    "s3", "gcs", "azure", "http", "file", "in-memory"
]


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
        protocol: The protocol of the storage namespace. E.g. s3, gcs, azure, http, file, in-memory.
        root_path: The root path of the storage namespace.
        storage_entries: The storage entries in the storage namespace.
    """

    name: VariableName
    display_name: str
    protocol: str
    root_path: str
    storage_entries: list[StorageEntry]


DEFAULT_FETCH_LIMIT = 100


@dataclass
class DownloadResult:
    """Result of downloading a file from external storage.

    Attributes:
        file_bytes: The raw bytes of the downloaded file.
        filename: The suggested filename extracted from the path.
        ext: The file extension (without dot), or "bin" if none.
    """

    file_bytes: bytes
    filename: str
    ext: str


Backend = TypeVar("Backend")


class StorageBackend(abc.ABC, Generic[Backend]):
    def __init__(self, store: Backend, variable_name: VariableName) -> None:
        self.store = store
        self.variable_name = variable_name

    # TODO: We can make this async, but currently post_execution_hooks are synchronous.
    @abc.abstractmethod
    def list_entries(
        self,
        prefix: str | None,
        *,
        limit: int = DEFAULT_FETCH_LIMIT,
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

    async def download_file(self, path: str) -> DownloadResult:
        """Download the file at the given path with extracted metadata.

        Calls download() and extracts the filename and extension from the path.
        Subclasses can override this to customize filename extraction
        (e.g., using content-disposition headers).
        """
        file_bytes = await self.download(path)
        filename = path.rsplit("/", 1)[-1] or "download"
        _, sep, suffix = filename.rpartition(".")
        ext = suffix if sep and suffix else "bin"
        return DownloadResult(
            file_bytes=file_bytes,
            filename=filename,
            ext=ext,
        )

    @property
    @abc.abstractmethod
    def protocol(self) -> KNOWN_STORAGE_TYPES | str:
        """Return the protocol of the storage backend."""

    @property
    def display_name(self) -> str:
        protocol = self.protocol
        if protocol not in get_args(KNOWN_STORAGE_TYPES):
            return protocol.capitalize()
        if protocol == "s3":
            return "Amazon S3"
        elif protocol == "gcs":
            return "Google Cloud Storage"
        elif protocol == "azure":
            return "Azure Blob Storage"
        elif protocol == "http":
            return "HTTP"
        elif protocol == "file":
            return "File"
        elif protocol == "in-memory":
            return "In-memory"
        else:
            log_never(protocol)  # type: ignore[arg-type]
            return protocol

    @property
    @abc.abstractmethod
    def root_path(self) -> str | None:
        """Return the root path of the storage backend. None if in-memory or cannot be found"""

    @staticmethod
    @abc.abstractmethod
    def is_compatible(var: Any) -> bool:
        """Check if the backend is compatible with the given variable."""
