# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import re
from collections import namedtuple
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Optional, get_args

from marimo._plugins.ui._core.ui_element import UIElement
from marimo._runtime.context import ContextNotInitializedError, get_context
from marimo._runtime.state import SetFunctor

if TYPE_CHECKING:
    from marimo._ast.visitor import Name
    from marimo._save.hash import HashKey

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
MetaKey = Literal["return", "version"]


class ModuleStub:
    def __init__(self, module: Any) -> None:
        self.name = module.__name__

    def load(self):
        return __import__(self.name)


class FunctionStub:
    def __init__(self, function: Any) -> None:
        self.code = function.__code__

    def load(self, glbls: dict[str, Any]) -> Any:
        return eval(self.code, glbls)


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
        for var, lookup in self.contextual_defs():
            scope[lookup] = self.defs[var]

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

        for key, value in self.defs.items():
            # If it's a module we must replace with a stub.
            if isinstance(value, ModuleStub):
                scope[key] = value.load()
            elif isinstance(value, FunctionStub):
                value.load(scope)

    def update(
        self,
        scope: dict[str, Any],
        meta: Optional[dict[MetaKey, Any]] = None,
    ) -> None:
        """Loads values from scope, updating the cache."""
        for var, lookup in self.contextual_defs():
            self.defs[var] = scope[lookup]

        self.meta = {}
        if meta is not None:
            for key, value in meta.items():
                if key not in get_args(MetaKey):
                    raise CacheException(f"Unexpected meta key: {key}")
                self.meta[key] = value
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

        for key, value in self.defs.items():
            # If it's a module we must replace with a stub.
            if inspect.ismodule(value):
                self.defs[key] = ModuleStub(value)
            elif inspect.isfunction(value):
                self.defs[key] = FunctionStub(value)

    def contextual_defs(self) -> dict[tuple[Name, Name], Any]:
        """Uses context to resolve private variable names."""
        try:
            context = get_context().execution_context
            assert context is not None, "Context could not be resolved"
            private_prefix = f"_cell_{context.cell_id}_"
        except (ContextNotInitializedError, AssertionError):
            private_prefix = r"^_cell_\w+_"

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
