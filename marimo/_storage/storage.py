# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, cast

from marimo import _loggers
from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.utils import remove_none_values
from marimo._storage.models import (
    DEFAULT_FETCH_LIMIT,
    StorageBackend,
    StorageEntry,
)
from marimo._utils.assert_never import log_never

if TYPE_CHECKING:
    from fsspec import (  # type: ignore[import-untyped]
        AbstractFileSystem,  # noqa: F401
    )
    from obstore import ObjectMeta
    from obstore.store import ObjectStore  # noqa: F401

LOGGER = _loggers.marimo_logger()


class Obstore(StorageBackend["ObjectStore"]):
    def list_entries(
        self,
        prefix: str | None,
        *,
        limit: int = DEFAULT_FETCH_LIMIT,
        offset: str | None = None,
    ) -> list[StorageEntry]:
        entries_stream = self.store.list(
            prefix=prefix, offset=offset, chunk_size=limit, return_arrow=False
        )
        entries_chunk = next(entries_stream, [])

        storage_entries = []
        for entry in entries_chunk:
            storage_entry = self._create_storage_entry(entry)
            storage_entries.append(storage_entry)
        return storage_entries

    async def get_entry(self, path: str) -> StorageEntry:
        entry = await self.store.head_async(path)
        return self._create_storage_entry(entry)

    def _create_storage_entry(self, entry: ObjectMeta) -> StorageEntry:
        path, size = entry.get("path"), entry.get("size")
        if path is None or size is None:
            LOGGER.debug(
                "Entry is missing required fields: path=%s, size=%s",
                path,
                size,
            )
        entry_meta = remove_none_values(
            {"e_tag": entry.get("e_tag"), "version": entry.get("version")}
        )
        last_modified = entry.get("last_modified")
        return StorageEntry(
            path=path or "",
            size=size or 0,
            last_modified=last_modified.timestamp() if last_modified else None,
            kind="object",
            metadata=entry_meta,
        )

    async def download(self, path: str) -> bytes:
        result = await self.store.get_async(path)
        bytes_data = await result.bytes_async()
        return bytes(bytes_data)

    @property
    def protocol(self) -> str:
        from obstore.store import (
            AzureStore,
            GCSStore,
            HTTPStore,
            LocalStore,
            MemoryStore,
            S3Store,
        )

        if isinstance(self.store, MemoryStore):
            return "in-memory"
        elif isinstance(self.store, HTTPStore):
            return "http"
        elif isinstance(self.store, LocalStore):
            return "file"
        elif isinstance(self.store, S3Store):
            return "s3"
        elif isinstance(self.store, AzureStore):
            return "azure"
        elif isinstance(self.store, GCSStore):
            return "gcs"
        else:
            log_never(self.store)
            return "unknown"

    @property
    def root_path(self) -> str | None:
        from obstore.store import HTTPStore, LocalStore, MemoryStore

        if isinstance(self.store, MemoryStore):
            return None
        elif isinstance(self.store, HTTPStore):
            return self.store.url
        prefix = self.store.prefix

        if prefix is None:
            if isinstance(self.store, LocalStore):
                return None  # root

            config = self.store.config
            bucket = config.get("bucket")
            if bucket is None:
                LOGGER.debug(
                    "No bucket found for storage backend. Config %s", config
                )
            elif not isinstance(bucket, str):
                LOGGER.debug("Bucket is not a string: %s", bucket)
                return str(bucket)
            return bucket

        return str(prefix)

    @staticmethod
    def is_compatible(var: Any) -> bool:
        if not DependencyManager.obstore.imported():
            return False

        from obstore.store import ObjectStore

        return isinstance(var, ObjectStore)  # type: ignore[misc,arg-type]


# Temporary limit for filesystem storage. We should play around with this value.
MAX_FILESYSTEM_FETCH_LIMIT = 200


class FsspecFilesystem(StorageBackend["AbstractFileSystem"]):
    def list_entries(
        self,
        prefix: str | None,
        *,
        limit: int = DEFAULT_FETCH_LIMIT,
        offset: str | None = None,
    ) -> list[StorageEntry]:
        del limit, offset

        # If no prefix provided, we use empty string to list root entries
        # Else, an error is raised
        if prefix is None:
            prefix = ""

        files = self.store.ls(path=prefix, detail=True)
        if not isinstance(files, list):
            raise ValueError(f"Files is not a list: {files}")
        total_files = len(files)
        if total_files > MAX_FILESYSTEM_FETCH_LIMIT:
            LOGGER.info(
                "Fetched %s files, but limiting to %s",
                total_files,
                MAX_FILESYSTEM_FETCH_LIMIT,
            )
            files = files[:MAX_FILESYSTEM_FETCH_LIMIT]

        storage_entries = []
        for file in files:
            if isinstance(file, dict):
                storage_entry = self._create_storage_entry(file)
                storage_entries.append(storage_entry)

        return storage_entries

    def _identify_kind(self, entry_type: str) -> Literal["file", "directory"]:
        entry_type = entry_type.strip().lower()
        if entry_type == "file":
            return "file"
        elif entry_type == "directory":
            return "directory"
        else:
            LOGGER.debug("Unknown entry type: %s", entry_type)
            return "file"

    async def get_entry(self, path: str) -> StorageEntry:
        entry = self.store.info(path)
        if not isinstance(entry, dict):
            raise ValueError(f"Entry at {path} is not a dictionary")
        return self._create_storage_entry(entry)

    def _create_storage_entry(self, file: dict[str, Any]) -> StorageEntry:
        name, size = file.get("name"), file.get("size")
        if name is None or size is None:
            LOGGER.debug(
                "File is missing required fields: name=%s, size=%s",
                name,
                size,
            )
        entry_meta = remove_none_values(
            {
                "e_tag": file.get("ETag"),
                "is_link": file.get("islink"),
                "mode": file.get("mode"),
                "n_link": file.get("nlink"),
                "created": file.get("created"),
            }
        )
        resolved_kind: Literal["file", "directory"] = "file"
        entry_type = file.get("type")
        if entry_type is None:
            LOGGER.debug(
                "File is missing required fields: type=%s", entry_type
            )
        else:
            resolved_kind = self._identify_kind(entry_type)

        return StorageEntry(
            path=name or "",
            size=size or 0,
            last_modified=file.get("mtime"),
            kind=resolved_kind,
            metadata=entry_meta,
        )

    async def download(self, path: str) -> bytes:
        file = self.store.open(path).read()
        if isinstance(file, str):
            return file.encode("utf-8")
        return cast(bytes, file)  # typechecker doesn't know that file is bytes

    @property
    def protocol(self) -> str:
        if isinstance(self.store.protocol, tuple):
            return "-".join(self.store.protocol)
        return cast(str, self.store.protocol)

    @property
    def root_path(self) -> str | None:
        return cast(str, self.store.root_marker)

    @staticmethod
    def is_compatible(var: Any) -> bool:
        if not DependencyManager.fsspec.imported():
            return False

        from fsspec import AbstractFileSystem

        return isinstance(var, AbstractFileSystem)
