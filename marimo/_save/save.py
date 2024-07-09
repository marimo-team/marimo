# Copyright 2024 Marimo. All rights reserved.
import ast
import sys
import traceback

from marimo._runtime.context import get_context
from marimo._save.ast import ExtractWithBlock
from marimo._save.hash import hash_context
from marimo._save.loaders import PickleLoader
from marimo._save.utils import contextual_defs


class SkipWithBlock(Exception):
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
        save_path="outputs",
        name: str,
    ):
        # TODO: consider construction injection
        self._loader = PickleLoader(name, save_path)
        self.name = name

        self._skipped = True
        self._cache = None
        self._entered_trace = False
        self._old_trace = None

    def __enter__(self):
        sys.settrace(lambda *args, **keys: None)
        frame = sys._getframe(1)
        # Attempt to hold on to the previous trace.
        self._old_trace = frame.f_trace
        # Setting the frametrace, will cause the function to be run on _every_
        # single context call until the trace is cleared.
        frame.f_trace = self.trace
        return self

    def trace(self, frame, event, arg):
        # General flow is as follows:
        #   1) Follow the stack trace backwards to the first instance of a "<module>"
        # function call, which corresponds to a cell level block.
        #   2) Run static analysis to determine whether the call meets our
        # criteria. The procedure is a little brittle as such, certain contexts
        # are not allow (e.g. called within a function or a loop).
        #  3) Hash the execution and lookup the cache, and return!
        #  otherwise) Set _skipped such that the block continues to execute.
        if self._old_trace:
            self._old_trace(frame, event, arg)

        self._entered_trace = True
        stack = traceback.extract_stack()
        if not self._skipped:
            return

        # This only executes on the first line of code in the block. If the
        # cache is hit, the block terminates early with a SkipWithBlock
        # exception, if the block is not hit, self._skipped is set to False,
        # causing this function to terminate before reaching this block.
        for i, frame in enumerate(stack[::-1]):
            filename, lineno, function_name, code = frame
            if function_name == "<module>":
                ctx = get_context()
                graph = ctx.graph
                cell_id = ctx.execution_context.cell_id
                pre_module, save_module = ExtractWithBlock(lineno - 1).visit(
                    ast.parse(ctx.graph.cells[cell_id].code).body
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
                return
            elif i > 1:
                raise Exception(
                    "persistent_cache must be invoked from cell level "
                    "(cannot be in a function or class)"
                )
        raise Exception("persistent_cache could not resolve block")

    def __exit__(self, exception, value, traceback):
        sys.settrace(self._old_trace)  # Clear to previous set trace.
        if not self._entered_trace:
            raise Exception("Unexpected block format.")

        # Backfill the loaded values into global scope.
        if self._cache and self._cache.hit:
            for lookup, var in contextual_defs(self._cache):
                globals()[var] = self._cache.defs[lookup]
            return True

        # NB: exception is a type.
        if exception:
            assert exception != SkipWithBlock, "Cache was not correctly set."
            raise exception

        # Fill the cache object and save.
        for lookup, var in contextual_defs(self._cache):
            self._cache.defs[lookup] = globals()[var]
        self._loader.save_cache(self._cache)
