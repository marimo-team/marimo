# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import abc
import inspect
import re
from collections import namedtuple
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Optional, get_args

from marimo._plugins.ui._core.ui_element import UIElement
from marimo._runtime.context import ContextNotInitializedError, get_context
from marimo._runtime.state import SetFunctor
from marimo._save.stubs import (
    CUSTOM_STUBS,
    CustomStub,
    FunctionStub,
    ModuleStub,
    UIElementStub,
    maybe_register_stub,
)

# Many assertions are for typing and should always pass. This message is a
# catch all to motive users to report if something does fail.
UNEXPECTED_FAILURE_BOILERPLATE = (
    "— this is"
    " unexpected and is likely a bug in marimo. "
    "Please file an issue at "
    "https://github.com/marimo-team/marimo/issues"
)


if TYPE_CHECKING:
    from marimo._ast.visitor import Name
    from marimo._runtime.state import State
    from marimo._save.hash import HashKey
    from marimo._save.loaders import Loader

# NB. Increment on cache breaking changes.
MARIMO_CACHE_VERSION: int = 3

CacheType = Literal[
    "ContextExecutionPath",
    "ContentAddressed",
    "ExecutionPath",
    "Pure",
    "Deferred",
    "Unknown",
]
# Easy visual identification of cache type.
CACHE_PREFIX: dict[CacheType, str] = {
    "ContextExecutionPath": "X_",
    "ContentAddressed": "C_",
    "ExecutionPath": "E_",
    "Pure": "P_",
    "Deferred": "D_",
    "Unknown": "U_",
}

ValidCacheSha = namedtuple("ValidCacheSha", ("sha", "cache_type"))
MetaKey = Literal["return", "version", "runtime"]
# Matches functools
CacheInfo = namedtuple(
    "CacheInfo", ["hits", "misses", "maxsize", "currsize", "time_saved"]
)


# BaseException because "raise _ as e" is utilized.
class CacheException(BaseException):
    pass


