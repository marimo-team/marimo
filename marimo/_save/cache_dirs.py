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
    from collections.abc import Collection, Iterator

LOGGER = _loggers.marimo_logger()

CACHE_DIR_NAME = "cache"

# A value too large to inline is split over a directory of blobs and described
# by an entry of this suffix, written last. The entry existing is the only
# evidence that the blobs beside it are complete.
LAZY_ENTRY_SUFFIX = ".jsonl"

# Windows rejects most punctuation in a path component.
_UNSAFE_IN_BLOCK_NAME = re.compile(r"[^a-zA-Z0-9 _-]")

# A key is a one-letter cache-type prefix, an underscore, and a url-safe
# base64 digest. Without the prefix a name could be a directory of blobs.
_ENTRY_KEY = re.compile(r"[A-Z]_[A-Za-z0-9_-]+")

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

    A notebook file resolves to the single cache directory beside it. A
    directory resolves to the cache directory for a notebook run there.
    Both are listed whether or not they exist yet, so a caller can report
    an absent cache rather than nothing at all.

    With `recursive`, a directory is instead searched for existing
    `__marimo__/cache` directories, skipping dot-folders. The search can
    come back empty.

    Either way a directory that is itself a cache directory resolves to
    itself, so the output of one call can be fed back into another.

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
        """What `self` holds over `other`, and never less than nothing.

        A deletion is measured as what a directory held before less what it
        holds after. If a kernel writes into the directory meanwhile, an
        unclamped difference reports a negative amount freed.
        """
        return CacheDirStats(
            total_bytes=max(self.total_bytes - other.total_bytes, 0),
            entries=max(self.entries - other.entries, 0),
        )


