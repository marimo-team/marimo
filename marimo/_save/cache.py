# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import re
from collections import namedtuple
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Optional, get_args

from marimo._plugins.ui._core.ui_element import UIElement
from marimo._runtime.context import ContextNotInitializedError, get_context
from marimo._runtime.state import SetFunctor

if TYPE_CHECKING:
    from marimo._ast.visitor import Name

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
MetaKey = Literal["return"]


# BaseException because "raise _ as e" is utilized.
class CacheException(BaseException):
    pass


@dataclass
class Cache:
    defs: dict[Name, Any]
    hash: str
    stateful_refs: set[str]
    cache_type: CacheType
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
