# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, Type

from marimo._runtime.context import get_context
from marimo._runtime.context.types import ContextNotInitializedError
from marimo._runtime.runtime import notebook_dir
from marimo._runtime.state import State
from marimo._save.cache import (
    CACHE_PREFIX,
    Cache,
    CacheType,
)

if TYPE_CHECKING:
    from marimo._ast.visitor import Name

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

    def build_path(self, hashed_context: str, cache_type: CacheType) -> Path:
        prefix = CACHE_PREFIX.get(cache_type, "U_")
        return Path(f"{prefix}{hashed_context}")

    def cache_attempt(
        self,
        defs: set[Name],
        hashed_context: str,
        stateful_refs: set[Name],
        cache_type: CacheType,
    ) -> Cache:
        if not self.cache_hit(hashed_context, cache_type):
            return Cache(
                {d: None for d in defs},
                hashed_context,
                stateful_refs,
                cache_type,
                False,
                {},
            )
        loaded = self.load_cache(hashed_context, cache_type)
        # TODO: Consider more robust verification
        if loaded.hash != hashed_context:
            raise LoaderError("Hash mismatch in loaded cache.")
        if (defs | stateful_refs) != set(loaded.defs):
            raise LoaderError("Variable mismatch in loaded cache.")
        self._hits += 1
        return Cache(
            loaded.defs,
            hashed_context,
            stateful_refs,
            cache_type,
            True,  # hit
            loaded.meta,
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
    def cache_hit(self, hashed_context: str, cache_type: CacheType) -> bool:
        """Check if cache has been hit given a result hash.

        Args:
            hashed_context: The hash of the result context
            cache_type: The type of cache to check for

        Returns:
            bool: Whether the cache has been hit
        """

    @abstractmethod
    def load_cache(self, hashed_context: str, cache_type: CacheType) -> Cache:
        """Load Cache"""

    @abstractmethod
    def save_cache(self, cache: Cache) -> None:
        """Save Cache"""


class BasePersistenceLoader(Loader):
    """Abstract base for cache written to disk."""

    def __init__(
        self, name: str, suffix: str, save_path: str | Path | None
    ) -> None:
        super().__init__(name)

        self.name = name
        # Setter takes care of this, not sure why mypy is complaining.
        self.save_path = save_path  # type: ignore
        self.suffix = suffix

    @property
    def save_path(self) -> Path:
        return self._save_path / self.name

    @save_path.setter
    def save_path(self, save_path: str | Path | None) -> None:
        if save_path is None and (root := notebook_dir()) is not None:
            save_path = str(root / "__marimo__" / "cache")
        elif save_path is None:
            # This can happen if the notebook file is unnamed.
            save_path = os.path.join("__marimo__", "cache")
        self._save_path = Path(save_path)
        (self._save_path / self.name).mkdir(parents=True, exist_ok=True)

    def build_path(self, hashed_context: str, cache_type: CacheType) -> Path:
        prefix = CACHE_PREFIX.get(cache_type, "U_")
        return self.save_path / f"{prefix}{hashed_context}.{self.suffix}"

    def cache_hit(self, hashed_context: str, cache_type: CacheType) -> bool:
        path = self.build_path(hashed_context, cache_type)
        return os.path.exists(path) and os.path.getsize(path) > 0

    def load_cache(self, hashed_context: str, cache_type: CacheType) -> Cache:
        try:
            return self.load_persistent_cache(hashed_context, cache_type)
        except FileNotFoundError as e:
            raise LoaderError("Unexpected cache miss.") from e

    @abstractmethod
    def load_persistent_cache(
        self, hashed_context: str, cache_type: CacheType
    ) -> Cache:
        """May throw FileNotFoundError"""


LoaderType = Type[Loader]
