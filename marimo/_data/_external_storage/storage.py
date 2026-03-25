# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import mimetypes
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Literal, cast

from marimo import _loggers
from marimo._data._external_storage.models import (
    CLOUD_STORAGE_TYPES,
    DEFAULT_FETCH_LIMIT,
    KNOWN_STORAGE_TYPES,
    SIGNED_URL_EXPIRATION,
    BackendType,
    StorageBackend,
    StorageEntry,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._utils.assert_never import log_never
from marimo._utils.dicts import remove_none_values

if TYPE_CHECKING:
    from fsspec import (  # type: ignore[import-untyped]
        AbstractFileSystem,  # noqa: F401
    )
    from obstore import ObjectMeta
    from obstore.store import (
        AzureConfig,
        AzureStore,
        GCSConfig,
        GCSStore,
        ObjectStore,  # noqa: F401
        S3Config,
        S3Store,
    )

LOGGER = _loggers.marimo_logger()


class Obstore(StorageBackend["ObjectStore"]):
    def list_entries(
        self,
        prefix: str | None,
        *,
        limit: int = DEFAULT_FETCH_LIMIT,
    ) -> list[StorageEntry]:
        result = self.store.list_with_delimiter(prefix=prefix)

        storage_entries: list[StorageEntry] = []

        # Common prefixes are virtual directories (e.g., "folder/")
        # We can't identify the size / last modified time unless we recursively list the entries
        for common_prefix in result["common_prefixes"]:
            storage_entries.append(
                StorageEntry(
                    path=common_prefix,
                    kind="directory",
                    size=0,
                    last_modified=None,
                )
            )

        # Objects are actual files/objects at this level
        for entry in result["objects"]:
            # Skip zero-byte folder marker objects that some S3 clients
            # create as directory placeholders (e.g., "folder" with size 0)
            path = entry.get("path", "")
            size = entry.get("size", 0)
            if size == 0 and prefix and path == prefix.rstrip("/"):
                continue
            storage_entries.append(self._create_storage_entry(entry))

        if len(storage_entries) > limit:
            LOGGER.debug(
                "Fetched %s entries, but limiting to %s",
                len(storage_entries),
                limit,
            )
            storage_entries = storage_entries[:limit]

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
            mime_type=mimetypes.guess_type(path or "")[0],
        )

    async def download(self, path: str) -> bytes:
        result = await self.store.get_async(path)
        bytes_data = await result.bytes_async()
        return bytes(bytes_data)

    async def read_range(
        self, path: str, *, offset: int = 0, length: int | None = None
    ) -> bytes:
        if length is None:
            data = await self.download(path)
            return data[offset:]
        from obstore import get_range_async

        return bytes(
            await get_range_async(
                self.store, path, start=offset, length=length
            )
        )

    async def sign_download_url(
        self, path: str, expiration: int = SIGNED_URL_EXPIRATION
    ) -> str | None:
        from obstore import sign_async
        from obstore.store import AzureStore, GCSStore, S3Store

        if not isinstance(self.store, (S3Store, GCSStore, AzureStore)):
            return None
        try:
            return await sign_async(
                self.store,
                "GET",
                path,
                expires_in=timedelta(seconds=expiration),
            )
        except Exception:
            LOGGER.info("Failed to sign URL for %s", path)
            return None

    def _get_config(
        self, store: AzureStore | GCSStore | S3Store
    ) -> AzureConfig | GCSConfig | S3Config | None:
        try:
            return store.config
        except BaseException:
            # Sometimes, there will be a Rust panic when trying to get the config for invalid stores
            LOGGER.exception(
                "Failed to read store config for %s", type(store).__name__
            )
        return None

    @property
    def protocol(self) -> KNOWN_STORAGE_TYPES | str:
        from obstore.store import (
            AzureStore,
            GCSStore,
            HTTPStore,
            LocalStore,
            MemoryStore,
            S3Store,
        )

        # Try the endpoint URL which can give a more accurate protocol
        if not isinstance(self.store, (MemoryStore, HTTPStore, LocalStore)):
            config = self._get_config(self.store)
            if config is None:
                return "unknown"

            endpoint = config.get("endpoint")
            if isinstance(endpoint, str) and (
                protocol := detect_protocol_from_url(endpoint)
            ):
                return protocol

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
    def backend_type(self) -> BackendType:
        return "obstore"

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

            config = self._get_config(self.store)
            if config is None:
                return None

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