@dataclass
class Cache:
    defs: dict[Name, Any]
    hash: str
    cache_type: CacheType
    stateful_refs: set[str]
    hit: bool
    # meta corresponds to internally used data, kept as a dictionary to allow
    # for backwards pickle compatibility with future entries.
    # TODO: Utilize to store code and output in cache.
    # TODO: Consider storing graph information such that execution history can
    # be explored and visualized.
    meta: dict[MetaKey, Any]

    def restore(self, scope: dict[str, Any]) -> None:
        """Restores values from cache, into scope."""
        memo: dict[int, Any] = {}  # Track processed objects to handle cycles
        for var, lookup in self.contextual_defs():
            value = self.defs.get(var, None)
            scope[lookup] = self._restore_from_stub_if_needed(
                value, scope, memo
            )

        for key, value in self.meta.items():
            self.meta[key] = self._restore_from_stub_if_needed(
                value, scope, memo
            )

        defs = {**globals(), **scope}
        for ref in self.stateful_refs:
            if ref not in defs:
                raise CacheException(
                    "Failure while restoring cached values. "
                    "Cache expected a reference to a "
                    f"variable that is not present ({ref})."
                )
            value = defs[ref]
            if isinstance(value, SetFunctor):
                value(self.defs[ref])
            # UI Values cannot be easily programmatically set, so only update
            # state values.
            elif not isinstance(value, UIElement):
                raise CacheException(
                    "Failure while restoring cached values. "
                    "Unexpected stateful reference type "
                    f"({type(ref)}:{ref})."
                )

    def _restore_from_stub_if_needed(
        self,
        value: Any,
        scope: dict[str, Any],
        memo: dict[int, Any] | None = None,
    ) -> Any:
        """Restore objects from stubs if needed, recursively handling collections."""
        if memo is None:
            memo = {}

        # Check for cycles
        obj_id = id(value)
        if obj_id in memo:
            return memo[obj_id]

        if isinstance(value, ModuleStub):
            result = value.load()
        elif isinstance(value, FunctionStub):
            result = value.load(scope)
        elif isinstance(value, UIElementStub):
            result = value.load()
        elif isinstance(value, tuple):
            result = tuple(
                self._restore_from_stub_if_needed(item, scope, memo)
                for item in value
            )
        elif isinstance(value, set):
            # Sets cannot be recursive (require hashable items), but keep the
            # reference.
            result = set(
                self._restore_from_stub_if_needed(item, scope, memo)
                for item in value
            )
            value.clear()
            value.update(result)
            result = value
        elif isinstance(value, list):
            memo[obj_id] = value
            result = [
                self._restore_from_stub_if_needed(item, scope, memo)
                for item in value
            ]
            # Keep the original list reference
            value.clear()
            value.extend(result)
            result = value
        elif isinstance(value, dict):
            memo[obj_id] = value
            result = {}
            for k, v in value.items():
                result[k] = self._restore_from_stub_if_needed(v, scope, memo)
            value.clear()
            value.update(result)
            result = value
        elif isinstance(value, CustomStub):
            # CustomStub is a placeholder for a custom type, which cannot be
            # restored directly.
            result = value.load(scope)
        else:
            result = value

        memo[obj_id] = result
        return result

    def update(
        self,
        scope: dict[str, Any],
        meta: Optional[dict[MetaKey, Any]] = None,
        preserve_pointers: bool = True,
    ) -> None:
        """Loads values from scope, updating the cache."""
        for var, lookup in self.contextual_defs():
            if lookup not in scope:
                raise CacheException(
                    "Failure while saving cached values. "
                    "Cache expected a reference to a "
                    f"variable that is not present ({lookup})."
                )
            self.defs[var] = scope[lookup]

        self.meta = {}
        if meta is not None:
            for metakey, metavalue in meta.items():
                if metakey not in get_args(MetaKey):
                    raise CacheException(f"Unexpected meta key: {metakey}")
                self.meta[metakey] = metavalue
        self.meta["version"] = MARIMO_CACHE_VERSION

        defs = {**globals(), **scope}
        for ref in self.stateful_refs:
            if ref not in defs:
                raise CacheException(
                    "Failure while saving cached values. "
                    "Cache expected a reference to a "
                    f"variable that is not present ({ref})."
                )
            value = defs[ref]
            if isinstance(value, SetFunctor):
                self.defs[ref] = value._state()
            elif isinstance(value, UIElement):
                self.defs[ref] = value.value
            else:
                raise CacheException(
                    "Failure while saving cached values. "
                    "Unexpected stateful reference type "
                    f"({type(value)}:{ref})."
                )

        # Convert objects to stubs in both defs and meta
        memo: dict[int, Any] = {}  # Track processed objects to handle cycles
        for key, value in self.defs.items():
            self.defs[key] = self._convert_to_stub_if_needed(
                value, memo, preserve_pointers
            )

        for key, value in self.meta.items():
            self.meta[key] = self._convert_to_stub_if_needed(
                value, memo, preserve_pointers
            )

    def _convert_to_stub_if_needed(
        self,
        value: Any,
        memo: dict[int, Any] | None = None,
        preserve_pointers: bool = True,
    ) -> Any:
        """Convert objects to stubs if needed, recursively handling collections.

        Args:
            value: The value to convert
            memo: Memoization dict to handle cycles
            preserve_pointers: If True, modifies containers in-place to preserve
                             object identity. If False, creates new containers.
        """
        if memo is None:
            memo = {}

        # Check for cycles
        obj_id = id(value)
        if obj_id in memo:
            return memo[obj_id]

        result: Any = None

        if inspect.ismodule(value):
            result = ModuleStub(value)
        elif inspect.isfunction(value):
            result = FunctionStub(value)
        elif isinstance(value, UIElement):
            result = UIElementStub(value)
        elif isinstance(value, tuple):
            # tuples are immutable and cannot be recursive, but we still want to
            # iteratively convert the internal items.
            result = tuple(
                self._convert_to_stub_if_needed(item, memo, preserve_pointers)
                for item in value
            )
        elif isinstance(value, set):
            # sets cannot be recursive (require hashable items)
            converted = set(
                self._convert_to_stub_if_needed(item, memo, preserve_pointers)
                for item in value
            )
            if preserve_pointers:
                value.clear()
                value.update(converted)
                result = value
            else:
                result = converted
        elif isinstance(value, list):
            if preserve_pointers:
                # Preserve original list reference
                memo[obj_id] = value
                converted_list = [
                    self._convert_to_stub_if_needed(
                        item, memo, preserve_pointers
                    )
                    for item in value
                ]
                value.clear()
                value.extend(converted_list)
                result = value
            else:
                # Create new list
                result = []
                memo[obj_id] = result
                result.extend(
                    [
                        self._convert_to_stub_if_needed(
                            item, memo, preserve_pointers
                        )
                        for item in value
                    ]
                )
        elif isinstance(value, dict):
            if preserve_pointers:
                # Preserve original dict reference
                memo[obj_id] = value
                converted_dict = {
                    k: self._convert_to_stub_if_needed(
                        v, memo, preserve_pointers
                    )
                    for k, v in value.items()
                }
                value.clear()
                value.update(converted_dict)
                result = value
            else:
                # Create new dict
                result = {}
                memo[obj_id] = result
                result.update(
                    {
                        k: self._convert_to_stub_if_needed(
                            v, memo, preserve_pointers
                        )
                        for k, v in value.items()
                    }
                )
        elif type(value) in CUSTOM_STUBS or maybe_register_stub(value):
            result = CUSTOM_STUBS[type(value)](value)
        else:
            result = value

        memo[obj_id] = result

        return result

    def contextual_defs(self) -> dict[tuple[Name, Name], Any]:
        """Uses context to resolve private variable names."""
        try:
            context = get_context().execution_context
            assert context is not None, "Context could not be resolved"
            private_prefix = f"_cell_{context.cell_id}_"
        except (ContextNotInitializedError, AssertionError):
            private_prefix = r"_"

        return {
            (var, re.sub(r"^_", private_prefix, var)): value
            for var, value in self.defs.items()
            if var not in self.stateful_refs
        }

    @property
    def key(self) -> HashKey:
        from marimo._save.hash import HashKey

        return HashKey(hash=self.hash, cache_type=self.cache_type)

    @classmethod
    def empty(
        cls, *, key: HashKey, defs: set[str], stateful_refs: set[str]
    ) -> Cache:
        return Cache(
            defs={d: None for d in defs},
            hash=key.hash,
            cache_type=key.cache_type,
            stateful_refs=stateful_refs,
            hit=False,
            meta={},
        )

    @classmethod
    def new(
        cls, *, loaded: Cache, key: HashKey, stateful_refs: set[str]
    ) -> Cache:
        return Cache(
            defs=loaded.defs,
            hash=key.hash,
            cache_type=key.cache_type,
            stateful_refs=stateful_refs,
            hit=True,
            meta=loaded.meta,
        )


