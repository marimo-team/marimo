# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import sys
import traceback
from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
    Type,
    Union,
)

from marimo._runtime.context import get_context
from marimo._save.ast import ExtractWithBlock
from marimo._save.cache import Cache, contextual_defs
from marimo._save.hash import hash_context
from marimo._save.loaders import PickleLoader

if TYPE_CHECKING:
    from types import FrameType, TracebackType

    from _typeshed import TraceFunction
    from typing_extensions import Self


class SkipWithBlock(Exception):
    """Special exception to get around executing the with block body."""


class CacheException(BaseException):
    pass


class persistent_cache(object):
    """Context block for cache lookup of a block of code.

    Example usage:

    >>> with persistent_cache(name="my_cache"):
    >>>     variable = expensive_function() # This will be cached.

    For an implementation sibling regarding the block skipping, see `withhacks`
    in pypi.

    NB: Since context abuses sys frame trace, this may conflict with debugging
    tools that also use sys.settrace.
    """

    def __init__(
        self,
        *,
        save_path: str = "outputs",
        name: str,
    ) -> None:
        # TODO: consider construction injection
        self._loader = PickleLoader(name, save_path)
        self.name = name

        self._skipped = True
        self._cache: Optional[Cache] = None
        self._entered_trace = False
        self._old_trace: Optional[TraceFunction] = None

    def __enter__(self) -> Self:
        sys.settrace(lambda *_args, **_keys: None)
        frame = sys._getframe(1)
        # Attempt to hold on to the previous trace.
        self._old_trace = frame.f_trace
        # Setting the frametrace, will cause the function to be run on _every_
        # single context call until the trace is cleared.
        frame.f_trace = self.trace
        return self

    def trace(
        self, _frame: FrameType, _event: str, _arg: Any
    ) -> Union[TraceFunction | None]:
        # General flow is as follows:
        #   1) Follow the stack trace backwards to the first instance of a
        # "<module>" function call, which corresponds to a cell level block.
        #   2) Run static analysis to determine whether the call meets our
        # criteria. The procedure is a little brittle as such, certain contexts
        # are not allow (e.g. called within a function or a loop).
        #  3) Hash the execution and lookup the cache, and return!
        #  otherwise) Set _skipped such that the block continues to execute.

        self._entered_trace = True
        stack = traceback.extract_stack()
        if not self._skipped:
            return self._old_trace

        # This only executes on the first line of code in the block. If the
        # cache is hit, the block terminates early with a SkipWithBlock
        # exception, if the block is not hit, self._skipped is set to False,
        # causing this function to terminate before reaching this block.
        for i, frame in enumerate(stack[::-1]):
            _filename, lineno, function_name, _code = frame
            if function_name == "<module>":
                ctx = get_context()
                assert (
                    ctx.execution_context is not None
                ), "Could not resolve context for cache."
                graph = ctx.graph
                cell_id = ctx.execution_context.cell_id
                pre_module, save_module = ExtractWithBlock(lineno - 1).visit(
                    ast.parse(ctx.graph.cells[cell_id].code).body  # type: ignore[arg-type]
                )

                self._cache = hash_context(
                    save_module,
                    graph,
                    cell_id,
                    loader=self._loader,
                    context=pre_module,
                )
                if self._cache.hit:
                    raise SkipWithBlock()

                self.cache_type = self._cache
                self._skipped = False
                return self._old_trace
            elif i > 1:
                raise CacheException(
                    "persistent_cache must be invoked from cell level "
                    "(cannot be in a function or class)"
                )
        raise CacheException("persistent_cache could not resolve block")

    def __exit__(
        self,
        exception: Optional[Type[BaseException]],
        instance: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> bool:
        sys.settrace(self._old_trace)  # Clear to previous set trace.
        if not self._entered_trace:
            raise CacheException("Unexpected block format.")

        # Backfill the loaded values into global scope.
        if self._cache and self._cache.hit:
            for lookup, var in contextual_defs(self._cache):
                globals()[var] = self._cache.defs[lookup]
            # Return true to suppress the SkipWithBlock exception.
            return True

        # NB: exception is a type.
        if exception:
            assert not isinstance(
                instance, SkipWithBlock
            ), "Cache was not correctly set."
            if isinstance(instance, BaseException):
                raise instance
            raise exception

        # Fill the cache object and save.
        assert self._cache is not None
        for lookup, var in contextual_defs(self._cache):
            self._cache.defs[lookup] = globals()[var]
        self._loader.save_cache(self._cache)
        return False
