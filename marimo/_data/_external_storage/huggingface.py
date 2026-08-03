# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import mimetypes
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from marimo import _loggers
from marimo._data._external_storage.models import (
    DEFAULT_FETCH_LIMIT,
    SIGNED_URL_EXPIRATION,
    StorageBackend,
    StorageEntry,
    StorageListResult,
)
from marimo._data._external_storage.utils import (
    paginate_entries,
    parse_page_offset,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._utils.assert_never import log_never
from marimo._utils.typing import override

if TYPE_CHECKING:
    from huggingface_hub import BucketFile, HfApi  # noqa: F401
    from huggingface_hub.hf_api import LastCommitInfo

LOGGER = _loggers.marimo_logger()

_ROOT_LIST_LIMIT = 50

_RepoType = Literal["model", "dataset", "space"]

# Namespaced prefixes resolve to a "namespace/name" id spanning two path
# segments (e.g. "datasets/org/name", "buckets/namespace/bucket-name"),
# unlike model repos which have no prefix (e.g. "org/name").
_NAMESPACED_PREFIXES: dict[
    str, tuple[Literal["repo", "bucket"], _RepoType | None]
] = {
    "datasets": ("repo", "dataset"),
    "spaces": ("repo", "space"),
    "buckets": ("bucket", None),
}


@dataclass(frozen=True)
class _ResolvedHubPath:
    kind: Literal["root", "repo", "bucket"]
    repo_type: _RepoType | None = None
    repo_id: str | None = None
    path_in_repo: str = ""
    bucket_id: str | None = None


def _hub_path_for_repo(repo_type: _RepoType, repo_id: str) -> str:
    if repo_type == "dataset":
        return f"datasets/{repo_id}"
    if repo_type == "space":
        return f"spaces/{repo_id}"
    return repo_id


def _parse_hub_path(path: str) -> _ResolvedHubPath:
    normalized = path.strip().strip("/")
    if not normalized:
        return _ResolvedHubPath(kind="root")

    # Drop empty segments (e.g. from a double slash) so they don't get
    # folded into namespaced_id/repo_id.
    parts = [part for part in normalized.split("/") if part]
    prefix = parts[0]
    if prefix in _NAMESPACED_PREFIXES:
        if len(parts) < 3:
            raise ValueError(f"Incomplete Hugging Face Hub path: {path}")
        kind, repo_type = _NAMESPACED_PREFIXES[prefix]
        namespaced_id = f"{parts[1]}/{parts[2]}"
        path_in_repo = "/".join(parts[3:])
        if kind == "bucket":
            return _ResolvedHubPath(
                kind="bucket",
                bucket_id=namespaced_id,
                path_in_repo=path_in_repo,
            )
        return _ResolvedHubPath(
            kind="repo",
            repo_type=repo_type,
            repo_id=namespaced_id,
            path_in_repo=path_in_repo,
        )

    if len(parts) >= 2:
        return _ResolvedHubPath(
            kind="repo",
            repo_type="model",
            repo_id=f"{parts[0]}/{parts[1]}",
            path_in_repo="/".join(parts[2:]),
        )
    raise ValueError(f"Incomplete Hugging Face Hub path: {path}")


def _last_modified_from_commit(
    last_commit: LastCommitInfo | None,
) -> float | None:
    if last_commit is None:
        return None
    return last_commit.date.timestamp()


def _last_modified_from_bucket_item(
    uploaded_at: datetime | None,
) -> float | None:
    return (
        uploaded_at.timestamp() if isinstance(uploaded_at, datetime) else None
    )


def _directory_entry(path: str) -> StorageEntry:
    return StorageEntry(
        path=path, kind="directory", size=0, last_modified=None
    )


class HuggingfaceApi(StorageBackend["HfApi"]):
    """Storage backend for Hugging Face Hub. See https://github.com/huggingface/huggingface_hub/blob/main/docs/source/en/guides/hf_file_system.md
    on why HfApi is a preferred interface rather than HfFileSystem."""

    @override
    def list_entries(
        self,
        prefix: str | None,
        *,
        limit: int = DEFAULT_FETCH_LIMIT,
        page_token: str | None = None,
    ) -> StorageListResult:
        offset = parse_page_offset(page_token)
        entries = self._list_storage_entries(prefix or "")
        return paginate_entries(entries, offset=offset, limit=limit)

    def _list_storage_entries(self, prefix: str) -> list[StorageEntry]:
        resolved = _parse_hub_path(prefix)
        if resolved.kind == "root":
            return self._list_root_entries()
        if resolved.kind == "bucket":
            return self._list_bucket_entries(resolved)
        return self._list_repo_entries(resolved)

    def _list_root_entries(self) -> list[StorageEntry]:
        entries: list[StorageEntry] = []
        author = self._current_username()

        try:
            for dataset in self.store.list_datasets(
                author=author, limit=_ROOT_LIST_LIMIT
            ):
                hub_path = _hub_path_for_repo("dataset", dataset.id)
                entries.append(_directory_entry(hub_path))
        except Exception:
            LOGGER.debug("Hugging Face list_datasets failed", exc_info=True)

        try:
            for model in self.store.list_models(
                author=author, limit=_ROOT_LIST_LIMIT
            ):
                hub_path = _hub_path_for_repo("model", model.id)
                entries.append(_directory_entry(hub_path))
        except Exception:
            LOGGER.debug("Hugging Face list_models failed", exc_info=True)

        try:
            for space in self.store.list_spaces(
                author=author, limit=_ROOT_LIST_LIMIT
            ):
                hub_path = _hub_path_for_repo("space", space.id)
                entries.append(_directory_entry(hub_path))
        except Exception:
            LOGGER.debug("Hugging Face list_spaces failed", exc_info=True)

        try:
            for bucket in self.store.list_buckets():
                entries.append(_directory_entry(f"buckets/{bucket.id}"))
        except Exception:
            LOGGER.debug("Hugging Face list_buckets failed", exc_info=True)

        entries.sort(key=lambda entry: entry.path)
        return entries

    def _current_username(self) -> str | None:
        try:
            whoami: dict[str, Any] = self.store.whoami()
        except Exception:
            LOGGER.debug("Hugging Face whoami failed; listing public repos")
            return None
        name = whoami.get("name")
        if not isinstance(name, str):
            LOGGER.warning(
                "Hugging Face whoami returned a non-string name %s", name
            )
            return None
        return name

    def _list_repo_entries(
        self, resolved: _ResolvedHubPath
    ) -> list[StorageEntry]:
        from huggingface_hub import RepoFile, RepoFolder

        if resolved.repo_id is None or resolved.repo_type is None:
            raise ValueError("Missing Hugging Face repository metadata")

        repo_root = _hub_path_for_repo(resolved.repo_type, resolved.repo_id)
        path_in_repo = resolved.path_in_repo or None
        entries: list[StorageEntry] = []

        for item in self.store.list_repo_tree(
            resolved.repo_id,
            path_in_repo=path_in_repo,
            repo_type=resolved.repo_type,
            recursive=False,
        ):
            if isinstance(item, RepoFile):
                full_path = (
                    f"{repo_root}/{item.path}" if item.path else repo_root
                )
                entries.append(
                    StorageEntry(
                        path=full_path,
                        kind="file",
                        size=item.size or 0,
                        last_modified=_last_modified_from_commit(
                            item.last_commit
                        ),
                        mime_type=mimetypes.guess_type(full_path)[0],
                    )
                )
            elif isinstance(item, RepoFolder):
                folder_path = item.path.rstrip("/")
                full_path = (
                    f"{repo_root}/{folder_path}" if folder_path else repo_root
                )
                entries.append(
                    StorageEntry(
                        path=full_path,
                        kind="directory",
                        size=0,
                        last_modified=_last_modified_from_commit(
                            item.last_commit
                        ),
                        mime_type=None,
                    )
                )
            else:
                log_never(item)

        return entries

    def _list_bucket_entries(
        self, resolved: _ResolvedHubPath
    ) -> list[StorageEntry]:
        from huggingface_hub import BucketFile, BucketFolder

        if resolved.bucket_id is None:
            raise ValueError("Missing Hugging Face bucket id")

        bucket_root = f"buckets/{resolved.bucket_id}"
        prefix = resolved.path_in_repo or None
        entries: list[StorageEntry] = []

        for item in self.store.list_bucket_tree(
            resolved.bucket_id,
            prefix=prefix,
            recursive=False,
        ):
            if isinstance(item, BucketFile):
                full_path = (
                    f"{bucket_root}/{item.path}" if item.path else bucket_root
                )
                entries.append(
                    StorageEntry(
                        path=full_path,
                        kind="file",
                        size=item.size or 0,
                        last_modified=_last_modified_from_bucket_item(
                            item.uploaded_at
                        ),
                        mime_type=mimetypes.guess_type(full_path)[0],
                    )
                )
            elif isinstance(item, BucketFolder):
                folder_path = item.path.rstrip("/")
                full_path = (
                    f"{bucket_root}/{folder_path}"
                    if folder_path
                    else bucket_root
                )
                entries.append(
                    StorageEntry(
                        path=full_path,
                        kind="directory",
                        size=0,
                        last_modified=_last_modified_from_bucket_item(
                            item.uploaded_at
                        ),
                        mime_type=None,
                    )
                )
            else:
                log_never(item)

        return entries

    @override
    async def get_entry(self, path: str) -> StorageEntry:
        resolved = _parse_hub_path(path)
        if resolved.kind == "root":
            return _directory_entry("")
        if resolved.kind == "bucket":
            return await self._get_bucket_entry(resolved, path)
        return await self._get_repo_entry(resolved, path)

    async def _get_repo_entry(
        self, resolved: _ResolvedHubPath, path: str
    ) -> StorageEntry:
        from huggingface_hub import RepoFile, RepoFolder

        if resolved.repo_id is None or resolved.repo_type is None:
            raise ValueError("Missing Hugging Face repository metadata")

        path_in_repo = resolved.path_in_repo
        if not path_in_repo:
            return _directory_entry(path.strip("/"))

        paths_info = await asyncio.to_thread(
            self.store.get_paths_info,
            resolved.repo_id,
            path_in_repo,
            repo_type=resolved.repo_type,
        )
        if not paths_info:
            raise ValueError(f"Entry at {path} not found")

        item = paths_info[0]
        repo_root = _hub_path_for_repo(resolved.repo_type, resolved.repo_id)
        if isinstance(item, RepoFile):
            full_path = f"{repo_root}/{item.path}"
            return StorageEntry(
                path=full_path,
                kind="file",
                size=item.size or 0,
                last_modified=_last_modified_from_commit(item.last_commit),
                mime_type=mimetypes.guess_type(full_path)[0],
            )
        elif isinstance(item, RepoFolder):
            folder_path = item.path.rstrip("/")
            full_path = f"{repo_root}/{folder_path}"
            return StorageEntry(
                path=full_path,
                kind="directory",
                size=0,
                last_modified=_last_modified_from_commit(item.last_commit),
                mime_type=None,
            )
        else:
            log_never(item)

        raise ValueError(f"Entry at {path} is not a file or directory")

    async def _get_bucket_entry(
        self, resolved: _ResolvedHubPath, path: str
    ) -> StorageEntry:
        if resolved.bucket_id is None:
            raise ValueError("Missing Hugging Face bucket id")

        path_in_bucket = resolved.path_in_repo
        if not path_in_bucket:
            return _directory_entry(path.strip("/"))

        bucket_id = resolved.bucket_id
        bucket_root = f"buckets/{bucket_id}"

        def _get_file() -> BucketFile | None:
            results = list(
                self.store.get_bucket_paths_info(bucket_id, [path_in_bucket])
            )
            return results[0] if results else None

        item = await asyncio.to_thread(_get_file)
        if item is not None:
            full_path = f"{bucket_root}/{item.path}"
            return StorageEntry(
                path=full_path,
                kind="file",
                size=item.size or 0,
                last_modified=_last_modified_from_bucket_item(
                    item.uploaded_at
                ),
                mime_type=mimetypes.guess_type(full_path)[0],
            )

        # get_bucket_paths_info only resolves files (nonexistent paths are
        # silently ignored, and directories aren't supported at all), so
        # fall back to a listing to handle the directory case.
        entries = await asyncio.to_thread(self._list_bucket_entries, resolved)
        normalized = path.strip().strip("/")
        for entry in entries:
            if entry.path.strip("/") == normalized:
                return entry
        raise ValueError(f"Entry at {path} not found")

    @override
    async def download(self, path: str) -> bytes:
        resolved = _parse_hub_path(path)
        if resolved.kind == "bucket":
            return await self._download_bucket_file(resolved)
        return await self._download_repo_file(resolved)

    async def _download_repo_file(self, resolved: _ResolvedHubPath) -> bytes:
        from huggingface_hub import hf_hub_download

        if resolved.repo_id is None or resolved.repo_type is None:
            raise ValueError("Missing Hugging Face repository metadata")
        if not resolved.path_in_repo:
            raise ValueError("Cannot download a repository root")

        repo_id = resolved.repo_id
        repo_type = resolved.repo_type
        path_in_repo = resolved.path_in_repo

        def _read() -> bytes:
            local_path = hf_hub_download(
                repo_id=repo_id,
                filename=path_in_repo,
                repo_type=repo_type,
                token=self.store.token,
                endpoint=self.store.endpoint,
            )
            return Path(local_path).read_bytes()

        return await asyncio.to_thread(_read)

    async def _download_bucket_file(self, resolved: _ResolvedHubPath) -> bytes:
        if resolved.bucket_id is None or not resolved.path_in_repo:
            raise ValueError("Missing Hugging Face bucket file path")

        bucket_id = resolved.bucket_id
        path_in_repo = resolved.path_in_repo

        def _read() -> bytes:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp_path = tmp.name
            try:
                self.store.download_bucket_files(
                    bucket_id,
                    [(path_in_repo, tmp_path)],
                    token=self.store.token,
                )
                return Path(tmp_path).read_bytes()
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        return await asyncio.to_thread(_read)

    @override
    async def read_range(
        self, path: str, *, offset: int = 0, length: int | None = None
    ) -> bytes:
        """Read a byte range from the file. If length is None, read the entire file."""
        resolved = _parse_hub_path(path)
        if resolved.kind != "repo":
            data = await self.download(path)
            if length is None:
                return data[offset:]
            return data[offset : offset + length]

        if resolved.repo_id is None or resolved.repo_type is None:
            raise ValueError("Missing Hugging Face repository metadata")
        if not resolved.path_in_repo:
            raise ValueError("Cannot read a repository root")

        if length == 0:
            return b""

        from huggingface_hub import HfFileSystem

        hub_path = (
            f"{_hub_path_for_repo(resolved.repo_type, resolved.repo_id)}"
            f"/{resolved.path_in_repo}"
        )

        def _read() -> bytes:
            # Both HfApi and HfFileSystem can be used to read a file, but HfFileSystem abstracts away the http call logic.
            fs = HfFileSystem(
                token=self.store.token, endpoint=self.store.endpoint
            )
            # block_size=0 bypasses fsspec's default block cache, which always reads `blocksize` bytes past what's requested
            # (see `fsspec.caching.ReadAheadCache._fetch`). Without this, every read would over-fetch.
            with fs.open(hub_path, "rb", block_size=0) as f:
                if offset:
                    f.seek(offset)
                data = f.read() if length is None else f.read(length)
                if not isinstance(data, bytes):
                    raise TypeError(
                        "Expected bytes from a binary-mode read, got "
                        f"{type(data).__name__}"
                    )
                return data

        return await asyncio.to_thread(_read)

    @override
    async def sign_download_url(
        self, path: str, expiration: int = SIGNED_URL_EXPIRATION
    ) -> str | None:
        del expiration  # Hugging Face resolve URLs are not time-limited.
        resolved = _parse_hub_path(path)
        if resolved.kind == "bucket":
            if resolved.bucket_id is None or not resolved.path_in_repo:
                return None
            from urllib.parse import quote

            # huggingface_hub has no URL-builder helper for buckets (unlike
            # hf_hub_url for repos), so we construct it by hand. This mirrors
            # what huggingface_hub itself does internally for buckets, e.g.
            # HfApi.get_bucket_file_metadata and HfFileSystem.url().
            return (
                f"{self.store.endpoint}/buckets/{resolved.bucket_id}/resolve/"
                f"{quote(resolved.path_in_repo, safe='/')}"
            )

        if resolved.kind != "repo":
            return None
        if resolved.repo_id is None or resolved.repo_type is None:
            # Should be unreachable: _ResolvedHubPath always sets these together when kind == "repo".
            LOGGER.debug(
                "Hugging Face repo path resolved without repo metadata: %s",
                path,
            )
            return None
        if not resolved.path_in_repo:
            return None

        from huggingface_hub import hf_hub_url

        return hf_hub_url(
            resolved.repo_id,
            resolved.path_in_repo,
            repo_type=resolved.repo_type,
            endpoint=self.store.endpoint,
        )

    @property
    @override
    def protocol(self) -> str:
        return "hf"

    @property
    @override
    def backend_type(self) -> Literal["huggingface"]:
        return "huggingface"

    @property
    @override
    def display_name(self) -> str:
        return "Hugging Face Hub"

    @property
    @override
    def root_path(self) -> str | None:
        return None

    @staticmethod
    @override
    def is_compatible(var: Any) -> bool:
        if not DependencyManager.huggingface_hub.imported():
            return False

        from huggingface_hub import HfApi

        return isinstance(var, HfApi)
