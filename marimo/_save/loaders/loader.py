# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from marimo._runtime.context import get_context
from marimo._runtime.state import State
from marimo._save.cache import CACHE_PREFIX, Cache, CacheType

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


LoaderType = TypeVar("LoaderType", bound="Loader")


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
        ctx = get_context()
        if ctx.state_registry is None:
            return State(self(name), _name=name, _context=context)

        loader_state: State[Loader] | None = ctx.state_registry.lookup(
            name, context=context
        )
        if loader_state is None:
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
        assert loaded.hash == hashed_context, INCONSISTENT_CACHE_BOILER_PLATE
        assert set(defs | stateful_refs) == set(loaded.defs), (
            INCONSISTENT_CACHE_BOILER_PLATE
        )
        self._hits += 1
        return Cache(
            loaded.defs,
            hashed_context,
            stateful_refs,
            cache_type,
            True,
            loaded.meta,
        )

    @property
    def hits(self) -> int:
        return self._hits

    @classmethod
    def partial(cls, **kwargs: Any) -> LoaderPartial:
        return LoaderPartial(cls, **kwargs)

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
