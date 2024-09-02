# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import re
from collections import namedtuple
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from marimo._plugins.ui._core.ui_element import UIElement
from marimo._runtime.context import get_context
from marimo._runtime.state import SetFunctor

if TYPE_CHECKING:
    from types import FrameType

    from marimo._ast.visitor import Name

CacheType = Literal[
    "ContextExecutionPath",
    "ContentAddressed",
    "ExecutionPath",
    "Pure",
    "Unknown",
]
# Easy visual identification of cache type.
CACHE_PREFIX: dict[CacheType, str] = {
    "ContextExecutionPath": "X_",
    "ContentAddressed": "C_",
    "ExecutionPath": "E_",
    "Pure": "P_",
    "Unknown": "U_",
}

ValidCacheSha = namedtuple("ValidCacheSha", ("sha", "cache_type"))


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

    def restore(self, frame: FrameType) -> None:
        for lookup, var in self.contextual_defs():
            frame.f_locals[var] = self.defs[lookup]

        defs = {**globals(), **frame.f_locals}
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
            elif isinstance(value, UIElement):
                value.value = self.defs[ref]
            else:
                raise CacheException(
                    "Failure while restoring cached values. "
                    "Unexpected stateful reference type "
                    f"({type(ref)}:{ref})."
                )

    def load(self, frame: FrameType) -> None:
        for lookup, var in self.contextual_defs():
            self.defs[lookup] = frame.f_locals[var]

        defs = {**globals(), **frame.f_locals}
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
                    f"({type(ref)}:{ref})."
                )

    def contextual_defs(self) -> dict[tuple[Name, Name], Any]:
        """Uses context to resolve private variable names."""
        context = get_context().execution_context
        assert context is not None, "Context could not be resolved"
        private_prefix = f"_cell_{context.cell_id}_"
        return {
            (var, re.sub(r"^_", private_prefix, var)): value
            for var, value in self.defs.items()
            if var not in self.stateful_refs
        }
