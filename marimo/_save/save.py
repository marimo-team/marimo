# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import inspect
import io
import sys
import traceback
from sys import maxsize as MAXINT
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Optional,
    Type,
    Union,
)

from marimo._messaging.tracebacks import write_traceback
from marimo._runtime.context import get_context
from marimo._runtime.state import State
from marimo._save.ast import ExtractWithBlock, strip_function
from marimo._save.cache import Cache, CacheException
from marimo._save.hash import cache_attempt_from_hash
from marimo._save.loaders import Loader, MemoryLoader, PickleLoader

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

    from marimo._runtime.dataflow import DirectedGraph


class SkipWithBlock(Exception):
    """Special exception to get around executing the with block body."""


class cache(object):
    """Decorator for caching the return value of a function.

    Decorating a function with `@mo.save.cache` will "memoize" the return
    value. Memoization helps optimize performance by storing the results of
    expensive function calls and reusing them when the same inputs occur again.

    This is analogous to `functools.cache`, but with the added benefit of
    context-aware cache invalidations specific to marimo notebooks.

    Since a dictionary is used to cache results, the positional and keyword
    arguments to the function must be hashable. There are certain exceptions
    for marimo specific variables, such as `mo.state` and `UIElement` objects.

    **Basic Usage.**

    ```python
    import marimo as mo


    @mo.save.cache
    def fib(n):
        if n <= 1:
            return n
        return fib(n - 1) + fib(n - 2)
    ```

    **LRU Cache.**

    The cache has an unlimited maximum size. To limit the cache size, use
    `@mo.save.lru_cache` (a default maxsize of 128), or specify the `maxsize`
    parameter. Set this value to -1 to disable cache limits (default).

    ```python
    @mo.save.cache(maxsize=128)
    def expensive_function():
        pass
    ```

    **Args**:

    - `maxsize`: the maximum number of entries in the cache; defaults to -1.
      Setting to -1 disables cache limits.
    - `pin_modules`: if True, the cache will be invalidated if module versions
      differ.
    """

    graph: DirectedGraph
    cell_id: str
    module: ast.Module
    _args: list[str]
    _loader: Optional[State[MemoryLoader]] = None
    name: str
    fn: Optional[Callable[..., Any]]
    DEFAULT_MAX_SIZE = -1

    def __init__(
        self,
        _fn: Optional[Callable[..., Any]] = None,
        *,
        maxsize: Optional[int] = None,
        pin_modules: bool = False,
    ) -> None:
        self.max_size = (
            maxsize if maxsize is not None else self.DEFAULT_MAX_SIZE
        )
        self.pin_modules = pin_modules
        if _fn is None:
            self.fn = None
        else:
            self.fn = _fn
            self._set_context()

    @property
    def hits(self) -> int:
        if self._loader is None:
            return 0
        return self._loader().hits

    def _set_context(self) -> None:
        assert callable(self.fn), "the provided function must be callable"
        ctx = get_context()
        assert ctx.execution_context is not None, (
            "Could not resolve context for cache. "
            "Either @cache is not called from a top level cell or "
            f"{UNEXPECTED_FAILURE_BOILERPLATE}"
        )
        self.graph = ctx.graph
        self.cell_id = ctx.cell_id or ctx.execution_context.cell_id
        self._args = list(self.fn.__code__.co_varnames)

        self.module = strip_function(self.fn)
        # frame is _set_context -> __call__ (or init) -> fn wrap
        # Note, that deeply nested frames may cause issues, however
        # checking a single frame- should be good enough.
        f_locals = inspect.stack()[2][0].f_locals
        self.scope = {**ctx.globals, **f_locals}

        # Load global cache from state
        name = self.fn.__name__
        # Note, that if the function name shadows a global variable, the
        # lifetime of the cache will be tied to the global variable.
        # We can invalidate that by making an invalid namespace.
        if ctx.globals != f_locals:
            name = name + "*"

        context = "cache"
        self._loader = ctx.state_registry.lookup(name, context=context)
        if self._loader is None:
            loader = MemoryLoader(name, max_size=self.max_size)
            self._loader = State(loader, _name=name, _context=context)
        else:
            self._loader().resize(self.max_size)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        # Capture the deferred call case
        if self.fn is None:
            if len(args) != 1:
                raise TypeError(
                    "cache() takes at most 1 argument (expecting function)"
                )
            self.fn = args[0]
            self._set_context()
            return self

        # Capture the call case
        arg_dict = {k: v for (k, v) in zip(self._args, args)}
        scope = {**self.scope, **arg_dict, **kwargs}
        assert self._loader is not None, UNEXPECTED_FAILURE_BOILERPLATE
        attempt = cache_attempt_from_hash(
            self.module,
            self.graph,
            self.cell_id,
            scope,
            loader=self._loader(),
            pin_modules=self.pin_modules,
            scoped_refs=set(self._args),
            as_fn=True,
        )
        if attempt.hit:
            attempt.restore(scope)
            return attempt.meta["return"]
        response = self.fn(*args, **kwargs)
        # stateful variables may be global
        scope = {k: v for k, v in scope.items() if k in attempt.stateful_refs}
        attempt.update(scope, meta={"return": response})
        self._loader().save_cache(attempt)
        return response


