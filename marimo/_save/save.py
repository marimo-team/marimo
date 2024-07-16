# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import io
import sys
import traceback
from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
    Type,
    Union,
)

from marimo._messaging.tracebacks import write_traceback
from marimo._runtime.context import get_context
from marimo._save.ast import ExtractWithBlock
from marimo._save.cache import Cache, contextual_defs
from marimo._save.hash import cache_attempt_from_hash
from marimo._save.loaders import Loader, PickleLoader

# Many assertions are for typing and should always pass. This message is a
# catch all to motive users to report if something does fail.
UNEXPECTED_FAILURE_BOILERPLATE = (
    "— this is"
    " unexpected and is likely a bug in marimo. "
    "Please file an issue at "
    "https://github.com/marimo-team/marimo/issues"
)


if TYPE_CHECKING:
    from types import FrameType, TracebackType

    from _typeshed import TraceFunction
    from typing_extensions import Self


class SkipWithBlock(Exception):
    """Special exception to get around executing the with block body."""


# BaseException because "raise _ as e" is utilized.
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
        _loader: Optional[Loader] = None,
    ) -> None:
        self.name = name
        if _loader:
            self._loader = _loader
        else:
            self._loader = PickleLoader(name, save_path)

        self._skipped = True
        self._cache: Optional[Cache] = None
        self._entered_trace = False
        self._old_trace: Optional[TraceFunction] = None
        self._frame: Optional[FrameType] = None

    def __enter__(self) -> Self:
        sys.settrace(lambda *_args, **_keys: None)
        frame = sys._getframe(1)
        # Hold on to the previous trace.
        self._old_trace = frame.f_trace
        # Setting the frametrace, will cause the function to be run on _every_
        # single context call until the trace is cleared.
        frame.f_trace = self.trace
        return self

    def trace(
        self, with_frame: FrameType, _event: str, _arg: Any
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

        # This is possible if `With` spans multiple lines.
        # This behavior may be a python bug.
        # Could not replicate in 3.10, 3.11 or 3.12 with direct testing; but it
        # may be due to the block being compiled prior to traversal.
        # See failure in:
        # github:marimo/actions/runs/9947523119/job/27480334273?pr=1758
        # TODO: Dig in and report bug to CPython.
        if self._cache and self._cache.hit:
            raise SkipWithBlock()

        # This only executes on the first line of code in the block. If the
        # cache is hit, the block terminates early with a SkipWithBlock
        # exception, if the block is not hit, self._skipped is set to False,
        # causing this function to terminate before reaching this block.
        self._frame = with_frame
        for i, frame in enumerate(stack[::-1]):
            _filename, lineno, function_name, _code = frame
            if function_name == "<module>":
                ctx = get_context()
                assert ctx.execution_context is not None, (
                    "Could not resolve context for cache.",
                    f"{UNEXPECTED_FAILURE_BOILERPLATE}",
                )
                graph = ctx.graph
                cell_id = (
                    ctx.execution_context.cell_id
                    or ctx.execution_context.cell_id
                )
                pre_module, save_module = ExtractWithBlock(lineno - 1).visit(
                    ast.parse(graph.cells[cell_id].code).body  # type: ignore[arg-type]
                )

                self._cache = cache_attempt_from_hash(
                    save_module,
                    graph,
                    cell_id,
                    {**globals(), **with_frame.f_locals},
                    loader=self._loader,
                    context=pre_module,
                )

                self.cache_type = self._cache
                # Raising on the first valid line, prevents a bug where
                # whitespace in `With`, changes behavior. This might be
                # an issue with Python's parser? Noticed because lint/ format
                # breaks things.
                if self._cache and self._cache.hit:
                    if lineno >= save_module.body[0].lineno:
                        raise SkipWithBlock()
                    return self._old_trace
                self._skipped = False
                return self._old_trace
            elif i > 1:
                raise CacheException(
                    "`persistent_cache` must be invoked from cell level "
                    "(cannot be in a function or class)"
                )
        raise CacheException(
            (
                "`persistent_cache` could not resolve block"
                f"{UNEXPECTED_FAILURE_BOILERPLATE}"
            )
        )

    def __exit__(
        self,
        exception: Optional[Type[BaseException]],
        instance: Optional[BaseException],
        _tracebacktype: Optional[TracebackType],
    ) -> bool:
        sys.settrace(self._old_trace)  # Clear to previous set trace.
        if not self._entered_trace:
            raise CacheException(
                ("Unexpected block format" f"{UNEXPECTED_FAILURE_BOILERPLATE}")
            )

        # Backfill the loaded values into global scope.
        if self._cache and self._cache.hit:
            assert self._frame is not None, UNEXPECTED_FAILURE_BOILERPLATE
            for lookup, var in contextual_defs(self._cache):
                self._frame.f_locals[var] = self._cache.defs[lookup]
            # Return true to suppress the SkipWithBlock exception.
            return True

        # NB: exception is a type.
        if exception:
            assert not isinstance(instance, SkipWithBlock), (
                "Cache was not correctly set"
                f"{UNEXPECTED_FAILURE_BOILERPLATE}"
            )
            if isinstance(instance, BaseException):
                raise instance from CacheException("Failure during save.")
            raise exception

        # Fill the cache object and save.
        assert self._cache is not None, UNEXPECTED_FAILURE_BOILERPLATE
        assert self._frame is not None, UNEXPECTED_FAILURE_BOILERPLATE
        for lookup, var in contextual_defs(self._cache):
            self._cache.defs[lookup] = self._frame.f_locals[var]

        try:
            self._loader.save_cache(self._cache)
        except Exception as e:
            sys.stderr.write(
                "An exception was raised when attempting to cache this code "
                "block with the following message:\n"
                f"{str(e)}\n"
                "NOTE: The cell has run, but cache has not been saved.\n"
            )
            tmpio = io.StringIO()
            traceback.print_exc(file=tmpio)
            tmpio.seek(0)
            write_traceback(tmpio.read())
        return False