# The async implementations has a few unimplemented methods (like ls), so it's better to use synchronous versions and
# wrap them in asyncio.to_thread
class FsspecFilesystem(StorageBackend["AbstractFileSystem"]):
    def list_entries(
        self,
        prefix: str | None,
        *,
        limit: int = DEFAULT_FETCH_LIMIT,
    ) -> list[StorageEntry]:
        # If no prefix provided, we use empty string to list root entries
        # Else, an error is raised
        if prefix is None:
            prefix = ""

        files = self._list_files(prefix)
        normalized_prefix = self._normalize_path(prefix)
        if self._has_self_entry(files, normalized_prefix):
            LOGGER.debug(
                "Detected self-entry for prefix %s, invalidating cache and retrying",
                prefix,
            )
            self._invalidate_listing_cache_for_prefix(prefix)
            files = self._list_files(prefix)

        # Drop exact self-entries that survived the retry
        files = self._filter_self_entries(files, normalized_prefix)

        total_files = len(files)
        if total_files > limit:
            LOGGER.debug(
                "Fetched %s files, but limiting to %s",
                total_files,
                limit,
            )
            files = files[:limit]

        storage_entries = []
        for file in files:
            if isinstance(file, dict):
                storage_entry = self._create_storage_entry(file)
                storage_entries.append(storage_entry)

        return storage_entries

    def _normalize_path(self, path: str) -> str:
        return path.strip().strip("/")

    def _list_files(self, prefix: str) -> list[Any]:
        files = self.store.ls(path=prefix, detail=True)
        if not isinstance(files, list):
            raise ValueError(f"Files is not a list: {files}")
        return files

    def _has_self_entry(
        self, files: list[Any], normalized_prefix: str
    ) -> bool:
        # Some fsspec backends may return the queried directory itself when
        # listings are satisfied from cache. Detect that exact shape so we can
        # recover and avoid recursive "folder contains itself" trees.
        if not normalized_prefix:
            return False
        return any(self._is_self_entry(f, normalized_prefix) for f in files)

    def _is_self_entry(self, file: Any, normalized_prefix: str) -> bool:
        if not isinstance(file, dict):
            return False
        name = file.get("name")
        if not isinstance(name, str):
            return False
        return self._normalize_path(name) == normalized_prefix

    def _filter_self_entries(
        self, files: list[Any], normalized_prefix: str
    ) -> list[Any]:
        """Drop entries whose normalized path matches the queried prefix exactly.

        Descendants like "foo/foo" are preserved; only exact echoes are removed.
        """
        if not normalized_prefix:
            return files
        return [
            f for f in files if not self._is_self_entry(f, normalized_prefix)
        ]

    def _invalidate_listing_cache_for_prefix(self, prefix: str) -> None:
        dircache = getattr(self.store, "dircache", None)
        if dircache is None:
            return

        # Clear the minimum cache surface (target, parent, and root) that can
        # contribute stale self-entries before retrying list().
        cache_keys: set[str] = {self._normalize_path(prefix), ""}
        parent_fn = getattr(self.store, "_parent", None)
        if callable(parent_fn):
            parent = parent_fn(prefix)
            if isinstance(parent, str):
                cache_keys.add(self._normalize_path(parent))

        for key in cache_keys:
            try:
                dircache.pop(key, None)
            except Exception:
                # Some custom mappings may not support pop semantics.
                LOGGER.debug(
                    "Failed to clear fsspec cache key %s for listing", key
                )

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
        entry = await asyncio.to_thread(self.store.info, path)
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

        resolved_path = name or ""
        return StorageEntry(
            path=resolved_path,
            size=size or 0,
            last_modified=file.get("mtime"),
            kind=resolved_kind,
            metadata=entry_meta,
            mime_type=mimetypes.guess_type(resolved_path)[0]
            if resolved_kind != "directory"
            else None,
        )

    async def download(self, path: str) -> bytes:
        # There is no async version of open, so we wrap the synchronous open method
        def _read() -> str | bytes:
            return self.store.open(path).read()  # type: ignore[no-any-return]

        file = await asyncio.to_thread(_read)
        if isinstance(file, str):
            return file.encode("utf-8")
        return file

    async def read_range(
        self, path: str, *, offset: int = 0, length: int | None = None
    ) -> bytes:
        end = offset + length if length is not None else None
        data = await asyncio.to_thread(
            self.store.cat_file, path, start=offset, end=end
        )
        if isinstance(data, str):
            return data.encode("utf-8")
        return bytes(data)

    async def sign_download_url(
        self, path: str, expiration: int = SIGNED_URL_EXPIRATION
    ) -> str | None:
        try:
            url = await asyncio.to_thread(
                self.store.sign, path, expiration=expiration
            )
            return str(url)
        except NotImplementedError:
            return None
        except Exception:
            LOGGER.info("Failed to sign URL for %s", path)
            return None

    @property
    def protocol(self) -> KNOWN_STORAGE_TYPES | str:
        store_protocol = self.store.protocol
        storage_options = self.store.storage_options

        # Try the endpoint URL which can give a more accurate protocol
        endpoint_url = storage_options.get("endpoint_url")
        if isinstance(endpoint_url, str) and (
            protocol := detect_protocol_from_url(endpoint_url)
        ):
            return protocol

        if isinstance(store_protocol, tuple):
            for store_protocol_item in store_protocol:
                if normalized := normalize_protocol(store_protocol_item):
                    return normalized
            return "-".join(store_protocol)

        return normalize_protocol(store_protocol) or store_protocol

    @property
    def backend_type(self) -> BackendType:
        return "fsspec"

    @property
    def root_path(self) -> str | None:
        return cast(str, self.store.root_marker)

    @staticmethod
    def is_compatible(var: Any) -> bool:
        if not DependencyManager.fsspec.imported():
            return False

        from fsspec import AbstractFileSystem

        return isinstance(var, AbstractFileSystem)


