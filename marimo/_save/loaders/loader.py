# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

from marimo._runtime.context import get_context
from marimo._runtime.context.types import ContextNotInitializedError
from marimo._runtime.state import State
from marimo._save.cache import (
    CACHE_PREFIX,
    Cache,
)
from marimo._save.stores import DEFAULT_STORE, Store

if TYPE_CHECKING:
    from marimo._ast.visitor import Name
    from marimo._save.hash import HashKey

INCONSISTENT_CACHE_BOILER_PLATE = (
    "The cache state does not match "
    "expectations, this can be due to file "
    "corruption or an incompatible marimo "
    "version. Alternatively, this may be a bug"
    " in marimo. Please file an issue at "
    "github.com/marimo-team/marimo/issues"
)


class LoaderError(BaseException):
    """Base exception such that it can be raised as context for other errors."""

    def __init__(self, message: str) -> None:
        self.message = f"{message}\n{INCONSISTENT_CACHE_BOILER_PLATE}"
        super().__init__(message)


class LoaderPartial:
    """Cache implementation sometimes requires a deferred construction.
    Moreover, for a cache persistence, we utilize the state registry to store
    the loader such that the loader object is not actually reconstructed if it
    does not need to be.
    """

    def __init__(self, loader_type: type[Loader], **kwargs: Any) -> None:
        self.loader_type = loader_type
        self.kwargs = kwargs

    def __call__(self, name: str) -> Loader:
        try:
            return self.loader_type(name, **self.kwargs)
        except TypeError as e:
            raise TypeError(
                f"Could not create {self.loader_type} from the construction "
                f"arguments: [{', '.join(self.kwargs.keys())}]. Consider "
                "setting these arguments explicitly with "
                f"{self.loader_type}.partial(needed_arg=value)."
            ) from e

    def create_or_reconfigure(
        self, name: str, context: str = "cache_partial"
    ) -> State[Loader]:
        try:
            ctx = get_context()
        except ContextNotInitializedError:
            return State(self(name), _name=name, _context=context)
        if ctx.state_registry is None:
            return State(self(name), _name=name, _context=context)

        loader_state: State[Loader] | None = ctx.state_registry.lookup(
            name, context=context
        )
        if loader_state is None:
            # There's a chance it's in the registry, but the reference is None.
            # Delete the reference just in case, otherwise GC won't hold on to
            # this instance either.
            ctx.state_registry.delete(name, context=context)
            loader = self(name)
            # State creation automatically registers itself.
            return State(loader, _name=name, _context=context)
        else:
            loader = loader_state()
            if isinstance(loader, self.loader_type):
                # Manually set the attributes of the old loader.
                # Overriding attr.setter is useful for
                # managed behavior.
                for key, value in self.kwargs.items():
                    setattr(loader, key, value)
            else:
                loader = self(name)
                # Replace the previous loader with the new construction.
                loader_state._set_value(loader)
        return loader_state


class Loader(ABC):
    """Loaders are responsible for saving and loading persistent caches.

    Loaders are provided a name, a save path and a cache key or "hash", which
    should be deterministically determined given the notebook context.

    In the future, they may be specialized for different types of data (such as
    numpy or pandas dataframes), or remote storage (such as S3 or marimo
    cloud).
    """

    def __init__(self, name: str) -> None:
        # Remove * since used to prevent shadowing in scoped cases.
        self.name = name.strip("*")
        self._hits = 0
        self._time_saved = 0.0

    def build_path(self, key: HashKey) -> Path:
        prefix = CACHE_PREFIX.get(key.cache_type, "U_")
        return Path(f"{prefix}{key.hash}")

    def flush(self) -> None:
        """Drain any pending asynchronous writes so results are durable.

        No-op by default; backends that dispatch writes to background threads
        (e.g. the lazy loader) override this to join them before shutdown.
        """
        return

    def cache_attempt(
        self,
        defs: set[Name],
        key: HashKey,
        stateful_refs: set[Name],
        glbls: dict[str, Any] | None = None,
    ) -> Cache:
        start_time = time.time()
        loaded = self.load_cache(key, glbls=glbls)
        if not loaded:
            return Cache.empty(defs=defs, key=key, stateful_refs=stateful_refs)
        load_time = time.time() - start_time

        # TODO: Consider more robust verification
        if loaded.hash != key.hash:
            raise LoaderError("Hash mismatch in loaded cache.")
        if (defs | stateful_refs) != set(loaded.defs):
            raise LoaderError("Variable mismatch in loaded cache.")
        self._hits += 1

        # Track time savings: original runtime - time to load from cache
        runtime = loaded.meta.get("runtime", 0)
        if runtime > 0:
            time_saved = runtime - load_time
            self._time_saved += max(0, time_saved)

        return Cache.new(
            loaded=loaded,
            key=key,
            stateful_refs=stateful_refs,
        )

    @property
    def hits(self) -> int:
        return self._hits

    @property
    def time_saved(self) -> float:
        return self._time_saved

    @classmethod
    def partial(cls, **kwargs: Any) -> LoaderPartial:
        return LoaderPartial(cls, **kwargs)

    @classmethod
    def cache(cls, *args: Any, **kwargs: Any) -> Any:
        """General `mo.cache` api for this loader"""
        from marimo._save.save import cache

        return cache(*args, loader=cls, **kwargs)  # type: ignore

    @abstractmethod
    def cache_hit(self, key: HashKey) -> bool:
        """Check if cache has been hit given a result hash.

        Args:
            key: The hash of the result context, and the hash type, and the
            execution hash.

        Returns:
            bool: Whether the cache has been hit
        """

    @abstractmethod
    def load_cache(
        self,
        key: HashKey,
        glbls: dict[str, Any] | None = None,
    ) -> Cache | None:
        """Load Cache. `glbls` is an optional cell namespace used by
        loaders (e.g. `LazyLoader`) that need to resolve
        `__main__`-qualified pickle refs against the live cell scope."""

    @abstractmethod
    def save_cache(self, cache: Cache) -> bool:
        """Save Cache"""

    def clear(self) -> None:
        """Clear all cached items. Default implementation does nothing."""
        # Default implementation: no-op for loaders that don't support clearing
        return

    def storage_dirs(self) -> list[Path]:
        """Cache directories this loader writes its block into.

        Empty when the cache keeps nothing on the local filesystem, so there
        is no disk usage to attribute to it.
        """
        return []

    def clearable_paths(self) -> list[Path]:
        """Files and directories on disk that `clear()` removes."""
        return []

    def clearable_bytes(self) -> int:
        """Bytes on disk that `clear()` frees."""
        return 0