class CacheContext(abc.ABC):
    """Tracks cache loader state and statistics.
    Base class for cache interfaces."""

    __slots__ = "_loader"
    _loader: Optional[State[Loader]]

    # Match functools api
    def cache_info(self) -> CacheInfo:
        return CacheInfo(
            hits=self.hits,
            misses=self.misses,
            maxsize=self.maxsize,
            currsize=self.currsize,
            time_saved=self.time_saved,
        )

    @property
    def loader(self) -> Loader:
        assert self._loader is not None, UNEXPECTED_FAILURE_BOILERPLATE
        return self._loader()

    def cache_clear(self) -> None:
        if self._loader is not None:
            self.loader.clear()

    @property
    def hits(self) -> int:
        if self._loader is None:
            return 0
        return self.loader.hits

    @property
    def misses(self) -> int:
        # Not something explicitly recorded.
        return 0

    @property
    def maxsize(self) -> int | None:
        if self._loader is None:
            return None
        maxsize = getattr(self.loader, "_max_size", -1)
        if maxsize < 0:
            return None
        return maxsize

    @property
    def currsize(self) -> int:
        if self._loader is None:
            return 0
        # Use current_size if available, otherwise fall back to misses
        if hasattr(self.loader, "current_size"):
            return int(self.loader.current_size)
        # Assume all misses leave an entry
        return self.misses

    @property
    def time_saved(self) -> float:
        if self._loader is None:
            return 0.0
        return self.loader.time_saved

    @property
    @abc.abstractmethod
    def last_hash(self) -> Optional[str]:
        """Last computed cache hash, if available."""

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} hits={self.hits} "
            f"misses={self.misses} maxsize={self.maxsize} "
            f"currsize={self.currsize} time_saved={self.time_saved:.4f}s "
            f"last_hash={self.last_hash}>"
        )
