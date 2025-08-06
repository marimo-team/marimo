# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import importlib
import inspect
import re
import textwrap
from collections import namedtuple
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Optional, get_args

from marimo._plugins.ui._core.ui_element import S, T, UIElement
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

    def load(self) -> Any:
        return importlib.import_module(self.name)


class FunctionStub:
    def __init__(self, function: Any) -> None:
        self.code = textwrap.dedent(inspect.getsource(function))

    def load(self, glbls: dict[str, Any]) -> Any:
        # TODO: Fix line cache and associate with the correct module.
        code_obj = compile(self.code, "<string>", "exec")
        lcls: dict[str, Any] = {}
        exec(code_obj, glbls, lcls)
        # Update the global scope with the function.
        for value in lcls.values():
            return value


class UIElementStub:
    def __init__(self, element: UIElement[S, T]) -> None:
        self.args = element._args
        self.cls = element.__class__
        # Ideally only hashable attributes are stored on the subclass level.
        defaults = set(self.cls.__new__(self.cls).__dict__.keys())
        defaults |= {"_ctx"}
        self.data = {
            k: v
            for k, v in element.__dict__.items()
            if hasattr(v, "__hash__") and k not in defaults
        }

    def load(self) -> UIElement[S, T]:
        return self.cls.from_args(self.data, self.args)  # type: ignore


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
        memo = {}  # Track processed objects to handle cycles
        for var, lookup in self.contextual_defs():
            value = self.defs.get(var, None)
            scope[lookup] = self._restore_from_stub_if_needed(value, scope, memo)

        for key, value in self.meta.items():
            self.meta[key] = self._restore_from_stub_if_needed(value, scope, memo)

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
        self, value: Any, scope: dict[str, Any], memo: dict[int, Any] | None = None
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
        elif isinstance(value, list):
            result = []
            memo[obj_id] = result
            result.extend([
                self._restore_from_stub_if_needed(item, scope, memo)
                for item in value
            ])
        elif isinstance(value, tuple):
            result = tuple(
                self._restore_from_stub_if_needed(item, scope, memo)
                for item in value
            )
        elif isinstance(value, dict):
            result = {}
            memo[obj_id] = result
            for k, v in value.items():
                result[k] = self._restore_from_stub_if_needed(v, scope, memo)
        else:
            result = value
        memo[obj_id] = result
        
        return result

    def update(
        self,
        scope: dict[str, Any],
        meta: Optional[dict[MetaKey, Any]] = None,
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
        memo = {}  # Track processed objects to handle cycles
        for key, value in self.defs.items():
            self.defs[key] = self._convert_to_stub_if_needed(value, memo)

        for key, value in self.meta.items():
            self.meta[key] = self._convert_to_stub_if_needed(value, memo)

    def _convert_to_stub_if_needed(self, value: Any, memo: dict[int, Any] | None = None) -> Any:
        """Convert objects to stubs if needed, recursively handling collections."""
        if memo is None:
            memo = {}
        
        # Check for cycles
        obj_id = id(value)
        if obj_id in memo:
            return memo[obj_id]
        
        if inspect.ismodule(value):
            result = ModuleStub(value)
        elif inspect.isfunction(value):
            result = FunctionStub(value)
        elif isinstance(value, UIElement):
            result = UIElementStub(value)
        elif isinstance(value, list):
            # Store placeholder to handle cycles
            result = []
            memo[obj_id] = result

            result.extend(
                self._convert_to_stub_if_needed(item, memo) for item in value
            )
        elif isinstance(value, tuple):
            result = tuple(
                self._convert_to_stub_if_needed(item, memo) for item in value
            )
        elif isinstance(value, dict):
            # Store placeholder to handle cycles
            memo[obj_id] = value  # Temporary, will be replaced
            # Recursively convert dictionary values
            result = {
                k: self._convert_to_stub_if_needed(v, memo) for k, v in value.items()
            }
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