def _files(directory: Path, suffix: str) -> list[Path]:
    """The files directly under `directory` ending in `suffix`."""
    try:
        return [
            child
            for child in directory.iterdir()
            if child.name.endswith(suffix) and child.is_file()
        ]
    except OSError:
        return []


def _subdirectories(directory: Path) -> list[Path]:
    """The directories directly under `directory`, links excluded."""
    try:
        return [
            child
            for child in directory.iterdir()
            if child.is_dir() and not child.is_symlink()
        ]
    except OSError:
        return []


class BasePersistenceLoader(Loader):
    """Abstract base for cache written to disk."""

    def __init__(
        self,
        name: str,
        suffix: str,
        store: Store | None = None,
    ) -> None:
        super().__init__(name)

        if store is not None:
            self.store = store
        else:
            try:
                self.store = get_context().cache.store
            except ContextNotInitializedError:
                self.store = DEFAULT_STORE()

        from marimo._save.cache_dirs import block_dir_name

        self.name = block_dir_name(self.name)
        self.suffix = suffix

    def build_path(self, key: HashKey) -> Path:
        prefix = CACHE_PREFIX.get(key.cache_type, "U_")
        return Path(self.name) / f"{prefix}{key.hash}.{self.suffix}"

    def cache_hit(self, key: HashKey) -> bool:
        return self.store.hit(str(self.build_path(key)))

    def mark_stale(self, manifest_key: str) -> None:
        """Force a manifest to miss for the rest of the session.

        No-op by default; loaders with a session-scoped store override this to
        record the key as stale.
        """

    def save_cache(self, cache: Cache) -> bool:
        blob = self.to_blob(cache)
        if blob is None:
            return False
        return self.store.put(str(self.build_path(cache.key)), blob)

    def load_cache(
        self,
        key: HashKey,
        glbls: dict[str, Any] | None = None,
    ) -> Cache | None:
        del glbls  # Base persistence loader doesn't need a cell namespace.
        try:
            blob: bytes | None = self.store.get(str(self.build_path(key)))
            if not blob:
                return None
            return self.restore_cache(key, blob)
        except FileNotFoundError as e:
            raise LoaderError("Unexpected cache miss.") from e

    def storage_dirs(self) -> list[Path]:
        return self.store.local_dirs()

    def _clearable_root(self) -> Path | None:
        """Root directory `clear()` removes this loader's entry files under.

        `None` unless the store maps every key to a path below a root it
        owns. A remote store holds entries that cannot be enumerated as
        paths.
        """
        return self.store.clearable_root()

    def _clearable_paths(self, root: Path) -> list[Path]:
        """Paths under `root` that `clear()` removes."""
        import glob

        from marimo._save.cache_dirs import (
            LAZY_ENTRY_SUFFIX,
            PARTIAL_WRITE_INFIX,
            entry_hash,
        )

        block = root / self.name
        # The leftovers of an interrupted write hold no value anyone can read,
        # so clearing the block is the last chance to reclaim their bytes.
        patterns = (
            str(block / f"*.{self.suffix}"),
            str(block / f"*.{self.suffix}{PARTIAL_WRITE_INFIX}*"),
        )
        paths = [
            Path(match) for pattern in patterns for match in glob.glob(pattern)
        ]
        # A value too large to inline is split over a directory of blobs
        # named after the same hash as its entry. Removing the entry alone
        # leaves those bytes behind with nothing left that can read them.
        # Only this loader's own hashes are taken: another loader sharing
        # the block name still reads its blobs through its own entries.
        hashes = {entry_hash(path.name) for path in paths}
        # A marker another loader left under the same name and hash still
        # reads those blobs, so they stay with it.
        hashes -= {
            entry_hash(marker.name)
            for marker in _files(block, LAZY_ENTRY_SUFFIX)
            if marker not in paths
        }
        paths.extend(
            child for child in _subdirectories(block) if child.name in hashes
        )
        return paths

    def clear(self) -> None:
        """Clear all cached items for this loader."""
        root = self._clearable_root()
        if root is None:
            return
        for cache_file in self._clearable_paths(root):
            self.store.clear(str(cache_file.relative_to(root)))

    def clearable_paths(self) -> list[Path]:
        root = self._clearable_root()
        return [] if root is None else self._clearable_paths(root)

    def clearable_bytes(self) -> int:
        from marimo._save.cache_dirs import entry_bytes

        return sum(entry_bytes(path) for path in self.clearable_paths())

    @abstractmethod
    def restore_cache(self, key: HashKey, blob: bytes) -> Cache:
        """May throw FileNotFoundError"""

    @abstractmethod
    def to_blob(self, cache: Cache) -> bytes | None:
        """Convert cache to bytes"""


LoaderType = type[Loader]