class lru_cache(cache):
    """Decorator for LRU caching the return value of a function.

    This is analogous to `functools.lru_cache`, but with the added benefit of
    being context aware, with cache invalidations particular to marimo
    notebooks. As an LRU (Least Recently Used) cache, only the last used
    `maxsize` values are retained, with the oldest values being discarded.

    **Basic Usage.**

    ```python
    import marimo as mo


    @mo.save.lru_cache(maxsize=128)
    def factorial(n):
        return n * factorial(n - 1) if n else 1
    ```

    For more details, or a cache without a limit by default, refer to
    `mo.save.cache`.

    **Args**:

    - `maxsize`: the maximum number of entries in the cache; defaults to 128.
      Setting to -1 disables cache limits.
    - `pin_modules`: if True, the cache will be invalidated if module versions
      differ.
    """

    DEFAULT_MAX_SIZE = 128


class persistent_cache(object):
    """Context block for cache lookup of a block of code.

    **Basic Usage.**

    ```python
    with persistent_cache(name="my_cache"):
        variable = expensive_function()  # This will be cached.
    ```

    Here, `variable` will be cached and restored on subsequent runs of the
    block. The contents of the `with` block will be skipped on execution, if
    cache conditions are met. Note, this means that stdout and stderr will be
    skipped on cache hits. For function level memoization, use `@mo.save.cache`
    or `@mo.save.lru_cache`.

    Note that `mo.state` and `UIElement` changes will also trigger cache
    invalidation, and be accordingly updated.

    **Warning.** Since context abuses sys frame trace, this may conflict with
    debugging tools or libraries that also use `sys.settrace`.

    **Args**:

    - `name`: the name of the cache, used to set saving path- to manually
      invalidate the cache, change the name.
    - `save_path`: the folder in which to save the cache, defaults to "outputs"
    - `pin_modules`: if True, the cache will be invalidated if module versions
      differ between runs, defaults to False.
    """

    def __init__(
        self,
        *,
        name: str,
        save_path: str = "outputs",
        pin_modules: bool = False,
        _loader: Optional[Loader] = None,
    ) -> None:
        # For an implementation sibling regarding the block skipping, see
        # `withhacks` in pypi.
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
        self._body_start: int = MAXINT
        # TODO: Consider having a user level setting.
        self.pin_modules = pin_modules

    def __enter__(self) -> Self:
        sys.settrace(lambda *_args, **_keys: None)
        frame = sys._getframe(1)
        # Hold on to the previous trace.
        self._old_trace = frame.f_trace
        # Setting the frametrace, will cause the function to be run on _every_
        # single context call until the trace is cleared.
        frame.f_trace = self._trace
        return self

    def _trace(
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

        if not self._skipped:
            return self._old_trace

        # This is possible if `With` spans multiple lines.
        # This behavior arguably a python bug.
        # Note the behavior does subtly change in 3.14, but will still be
        # captured by this check.
        if self._cache and self._cache.hit:
            if with_frame.f_lineno >= self._body_start:
                raise SkipWithBlock()

        stack = traceback.extract_stack()

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
                cell_id = ctx.cell_id or ctx.execution_context.cell_id
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
                    pin_modules=self.pin_modules,
                )

                self.cache_type = self._cache
                # Raising on the first valid line, prevents a discrepancy where
                # whitespace in `With`, changes behavior.
                self._body_start = save_module.body[0].lineno
                if self._cache and self._cache.hit:
                    if lineno >= self._body_start:
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
            self._cache.restore(self._frame.f_locals)
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
        self._cache.update(self._frame.f_locals)

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