def cache_dir_stats(cache_dir: Path) -> CacheDirStats:
    """Return the bytes and entry count held by `cache_dir`.

    An entry is one cached value. It is a file in a block directory, together
    with the directory of blobs that a value too large to inline is split
    over.
    Files at the root of the cache directory, such as manifests, hold no
    cached value and so add bytes without adding entries.

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


def cache_entry_keys(cache_dir: Path) -> set[tuple[str, str]]:
    """Return the `(block, key)` entries `cache_dir` holds.

    A key names an entry without its suffix, as in `C_ab12`, which is how a
    manifest records it. A directory of blobs is named by the entry that reads
    it rather than by itself, and the leftovers of a killed write name no
    entry at all.
    """
    keys: set[tuple[str, str]] = set()
    for block in _children(cache_dir):
        if not _is_directory(block):
            continue
        for child in _children(block):
            if _is_directory(child) or is_partial_write(child.name):
                continue
            keys.add((block.name, child.name.split(".", 1)[0]))
    return keys


def is_marimo_notebook(path: Path) -> bool:
    """Whether marimo reads `path` as a notebook."""
    try:
        _validate_notebook(path)
    except NotANotebookError:
        return False
    return True


def block_dir_name(name: str) -> str:
    """Return the directory a cache block called `name` is written to.

    A block is named by whoever writes the cache, so the name can hold
    anything a path component cannot. Stars around a name keep it from
    shadowing another and are dropped, as the loader drops them.
    """
    return _UNSAFE_IN_BLOCK_NAME.sub("_", name.strip("*"))


def clean_cache_dir(
    cache_dir: Path,
    names: Collection[str] | None = None,
    *,
    dry_run: bool = False,
) -> CacheDirStats:
    """Delete whole blocks from `cache_dir`, reporting what that freed.

    `names` are the names given to `mo.persistent_cache`. An empty `names`
    deletes every block. A block goes with the blobs it holds. Files at the
    root of the cache directory describe the cache rather than holding a
    cached value, so a manifest outlives the entries it lists.

    With `dry_run`, nothing is deleted and the report says what deleting
    frees.
    """
    if not cache_dir.is_dir():
        return CacheDirStats()

    wanted = {block_dir_name(name) for name in names} if names else None
    freed = CacheDirStats()
    for block in _children(cache_dir):
        if not _is_directory(block):
            continue
        if wanted is not None and block.name not in wanted:
            continue
        if not _holds_entries(block):
            LOGGER.warning("Skipping %s: it holds no cache entries.", block)
            continue
        held = _block_stats(block)
        if dry_run:
            freed += held
            continue
        _remove_tree(block)
        freed += held - _remaining_stats(block)
    return freed


def delete_cache_entries(
    cache_dir: Path,
    entries: Collection[tuple[str, str]],
    *,
    dry_run: bool = False,
) -> CacheDirStats:
    """Delete the `(block, key)` entries named, reporting what that freed.

    A key names an entry without its suffix, as in `C_ab12`. Everything else
    the cache directory holds stays, including a directory of blobs that an
    entry outside `entries` still names.

    Entries come from a manifest, a file that travels with the cache, so
    anything can have written them. A pair that no cache write can produce
    is reported and skipped, and no deletion reaches past `cache_dir`.

    With `dry_run`, nothing is deleted and the report says what deleting
    frees.
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
    """Delete the entries `keys` name from one block directory."""
    if not _is_directory(block):
        return CacheDirStats()

    children = _children(block)
    doomed = {key: _entry_files(children, key) for key in keys}
    # A directory of blobs is named after a hash, which more than one entry
    # can name. Reading it needs an entry that says the blobs are complete, so
    # one left behind by a surviving entry keeps the blobs alive.
    going = {file for files in doomed.values() for file in files}
    attested = {
        entry_hash(child.name)
        for child in children
        if child.name.endswith(LAZY_ENTRY_SUFFIX) and child not in going
    }

    freed = CacheDirStats()
    # Blobs several doomed entries name are freed by whichever is reached
    # first. Charging them twice promises more than deleting can free.
    taken: set[str] = set()
    for key in sorted(keys):
        entry_files = doomed[key]
        key_hash = entry_hash(key)
        blob_dir = block / key_hash
        blobs: Path | None = None
        if (
            key_hash not in attested
            and key_hash not in taken
            and _is_directory(blob_dir)
        ):
            blobs = blob_dir
            taken.add(key_hash)
        if not entry_files and blobs is None:
            continue
        if dry_run:
            bytes_freed = sum(_file_bytes(file) for file in entry_files)
            bytes_freed += entry_bytes(blobs) if blobs is not None else 0
        else:
            # The completeness marker goes first: a reader arriving mid-delete
            # then misses the entry instead of reading half of it.
            bytes_freed = sum(
                _unlink(file) for file in _marker_first(entry_files)
            )
            if any(file.exists() for file in entry_files):
                # An entry that stays can still be read, so the blobs it
                # names stay with it, and it does not count as gone.
                LOGGER.warning("Could not remove %s from %s.", key, block)
                freed += CacheDirStats(total_bytes=bytes_freed)
                continue
            bytes_freed += _remove_tree(blobs) if blobs is not None else 0
        freed += CacheDirStats(total_bytes=bytes_freed, entries=1)
    return freed


def _holds_entries(block: Path) -> bool:
    """Whether `block` holds a cache entry, or nothing at all.

    A `save_path` in the configuration can point the cache at a directory
    that is not one. Its subdirectories are then not blocks, and deleting
    them would take a project with them.
    """
    children = _children(block)
    return not children or any(
        not _is_directory(child)
        and _ENTRY_KEY.fullmatch(child.name.split(".", 1)[0]) is not None
        for child in children
    )


def _names_an_entry(block: str, key: str) -> bool:
    """Whether `(block, key)` names an entry the cache can hold.

    Both are one path component of the character set a cache write is
    restricted to, which keeps them from reaching out of the cache
    directory or naming a directory the cache does not own.
    """
    return (
        bool(block)
        and block == block_dir_name(block)
        and _ENTRY_KEY.fullmatch(key) is not None
    )


def _entry_files(children: list[Path], key: str) -> list[Path]:
    """The files holding entry `key`, the leftovers of a killed write too."""
    return [
        child
        for child in children
        if not _is_directory(child)
        and (child.name == key or child.name.startswith(f"{key}."))
    ]


def _marker_first(entry_files: list[Path]) -> list[Path]:
    return sorted(
        entry_files,
        key=lambda file: not file.name.endswith(LAZY_ENTRY_SUFFIX),
    )


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
    return held - entry_bytes(directory)


def _remaining_stats(block: Path) -> CacheDirStats:
    return _block_stats(block) if block.exists() else CacheDirStats()


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
            yield Path(dirpath) / CACHE_DIR_NAME


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
