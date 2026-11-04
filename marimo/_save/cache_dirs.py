# Copyright 2026 Marimo. All rights reserved.
"""Discovery of the on-disk cache directories that a path resolves to.

Pure and kernel-free so the CLI can import it without starting a runtime.
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from marimo import _loggers
from marimo._utils.paths import (
    MARIMO_DIR_NAME,
    normalize_path,
    notebook_output_dir,
)

if TYPE_CHECKING:
    from collections.abc import Collection, Iterator, Mapping

LOGGER = _loggers.marimo_logger()

CACHE_DIR_NAME = "cache"

# A value too large to inline is split over a directory of blobs and described
# by an entry of this suffix. The entry is written last, so its presence shows
# that the blobs beside it are complete.
LAZY_ENTRY_SUFFIX = ".jsonl"

# Windows rejects most punctuation in a path component.
_UNSAFE_IN_BLOCK_NAME = re.compile(r"[^a-zA-Z0-9 _-]")

# A key is a cache-type prefix and a digest. The digest uses url-safe base64
# without padding, so its length cannot be one more than a multiple of four.
# Without the prefix a name can also be a directory of blobs.
_DIGEST = re.compile(r"[A-Za-z0-9_-]{2,}")

# Loaders write entries with these suffixes, and a neighboring file with any
# other suffix belongs to something else.
_ENTRY_SUFFIXES = frozenset({"json", "jsonl", "pickle"})

# An entry is written to a sibling and renamed into place, so a reader never
# meets a half-written value. A process killed between the two steps leaves
# the sibling behind, bytes on disk that hold no cached value.
PARTIAL_WRITE_INFIX = ".tmp"
_PARTIAL_WRITE_TAG = re.compile(r"[0-9a-f]{8}")

# Statuses that still describe a marimo notebook, unlike "empty" and
# "invalid".
_NOTEBOOK_STATUSES = frozenset({"valid", "has_warnings", "has_errors"})


class CacheDirError(Exception):
    """Base class for cache-directory resolution failures."""


class NotANotebookError(CacheDirError):
    """Raised when a path names a file that is not a marimo notebook."""


def notebook_cache_dir(notebook_path: Path) -> Path:
    """Return the cache directory belonging to `notebook_path`.

    The directory need not exist. `sys.pycache_prefix` moves it away from the
    notebook, so a caller must run under the same prefix as the kernel that
    wrote the cache.
    """
    parent = normalize_path(notebook_path).parent
    return notebook_output_dir(parent) / CACHE_DIR_NAME


def directory_cache_dir(directory: Path) -> Path:
    """Return the cache directory for a notebook run in `directory`.

    The directory need not exist. A cache directory resolves to itself.
    """
    directory = normalize_path(directory)
    if _is_cache_dir(directory):
        return directory
    # Resolve through a notebook inside the directory. A directory name with
    # a suffix, such as "data.v2", reads as a file until it exists on disk,
    # and a file's cache sits one directory up.
    return notebook_output_dir(directory / "notebook.py") / CACHE_DIR_NAME


def resolve_cache_dirs(path: Path, recursive: bool = False) -> list[Path]:
    """Return the cache directories that `path` resolves to, absolute.

    A notebook file resolves to the cache directory beside it, and a
    directory to the cache directory for a notebook run there. Both are
    listed whether or not they exist yet. With `recursive`, a directory is
    instead searched for existing `__marimo__/cache` directories, skipping
    dot-folders. The search can come back empty.

    Raises:
        FileNotFoundError: If `path` does not exist.
        NotANotebookError: If `path` is neither a directory nor a marimo
            notebook file.
    """
    if path.is_dir():
        if recursive:
            return _walk_cache_dirs(path)
        return [directory_cache_dir(path)]
    if not path.exists():
        raise FileNotFoundError(f"No such file or directory: {path}")
    if not path.is_file():
        # Reading a pipe or a device as notebook text can block for good.
        raise NotANotebookError(f"{path} is not a notebook file.")
    _validate_notebook(path)
    return [notebook_cache_dir(path)]


@dataclass(frozen=True)
class CacheDirStats:
    """Disk usage of a cache directory."""

    total_bytes: int = 0
    entries: int = 0

    def __add__(self, other: CacheDirStats) -> CacheDirStats:
        return CacheDirStats(
            total_bytes=self.total_bytes + other.total_bytes,
            entries=self.entries + other.entries,
        )

    def __sub__(self, other: CacheDirStats) -> CacheDirStats:
        return CacheDirStats(
            total_bytes=max(self.total_bytes - other.total_bytes, 0),
            entries=max(self.entries - other.entries, 0),
        )


def cache_dir_stats(cache_dir: Path) -> CacheDirStats:
    """Return byte and entry count in `cache_dir`.

    A directory that does not exist, or that cannot be read, reports zero.
    """
    if not cache_dir.is_dir():
        return CacheDirStats()

    stats = CacheDirStats()
    for block in _children(cache_dir):
        if _is_directory(block):
            stats += _block_stats(block)
        else:
            stats += CacheDirStats(total_bytes=_file_bytes(block))
    return stats


def block_dir_name(name: str) -> str:
    """Return the directory for a cache block called `name`."""
    return _UNSAFE_IN_BLOCK_NAME.sub("_", name.strip("*"))


def select_blocks(
    cache_dir: Path, names: Collection[str] | None = None
) -> dict[Path, frozenset[str]]:
    """Return the entry keys in each block of `cache_dir` that `names` select.

    An empty `names` selects every block. A cache with an empty name writes
    entries at the cache root, and selection lists them under `cache_dir`
    itself.
    """
    if not cache_dir.is_dir():
        return {}
    wanted = {block_dir_name(name) for name in names} if names else None
    blocks = [cache_dir] + [
        child for child in _children(cache_dir) if _is_directory(child)
    ]
    selected: dict[Path, frozenset[str]] = {}
    for block in blocks:
        name = "" if block == cache_dir else block.name
        if wanted is not None and name not in wanted:
            continue
        keys = _entry_keys(block)
        if keys:
            selected[block] = frozenset(keys)
        elif block != cache_dir and _children(block):
            LOGGER.warning("Skipping %s: it holds no cache entries.", block)
    return selected


def delete_blocks(
    cache_dir: Path,
    selection: Mapping[Path, Collection[str]],
    *,
    dry_run: bool = False,
) -> CacheDirStats:
    """Delete the selected entries of each block, reporting what that freed.

    A block directory goes once nothing is left in it. A dry run deletes
    nothing and reports what deleting frees.
    """
    freed = CacheDirStats()
    for block, keys in selection.items():
        try:
            freed += _delete_block_entries(block, set(keys), dry_run=dry_run)
        except OSError as e:
            LOGGER.warning("Skipping %s: %s", block, e)
            continue
        if dry_run or block == cache_dir:
            continue
        # A store pointed at a project puts entries beside source files, so
        # only entries and their blobs go, and the directory only when empty.
        if _children(block):
            LOGGER.warning("Kept %s: files remain in it.", block)
            continue
        try:
            block.rmdir()
        except OSError as e:
            LOGGER.warning("Could not remove %s: %s", block, e)
    return freed


def clean_cache_dir(
    cache_dir: Path,
    names: Collection[str] | None = None,
    *,
    dry_run: bool = False,
) -> CacheDirStats:
    """Delete blocks from `cache_dir`, returns stats of freed entries."""
    return delete_blocks(
        cache_dir, select_blocks(cache_dir, names), dry_run=dry_run
    )


def delete_cache_entries(
    cache_dir: Path,
    entries: Collection[tuple[str, str]],
    *,
    dry_run: bool = False,
) -> CacheDirStats:
    """Delete the `(block, key)` entries named, reporting what that freed.

    With `dry_run`, only report what would be freed (no deletion).

    Raises:
        OSError: If a block cannot be listed.
    """
    by_block: dict[str, set[str]] = {}
    for block, key in entries:
        if not _names_an_entry(block, key):
            LOGGER.warning(
                "Not deleting %s: no cache entry can be named that.",
                Path(block) / key,
            )
            continue
        by_block.setdefault(block, set()).add(key)
    freed = CacheDirStats()
    for block, keys in by_block.items():
        freed += _delete_block_entries(
            cache_dir / block, keys, dry_run=dry_run
        )
    return freed


def configured_store_dirs(path: Path, cache_dirs: list[Path]) -> list[Path]:
    """Return the directories the `cache.store` configured for `path` writes
    to, or `cache_dirs` when no store is configured."""
    # The stores import this module, so they are imported here instead.
    from marimo._save.stores import (
        cache_store_is_untrusted,
        configured_cache_store,
    )
    from marimo._save.stores.file import FileStore
    from marimo._save.stores.tiered import TieredStore

    try:
        store = configured_cache_store(current_path=str(path))
        if store is None:
            return cache_dirs
        untrusted = cache_store_is_untrusted(current_path=str(path))
    except Exception:
        LOGGER.warning("Could not read the cache store from the config")
        return cache_dirs

    tiers = store.stores if isinstance(store, TieredStore) else [store]
    directories: list[Path] = list(cache_dirs) if untrusted else []
    for tier in tiers:
        if isinstance(tier, FileStore) and tier.uses_default_path:
            directories.extend(cache_dirs)
        else:
            directories.extend(tier.local_dirs())
    return list(dict.fromkeys(directories))


def named_by_path(
    path: Path, own: list[Path], configured: list[Path]
) -> tuple[list[Path], list[Path]]:
    """Split `configured` into the directories `path` names and the rest.

    A directory is named when it is `path` itself or one of `own`, the
    directories `path` resolves to without a configured store.
    """
    named = {normalize_path(directory) for directory in own}
    named.add(normalize_path(path))
    kept = [d for d in configured if normalize_path(d) in named]
    unnamed = [d for d in configured if normalize_path(d) not in named]
    return kept, unnamed


def partial_write_name(name: str) -> str:
    """Return the sibling name to write `name` to before renaming it in."""
    return f"{name}{PARTIAL_WRITE_INFIX}{uuid4().hex[:8]}"


def is_partial_write(name: str) -> bool:
    """Whether `name` is a sibling that an interrupted write left behind."""
    head, _, tag = name.rpartition(PARTIAL_WRITE_INFIX)
    return bool(head) and _PARTIAL_WRITE_TAG.fullmatch(tag) is not None


def entry_bytes(entry: Path) -> int:
    """Return the bytes a cache entry occupies.

    An entry is a file, or a directory holding the blobs of one value; either
    one that cannot be read counts as nothing.
    """
    if not _is_directory(entry):
        return _file_bytes(entry)
    total = 0
    for dirpath, _dirnames, filenames in os.walk(
        entry, onerror=_log_walk_error
    ):
        total += sum(_file_bytes(Path(dirpath) / name) for name in filenames)
    return total


def _delete_block_entries(
    block: Path, keys: set[str], *, dry_run: bool
) -> CacheDirStats:
    """Delete the entries `keys` name from one block directory.

    Raises:
        OSError: If `block` cannot be listed.
    """
    if not _is_directory(block):
        return CacheDirStats()

    index = _index_block(block)
    by_hash: dict[str, list[str]] = {}
    for key in sorted(keys):
        by_hash.setdefault(entry_hash(key), []).append(key)

    freed = CacheDirStats()
    # Entries with the same hash share blobs, even across cache types.
    for key_hash, shared_keys in by_hash.items():
        doomed = {key: index.files_by_key.get(key, []) for key in shared_keys}
        entry_files = {file for files in doomed.values() for file in files}
        blob_dir = block / key_hash
        shared = bool(index.markers_by_hash.get(key_hash, set()) - entry_files)
        has_blobs = (
            not shared
            and key_hash in index.dir_names
            and _is_directory(blob_dir)
        )
        if not entry_files and not has_blobs:
            continue
        entries = sum(bool(files) for files in doomed.values())
        if not entry_files and has_blobs:
            entries = 1
        if dry_run:
            bytes_freed = sum(_file_bytes(file) for file in entry_files)
            bytes_freed += entry_bytes(blob_dir) if has_blobs else 0
        else:
            # Readers must see a cache miss before any blobs disappear.
            bytes_freed = sum(
                _unlink(file)
                for file in sorted(
                    entry_files,
                    key=lambda file: not file.name.endswith(LAZY_ENTRY_SUFFIX),
                )
            )
            remaining = {
                key
                for key, files in doomed.items()
                if any(file.exists() or file.is_symlink() for file in files)
            }
            for key in remaining:
                LOGGER.warning("Could not remove %s from %s.", key, block)
            entries -= len(remaining)
            # A writer can publish a new marker for these blobs meanwhile.
            if (
                has_blobs
                and not remaining
                and not _has_marker(block, key_hash)
            ):
                bytes_freed += _remove_tree(blob_dir)
                if blob_dir.exists():
                    entries = 0
        freed += CacheDirStats(total_bytes=bytes_freed, entries=entries)
    return freed


@dataclass(frozen=True)
class _BlockIndex:
    """One listing of a block directory."""

    files_by_key: dict[str, list[Path]]
    markers_by_hash: dict[str, set[Path]]
    dir_names: frozenset[str]


def _index_block(block: Path) -> _BlockIndex:
    """List `block` once, sorting what it holds by entry key and hash.

    Raises:
        OSError: If `block` cannot be listed.
    """
    files_by_key: dict[str, list[Path]] = {}
    markers_by_hash: dict[str, set[Path]] = {}
    dir_names: set[str] = set()
    for child in block.iterdir():
        if _is_directory(child):
            dir_names.add(child.name)
            continue
        key = entry_key(child.name)
        if key is None:
            continue
        files_by_key.setdefault(key, []).append(child)
        if child.name.endswith(LAZY_ENTRY_SUFFIX):
            markers_by_hash.setdefault(entry_hash(key), set()).add(child)
    return _BlockIndex(files_by_key, markers_by_hash, frozenset(dir_names))


def _has_marker(block: Path, key_hash: str) -> bool:
    """Whether an entry in `block` names the blobs of `key_hash` now."""
    return any(
        (block / f"{prefix}{key_hash}{LAZY_ENTRY_SUFFIX}").exists()
        for prefix in _cache_prefixes()
    )


def holds_entry(cache_dir: Path, block: str, key: str) -> bool:
    """Whether a file on disk still answers to the entry `(block, key)`.

    Raises:
        OSError: If the block cannot be listed.
    """
    if not _names_an_entry(block, key):
        return False
    block_dir = cache_dir / block
    if not _is_directory(block_dir):
        return False
    index = _index_block(block_dir)
    if index.files_by_key.get(key):
        return True
    # Keep orphaned blobs tracked so a failed deletion can be retried.
    key_hash = entry_hash(key)
    return (
        key_hash in index.dir_names
        and _is_directory(block_dir / key_hash)
        and key_hash not in index.markers_by_hash
    )


def _entry_keys(block: Path) -> set[str]:
    """The keys of the entry files in `block`."""
    return {
        key
        for child in _children(block)
        if not _is_directory(child)
        and (key := entry_key(child.name)) is not None
    }


def entry_key(name: str) -> str | None:
    """Return the key of the entry file `name`, or `None` for any other file.

    An entry is a key, a dot, and the suffix of the loader that wrote it. A
    write in flight, and the sibling a killed write leaves behind, are not
    entries.
    """
    key, dot, suffix = name.partition(".")
    if dot and suffix in _ENTRY_SUFFIXES and _is_entry_key(key):
        return key
    return None


def _names_an_entry(block: str, key: str) -> bool:
    """Reject names that can escape the cache or name unrelated files."""
    return block == block_dir_name(block) and _is_entry_key(key)


def _is_entry_key(key: str) -> bool:
    """Whether `key` is spelled as a cache write spells one."""
    digest = key[2:]
    return (
        key[:2] in _cache_prefixes()
        and _DIGEST.fullmatch(digest) is not None
        and len(digest) % 4 != 1
    )


def _cache_prefixes() -> Collection[str]:
    # The stores import this module, so the cache types are imported here.
    from marimo._save.cache import CACHE_PREFIX

    return CACHE_PREFIX.values()


def _entry_files(children: list[Path], key: str) -> list[Path]:
    """The files holding entry `key`, the leftovers of a killed write too."""
    return [
        child
        for child in children
        if not _is_directory(child)
        and (child.name == key or child.name.startswith(f"{key}."))
    ]


def _unlink(path: Path) -> int:
    """Remove one file, returning the bytes that freed."""
    size = _file_bytes(path)
    try:
        path.unlink()
    except FileNotFoundError:
        return 0
    except OSError as e:
        LOGGER.warning("Could not remove %s: %s", path, e)
        return 0
    return size


def _remove_tree(directory: Path) -> int:
    """Remove a directory and everything in it, returning the bytes freed."""
    held = entry_bytes(directory)
    shutil.rmtree(directory, ignore_errors=True)
    if not directory.exists():
        return held
    LOGGER.warning("Could not remove %s", directory)
    return max(held - entry_bytes(directory), 0)


def _block_stats(block: Path) -> CacheDirStats:
    """Return the bytes and entry count of one block directory."""
    children = _children(block)
    # A value stored in pieces leaves an entry file next to a directory of
    # blobs named after the same hash. Counting that pair once keeps an entry
    # equal to a cached value.
    hashes = {
        entry_hash(child.name)
        for child in children
        if not _is_directory(child) and not is_partial_write(child.name)
    }
    total_bytes = 0
    entries = 0
    for child in children:
        total_bytes += entry_bytes(child)
        if is_partial_write(child.name):
            continue
        if not (_is_directory(child) and child.name in hashes):
            entries += 1
    return CacheDirStats(total_bytes=total_bytes, entries=entries)


def entry_hash(entry_name: str) -> str:
    """Return the hash an entry file names, without its prefix or suffix.

    A directory of blobs is named by this hash alone.
    """
    stem = entry_name.split(".", 1)[0]
    if len(stem) > 2 and stem[1] == "_":
        return stem[2:]
    return stem


def _is_directory(path: Path) -> bool:
    # A symlinked directory is never descended into: it is measured as the
    # link it is.
    return path.is_dir() and not path.is_symlink()


def _children(directory: Path) -> list[Path]:
    try:
        return list(directory.iterdir())
    except OSError as e:
        LOGGER.warning("Skipping %s: %s", directory, e)
        return []


def _file_bytes(path: Path) -> int:
    try:
        # lstat: a symlink counts as itself, so a link out of the cache is not
        # reported as space the cache holds.
        return path.lstat().st_size
    except FileNotFoundError:
        # A running kernel writes and replaces entries underneath the walk.
        return 0
    except OSError as e:
        LOGGER.warning("Skipping %s: %s", path, e)
        return 0


def _walk_cache_dirs(root: Path) -> list[Path]:
    # Normalize first: the search recognizes a cache directory by the names of
    # its own path components, which a relative path such as "." lacks.
    root = normalize_path(root)
    found = set(_cache_dirs_under(root))
    # sys.pycache_prefix moves caches out of the tree they belong to, so the
    # mirrored copy of `root` holds the caches written for it. Without a
    # prefix the mirror is `root` itself.
    mirrored = notebook_output_dir(root).parent
    if mirrored != root and mirrored.is_dir():
        found.update(_cache_dirs_under(mirrored))
    return sorted(found)


def _is_cache_dir(path: Path) -> bool:
    return path.name == CACHE_DIR_NAME and path.parent.name == MARIMO_DIR_NAME


def _cache_dirs_under(root: Path) -> Iterator[Path]:
    """Yield the existing cache directories at or below `root`."""
    if _is_cache_dir(root):
        yield root
        return
    for dirpath, dirnames, _filenames in os.walk(
        root, onerror=_log_walk_error
    ):
        dirnames[:] = [name for name in dirnames if not name.startswith(".")]
        if Path(dirpath).name != MARIMO_DIR_NAME:
            continue
        if CACHE_DIR_NAME in dirnames:
            # A cache directory holds no nested cache directories, and can be
            # large.
            dirnames.remove(CACHE_DIR_NAME)
            found = Path(dirpath) / CACHE_DIR_NAME
            # A link leads out of the tree that was asked about.
            if found.is_symlink():
                LOGGER.warning("Skipping %s: it is a symbolic link.", found)
                continue
            yield found


def _log_walk_error(error: OSError) -> None:
    # os.walk swallows these by default, and an unreadable subtree then
    # reads as holding no caches.
    LOGGER.warning("Skipping %s: %s", error.filename, error)


def _validate_notebook(path: Path) -> None:
    from marimo._ast.load import get_notebook_status

    try:
        status = get_notebook_status(str(path)).status
    except Exception as e:
        # Keep the cause in the message. Only the message reaches the CLI,
        # and the cause holds what actually went wrong, such as the list of
        # extensions marimo can read.
        raise NotANotebookError(f"{path} is not a marimo notebook: {e}") from e
    if status not in _NOTEBOOK_STATUSES:
        raise NotANotebookError(f"{path} is not a marimo notebook.")
