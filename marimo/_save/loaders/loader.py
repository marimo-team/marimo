# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

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
        self.message = "\n".join([message, INCONSISTENT_CACHE_BOILER_PLATE])
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
        self.name = name
        self._hits = 0

    def build_path(self, key: HashKey) -> Path:
        prefix = CACHE_PREFIX.get(key.cache_type, "U_")
        return Path(f"{prefix}{key.hash}")

    def cache_attempt(
        self,
        defs: set[Name],
        key: HashKey,
        stateful_refs: set[Name],
    ) -> Cache:
        loaded = self.load_cache(key)
        if not loaded:
            return Cache.empty(defs=defs, key=key, stateful_refs=stateful_refs)
        # TODO: Consider more robust verification
        if loaded.hash != key.hash:
            raise LoaderError("Hash mismatch in loaded cache.")
        if (defs | stateful_refs) != set(loaded.defs):
            raise LoaderError("Variable mismatch in loaded cache.")
        self._hits += 1
        return Cache.new(
            loaded=loaded,
            key=key,
            stateful_refs=stateful_refs,
        )

    @property
    def hits(self) -> int:
        return self._hits

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
    def load_cache(self, key: HashKey) -> Optional[Cache]:
        """Load Cache"""

    @abstractmethod
    def save_cache(self, cache: Cache) -> bool:
        """Save Cache"""


class BasePersistenceLoader(Loader):
    """Abstract base for cache written to disk."""

    def __init__(
        self,
        name: str,
        suffix: str,
        store: Optional[Store] = None,
    ) -> None:
        super().__init__(name)

        if store is not None:
            self.store = store
        else:
            try:
                self.store = get_context().cache_store
            except ContextNotInitializedError:
                self.store = DEFAULT_STORE()

        self.name = name
        self.suffix = suffix

    def build_path(self, key: HashKey) -> Path:
        prefix = CACHE_PREFIX.get(key.cache_type, "U_")
        return Path(self.name) / f"{prefix}{key.hash}.{self.suffix}"

    def cache_hit(self, key: HashKey) -> bool:
        return self.store.hit(str(self.build_path(key)))

    def save_cache(self, cache: Cache) -> bool:
        blob = self.to_blob(cache)
        if blob is None:
            return False
        return self.store.put(str(self.build_path(cache.key)), blob)

    def load_cache(self, key: HashKey) -> Optional[Cache]:
        try:
            blob: Optional[bytes] = self.store.get(str(self.build_path(key)))
            if not blob:
                return None
            return self.restore_cache(key, blob)
        except FileNotFoundError as e:
            raise LoaderError("Unexpected cache miss.") from e

    @abstractmethod
    def restore_cache(self, key: HashKey, blob: bytes) -> Cache:
        """May throw FileNotFoundError"""

    @abstractmethod
    def to_blob(self, cache: Cache) -> Optional[bytes]:
        """Convert cache to bytes"""


LoaderType = type[Loader]