_PROTOCOL_MAP: dict[str, KNOWN_STORAGE_TYPES] = {
    "s3": "s3",
    "s3a": "s3",
    "gs": "gcs",
    "gcs": "gcs",
    "abfs": "azure",
    "abfss": "azure",
    "az": "azure",
    "adl": "azure",
    "http": "http",
    "https": "http",
    "file": "file",
    "local": "file",
    "memory": "in-memory",
    "r2": "cloudflare",
}

# Specific provider patterns checked before generic ones (e.g. S3),
# since S3-compatible services may also have "s3" in their URL.
# The order of the patterns is important, the first pattern that matches will be used.
_URL_PATTERNS: list[tuple[str, CLOUD_STORAGE_TYPES]] = [
    ("cloudflare", "cloudflare"),
    ("r2.", "cloudflare"),
    ("cwobject", "coreweave"),
    ("cwlota", "coreweave"),
    ("coreweave", "coreweave"),
    ("blob.core.windows", "azure"),
    ("azure", "azure"),
    ("googleapis", "gcs"),
    ("storage.google", "gcs"),
    ("s3", "s3"),
    ("amazonaws", "s3"),
]


def detect_protocol_from_url(url: str) -> CLOUD_STORAGE_TYPES | None:
    """Detect the storage provider from an endpoint URL."""
    url = url.strip().lower()
    for pattern, protocol in _URL_PATTERNS:
        if pattern in url:
            return protocol
    return None


def normalize_protocol(protocol: str) -> KNOWN_STORAGE_TYPES | None:
    """Normalize a protocol string (e.g. 's3a', 'gs', 'abfs') to a known storage type."""
    return _PROTOCOL_MAP.get(protocol.strip().lower())
