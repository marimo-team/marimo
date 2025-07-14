# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import functools
import inspect
import io
import sys
import traceback
from collections import abc

# NB: maxsize follows functools.cache, but renamed max_size outside of drop-in
# api.
from sys import maxsize as MAXINT
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Optional,
    Union,
    cast,
    overload,
)

from marimo._ast.transformers import (
    ARG_PREFIX,
    CacheExtractWithBlock,
    strip_function,
)
from marimo._ast.variables import is_mangled_local, unmangle_local
from marimo._messaging.tracebacks import write_traceback
from marimo._runtime.context import get_context
from marimo._runtime.side_effect import SideEffect
from marimo._runtime.state import State
from marimo._save.cache import Cache, CacheException
from marimo._save.hash import (
    DEFAULT_HASH,
    BlockHasher,
    cache_attempt_from_hash,
    content_cache_attempt_from_base,
)
from marimo._save.loaders import (
    PERSISTENT_LOADERS,
    Loader,
    LoaderKey,
    LoaderPartial,
    LoaderType,
    MemoryLoader,
)
from marimo._save.stores.file import FileStore
from marimo._types.ids import CellId_t
from marimo._utils.with_skip import SkipContext

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

    from marimo._save.stores import Store


class _cache_call:
    """Like functools.cache but notebook-aware. See `cache` docstring`"""

    base_block: BlockHasher
    scope: dict[str, Any]
    scoped_refs: set[str]
    pin_modules: bool
    hash_type: str
    _args: list[str]
    _var_arg: Optional[str] = None
    _var_kwarg: Optional[str] = None
    _loader: Optional[State[Loader]] = None
    _loader_partial: LoaderPartial
    _bound: Optional[dict[str, Any]]
    _last_hash: Optional[str] = None
    _frame_offset: int = 0
    # Consistent with functools.cache
    __wrapped__: Optional[Callable[..., Any]]

    def __init__(
        self,
        _fn: Optional[Callable[..., Any]],
        loader_partial: LoaderPartial,
        *,
        pin_modules: bool = False,
        hash_type: str = DEFAULT_HASH,
        # frame_offset is the number of frames the __init__ call is nested
        # with respect to definition of _fn
        frame_offset: int = 0,
    ) -> None:
        self.pin_modules = pin_modules
        self.hash_type = hash_type
        self._frame_offset = frame_offset
        self._loader_partial = loader_partial
        self._last_hash: Optional[str] = None
        self._bound = {}
        if _fn is None:
            self.__wrapped__ = None
        else:
            self._set_context(_fn)

    @property
    def hits(self) -> int:
        if self._loader is None:
            return 0
        return self.loader.hits

    def _set_context(self, fn: Callable[..., Any]) -> None:
        assert callable(fn), "the provided function must be callable"
        ctx = get_context()
        assert ctx.execution_context is not None, (
            "Could not resolve context for cache. "
            "Either @cache is not called from a top level cell or "
            f"{UNEXPECTED_FAILURE_BOILERPLATE}"
        )

        self.__wrapped__ = fn
        sig = inspect.signature(fn)
        self._args = [
            param.name
            for param in sig.parameters.values()
            if param.kind
            in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.POSITIONAL_ONLY,
            )
        ]
        self._var_arg = next(
            (
                param.name
                for param in sig.parameters.values()
                if param.kind == inspect.Parameter.VAR_POSITIONAL
            ),
            None,
        )
        self._var_kwarg = next(
            (
                param.name
                for param in sig.parameters.values()
                if param.kind == inspect.Parameter.VAR_KEYWORD
            ),
            None,
        )

        # Retrieving frame from the stack: frame is
        #
        # 0  _set_context ->
        # 1  __call__ (or init) -->
        # ...
        # 2 + self._frame_offset: fn
        #
        # Note, that deeply nested frames may cause issues, however
        # checking a single frame- should be good enough.
        f_locals = inspect.stack()[2 + self._frame_offset][0].f_locals
        self.scope = {**ctx.globals, **f_locals}

        # Scoped refs are references particular to this block, that may not be
        # defined out of the context of the block, or the cell.
        # For instance, the args of the invoked function are restricted to the
        # block.
        cell_id = ctx.cell_id or ctx.execution_context.cell_id or CellId_t("")
        self.scoped_refs = set([f"{ARG_PREFIX}{k}" for k in self._args])
        # As are the "locals" not in globals
        self.scoped_refs |= set(f_locals.keys()) - set(ctx.globals.keys())
        # Defined in the cell, and currently available in scope
        self.scoped_refs |= ctx.graph.cells[cell_id].defs & set(
            ctx.globals.keys()
        )
        # The defined private variables of this cell, normalized
        self.scoped_refs |= set(
            unmangle_local(x).name
            for x in ctx.globals.keys()
            if is_mangled_local(x, cell_id)
        )

        graph = ctx.graph
        cell_id = ctx.cell_id or ctx.execution_context.cell_id
        module = strip_function(self.__wrapped__)

        self.base_block = BlockHasher(
            module=module,
            graph=graph,
            cell_id=cell_id,
            scope=self.scope,
            pin_modules=self.pin_modules,
            hash_type=self.hash_type,
            scoped_refs=self.scoped_refs,
            apply_content_hash=False,
        )

        # Load global cache from state
        name = self.__wrapped__.__name__
        # Note, that if the function name shadows a global variable, the
        # lifetime of the cache will be tied to the global variable.
        # We can invalidate that by making an invalid namespace.
        if ctx.globals != f_locals:
            name = f"{name}*"

        self._loader = self._loader_partial.create_or_reconfigure(name)

    @property
    def loader(self) -> Loader:
        assert self._loader is not None, UNEXPECTED_FAILURE_BOILERPLATE
        return self._loader()

    def __get__(
        self, instance: Any, _owner: Optional[type] = None
    ) -> _cache_call:
        if instance is not None:
            if not callable(self.__wrapped__):
                raise TypeError(
                    f"cache() expected a callable, got {type(self.__wrapped__)} "
                    "(have you wrapped a function?)"
                )
            # Bind to the instance
            copy = _cache_call(
                None,
                self._loader_partial,
                pin_modules=self.pin_modules,
                hash_type=self.hash_type,
            )
            # Manually set context, since we have lost frame context.
            # Safe to not copy because data is RO.
            copy.__wrapped__ = functools.partial(self.__wrapped__, instance)
            copy._var_arg = self._var_arg
            copy._var_kwarg = self._var_kwarg
            copy._loader = self._loader
            copy.base_block = self.base_block
            copy.scope = self.scope
            copy.scoped_refs = self.scoped_refs
            # Except _args, which is is different.
            copy._args = self._args.copy()
            # Remove the first arg, which is 'self' or otherwise bound.
            copy._bound = {f"{ARG_PREFIX}{copy._args.pop(0)}": instance}
            return copy
        return self

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        # Capture the deferred call case
        if self.__wrapped__ is None:
            if len(args) != 1:
                raise TypeError(
                    "cache() takes at most 1 argument (expecting function)"
                )
            # Remove the additional frames from singledispatch, because invoking
            # the function directly.
            self._frame_offset -= 4
            self._set_context(args[0])
            return self

        # Rewrite scoped args to prevent shadowed variables
        arg_dict = {f"{ARG_PREFIX}{k}": v for (k, v) in zip(self._args, args)}
        kwargs_copy = {f"{ARG_PREFIX}{k}": v for (k, v) in kwargs.items()}
        # If the function has varargs, we need to capture them as well.
        if self._var_arg is not None:
            arg_dict[f"{ARG_PREFIX}{self._var_arg}"] = args[len(self._args) :]
        if self._var_kwarg is not None:
            # NB: kwargs are always a dict, so we can just copy them.
            arg_dict[f"{ARG_PREFIX}{self._var_kwarg}"] = kwargs.copy()

        # Capture the call case
        ctx = get_context()
        scope = {
            **self.scope,
            **ctx.globals,
            **arg_dict,
            **kwargs_copy,
            **(self._bound or {}),
        }
        assert self._loader is not None, UNEXPECTED_FAILURE_BOILERPLATE
        attempt = content_cache_attempt_from_base(
            self.base_block,
            scope,
            self.loader,
            scoped_refs=self.scoped_refs,
            required_refs=set([f"{ARG_PREFIX}{k}" for k in self._args]),
            as_fn=True,
        )

        failed = False
        self._last_hash = attempt.hash
        try:
            if attempt.hit:
                attempt.restore(scope)
                return attempt.meta["return"]
            response = self.__wrapped__(*args, **kwargs)
            # stateful variables may be global
            scope = {
                k: v for k, v in scope.items() if k in attempt.stateful_refs
            }
            attempt.update(scope, meta={"return": response})
            self.loader.save_cache(attempt)
        except Exception as e:
            failed = True
            raise e
        finally:
            # NB. Exceptions raise their own side effects.
            if not failed:
                ctx.cell_lifecycle_registry.add(SideEffect(attempt.hash))
        return response


class _cache_context(SkipContext):
    def __init__(
        self,
        name: str,
        loader: Loader,
        *,
        pin_modules: bool = False,
        hash_type: str = DEFAULT_HASH,
    ) -> None:
        super().__init__()
        self.name = name

        self._cache: Optional[Cache] = None
        self._body_start: int = MAXINT
        # TODO: Consider having a user level setting.
        self.pin_modules = pin_modules
        self.hash_type = hash_type
        self._loader = loader

    @property
    def hit(self) -> bool:
        return self._cache is not None and self._cache.hit

    def trace(self, with_frame: FrameType) -> None:
        # General flow is as follows:
        #   1) Follow the stack trace backwards to the first instance of a
        # "<module>" function call, which corresponds to a cell level block.
        #   2) Run static analysis to determine whether the call meets our
        # criteria. The procedure is a little brittle as such, certain contexts
        # are not allowed (e.g. called within a function or a loop).
        #  3) Hash the execution and lookup the cache, and return!
        #  otherwise) Set _skipped such that the block continues to execute.

        # This is possible if `With` spans multiple lines.
        # This behavior arguably a python bug.
        # Note the behavior does subtly change in 3.14, but will still be
        # captured by this check.
        if self._cache and self._cache.hit:
            self.skip()

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
                if ctx.execution_context is None:
                    raise CacheException(
                        (
                            "Could not resolve context for cache."
                            f"{UNEXPECTED_FAILURE_BOILERPLATE}"
                        ),
                    )
                graph = ctx.graph
                cell_id = ctx.cell_id or ctx.execution_context.cell_id
                pre_module, save_module = CacheExtractWithBlock(
                    lineno - 1
                ).visit(
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
                    hash_type=self.hash_type,
                )

                self.cache_type = self._cache.cache_type
                # Raising on the first valid line, prevents a discrepancy where
                # whitespace in `With`, changes behavior.
                self._body_start = save_module.body[0].lineno

                if self._cache and self._cache.hit:
                    if lineno >= self._body_start:
                        self.skip()
                return
            # <module> -> _trace_wrapper -> _trace
            elif i > 3:
                raise CacheException(
                    "`cache` must be invoked from cell level "
                    "(cannot be in a function or class)"
                )
        raise CacheException(
            "`persistent_cache` could not resolve block"
            f"{UNEXPECTED_FAILURE_BOILERPLATE}"
        )

    def __exit__(
        self,
        exception: Optional[type[BaseException]],
        instance: Optional[BaseException],
        _tracebacktype: Optional[TracebackType],
    ) -> bool:
        self.teardown()
        if not self.entered_trace:
            raise CacheException(
                f"Unexpected block format {UNEXPECTED_FAILURE_BOILERPLATE}"
            )

        # Cache hit is acceptable, because SkipWithBlock is raised.
        # NB: exception is a type.
        if exception and (self._cache is None or not self._cache.hit):
            if isinstance(instance, BaseException):
                raise instance from CacheException("Failure during save.")
            raise exception

        if self._cache is None or self._frame is None:
            raise CacheException(
                f"Cache was not correctly set {UNEXPECTED_FAILURE_BOILERPLATE}"
            )

        failed = False
        try:
            # Backfill the loaded values into global scope.
            if self._cache.hit:
                assert self._frame is not None, UNEXPECTED_FAILURE_BOILERPLATE
                self._cache.restore(self._frame.f_locals)
                # Return true to suppress the SkipWithBlock exception.
                return True

            # Fill the cache object and save.
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
        except Exception as e:
            failed = True
            raise e
        finally:
            if not failed:
                # Conditional because pendantically, the side effect is on restore /
                # save respectively, and exceptions should raise their own.
                ctx = get_context()
                ctx.cell_lifecycle_registry.add(SideEffect(self._cache.hash))

        return False


# A note on overloading:
# Single dispatch cues off only the first argument, and expects a similar
# signature for every overload: https://peps.python.org/pep-0443/
# However.
# The context and call APIs are slightly different, so `*` expansions are used
# to propagate that information down to the actually implementation.
# As such, we also leverage the `@overload` decorator to provide the correct
# signature and documentation for the singledispatch entry points.

# mypy also seems to do pretty poorly with this overloading, so there is liberal
# removal type rules.


@functools.singledispatch
def _cache_invocation(
    arg: Any,
    loader: Union[LoaderPartial, Loader, LoaderType],
    *args: Any,
    frame_offset: int = 1,
    **kwargs: Any,
) -> Union[_cache_call, _cache_context]:
    del loader, args, kwargs, frame_offset
    raise TypeError(f"Invalid type for cache: {type(arg)}")


def _invoke_call(
    _fn: Callable[..., Any] | None,
    loader: Union[LoaderPartial, Loader, LoaderType],
    *args: Any,
    frame_offset: int = 1,
    **kwargs: Any,
) -> _cache_call:
    if isinstance(loader, Loader):
        raise TypeError(
            "A loader instance cannot be passed to cache directly. "
            f"Specify a loader type (e.g. `{loader.__class__}`) or a loader "
            f"partial (e.g. `{loader.__class__}.partial(arg=value)`)."
        )
    elif isinstance(loader, type) and issubclass(loader, Loader):
        cache_args = {
            "pin_modules": kwargs.pop("pin_modules", False),
            "hash_type": kwargs.pop("hash_type", DEFAULT_HASH),
        }
        loader = cast(Loader, loader).partial(**kwargs)
        kwargs = cache_args

    if not isinstance(loader, LoaderPartial):
        raise TypeError(
            "Invalid loader type. "
            f"Expected a loader partial, got {type(loader)}."
        )
    return _cache_call(
        _fn, loader, *args, frame_offset=frame_offset + 1, **kwargs
    )


@_cache_invocation.register
def _invoke_call_none(
    _fn: None,
    loader: Union[LoaderPartial, Loader, LoaderType],
    *args: Any,
    frame_offset: int = 1,
    **kwargs: Any,
) -> _cache_call:
    return _invoke_call(
        _fn, loader, *args, frame_offset=frame_offset + 1, **kwargs
    )


@_cache_invocation.register
def _invoke_call_fn(
    # mypy would like some generics, but this breaks the singledispatch
    _fn: abc.Callable,  # type: ignore[type-arg]
    loader: Union[LoaderPartial, Loader, LoaderType],
    *args: Any,
    frame_offset: int = 1,
    **kwargs: Any,
) -> _cache_call:
    return _invoke_call(
        _fn, loader, *args, frame_offset=frame_offset + 1, **kwargs
    )


@_cache_invocation.register
def _invoke_context(
    name: str,
    loader: Union[LoaderPartial, Loader, LoaderType],
    *args: Any,
    frame_offset: int = 1,
    **kwargs: Any,
) -> _cache_context:
    del frame_offset

    if isinstance(loader, LoaderPartial):
        loader = loader.create_or_reconfigure(name)()
    elif isinstance(loader, type) and issubclass(loader, Loader):
        cache_args = {
            "pin_modules": kwargs.pop("pin_modules", False),
            "hash_type": kwargs.pop("hash_type", DEFAULT_HASH),
        }
        # Create through partial for meaningful error message.
        loader = (
            cast(Loader, loader)
            .partial(**kwargs)
            .create_or_reconfigure(name)()
        )
        kwargs = cache_args
    return _cache_context(name, loader, *args, **kwargs)


@overload
def cache(
    fn: Optional[Callable[..., Any]] = None,
    pin_modules: bool = False,
    loader: LoaderPartial | LoaderType = MemoryLoader,
) -> _cache_call: ...


@overload
def cache(
    name: str,
    pin_modules: bool = False,
    loader: LoaderPartial | Loader | LoaderType = MemoryLoader,
) -> _cache_context: ...


def cache(  # type: ignore[misc]
    name: Union[str, Optional[Callable[..., Any]]] = None,
    *args: Any,
    pin_modules: bool = False,
    loader: Optional[Union[LoaderPartial, Loader]] = None,
    _frame_offset: int = 1,
    _internal_interface_not_for_external_use: None = None,
    **kwargs: Any,
) -> Union[_cache_call, _cache_context]:
    """## Cache the value of a function based on args and closed-over variables.

    Decorating a function with `@mo.cache` will cache its value based on
    the function's arguments, closed-over values, and the notebook code.

    Examples:
    ```python
    import marimo as mo


    @mo.cache
    def fib(n):
        if n <= 1:
            return n
        return fib(n - 1) + fib(n - 2)
    ```

    `mo.cache` is similar to `functools.cache`, but with three key benefits:

    1. `mo.cache` persists its cache even if the cell defining the
        cached function is re-run, as long as the code defining the function
        (excluding comments and formatting) has not changed.
    2. `mo.cache` keys on closed-over values in addition to function arguments,
        preventing accumulation of hidden state associated with
        `functools.cache`.
    3. `mo.cache` does not require its arguments to be
        hashable (only pickleable), meaning it can work with lists, sets, NumPy
        arrays, PyTorch tensors, and more.

    `mo.cache` obtains these benefits at the cost of slightly higher overhead
    than `functools.cache`, so it is best used for expensive functions.

    Like `functools.cache`, `mo.cache` is thread-safe.

    The cache has an unlimited maximum size. To limit the cache size, use
    `@mo.lru_cache`. `mo.cache` is slightly faster than `mo.lru_cache`, but in
    most applications the difference is negligible.

    Note, `mo.cache` can also be used as a drop in replacement for context block
    caching like `mo.persistent_cache`.

    Args:
        pin_modules: if True, the cache will be invalidated if module versions
            differ.

    ## Context manager to cache the return value of a block of code.

    The `mo.cache` context manager lets you delimit a block of code in which
    variables will be cached to memory when they are first computed.

    By default, the cache is stored in memory and is not persisted across kernel
    runs, for that functionality, refer to `mo.persistent_cache`.

    Examples:
    ```python
    with mo.cache("my_cache") as cache:
        variable = expensive_function()
    ```

    Args:
        name: the name of the cache, used to set saving path- to manually
            invalidate the cache, change the name.
        pin_modules: if True, the cache will be invalidated if module versions
            differ.
        loader: the loader to use for the cache, defaults to `MemoryLoader`.
        **kwargs: keyword arguments
        *args: positional arguments
    """
    arg = name
    del name

    if loader is None:
        loader = MemoryLoader.partial(max_size=-1)

    return _cache_invocation(
        arg,
        loader,
        *args,
        frame_offset=_frame_offset + 1,
        pin_modules=pin_modules,
        **kwargs,
    )


@overload
def lru_cache(
    fn: Optional[Callable[..., Any]] = None,
    maxsize: int = 128,
    pin_modules: bool = False,
) -> _cache_call: ...


@overload
def lru_cache(
    name: str,
    maxsize: int = 128,
    pin_modules: bool = False,
) -> _cache_call: ...


def lru_cache(  # type: ignore[misc]
    name: Union[str, Optional[Callable[..., Any]]] = None,
    maxsize: int = 128,
    *args: Any,
    pin_modules: bool = False,
    _internal_interface_not_for_external_use: None = None,
    **kwargs: Any,
) -> Union[_cache_call, _cache_context]:
    """Decorator for LRU caching the return value of a function.

    `mo.lru_cache` is a version of `mo.cache` with a bounded cache size. As an
    LRU (Least Recently Used) cache, only the last used `maxsize` values are
    retained, with the oldest values being discarded. For more information,
    see the documentation of `mo.cache`.

    Examples:
    ```python
    import marimo as mo


    @mo.lru_cache
    def factorial(n):
        return n * factorial(n - 1) if n else 1
    ```

    Args:
        maxsize: the maximum number of entries in the cache; defaults to 128.
            Setting to -1 disables cache limits.
        pin_modules: if True, the cache will be invalidated if module versions
            differ.

    ## Context manager for LRU caching the return value of a block of code.

    Args:
        name: Namespace key for the cache.
        maxsize: the maximum number of entries in the cache; defaults to 128.
            Setting to -1 disables cache limits.
        pin_modules: if True, the cache will be invalidated if module versions
            differ.
        **kwargs: keyword arguments passed to `cache()`
        *args: positional arguments passed to `cache()`
    """
    arg = name
    del name

    if {"loader"} & set(kwargs.keys()):
        raise ValueError(
            "loader is not a valid argument "
            "for lru_cache, use mo.cache instead."
        )

    return cast(
        Union[_cache_call, _cache_context],
        cache(  # type: ignore[call-overload]
            arg,
            *args,
            pin_modules=pin_modules,
            loader=MemoryLoader.partial(max_size=maxsize),
            _frame_offset=2,
            **kwargs,
        ),
    )


@overload
def persistent_cache(
    name: str,
    save_path: str | None = None,
    method: LoaderKey = "pickle",
    pin_modules: bool = False,
) -> _cache_context: ...


@overload
def persistent_cache(
    fn: Optional[Callable[..., Any]] = None,
    save_path: str | None = None,
    method: LoaderKey = "pickle",
    pin_modules: bool = False,
) -> _cache_call: ...


def persistent_cache(  # type: ignore[misc]
    name: Union[str, Optional[Callable[..., Any]]] = None,
    save_path: str | None = None,
    method: LoaderKey = "pickle",
    store: Optional[Store] = None,
    fn: Optional[Callable[..., Any]] = None,
    *args: Any,
    pin_modules: bool = False,
    _internal_interface_not_for_external_use: None = None,
    **kwargs: Any,
) -> Union[_cache_call, _cache_context]:
    """## Context manager to save variables to disk and restore them thereafter.

    The `mo.persistent_cache` context manager lets you delimit a block of code
    in which variables will be cached to disk when they are first computed. On
    subsequent runs of the cell, if marimo determines that this block of code
    hasn't changed and neither has its ancestors, it will restore the variables
    from disk instead of re-computing them, skipping execution of the block
    entirely.

    Restoration happens even across notebook runs, meaning you can use
    `mo.persistent_cache` to make notebooks start *instantly*, with variables
    that would otherwise be expensive to compute already materialized in
    memory.

    Examples:
    ```python
    with persistent_cache(name="my_cache"):
        variable = expensive_function()  # This will be cached to disk.
        print("hello, cache")  # this will be skipped on cache hits
    ```

    In this example, `variable` will be cached the first time the block
    is executed, and restored on subsequent runs of the block. If cache
    conditions are hit, the contents of `with` block will be skipped on
    execution. This means that side-effects such as writing to stdout and
    stderr will be skipped on cache hits.

    Note that `mo.state` and `UIElement` changes will also trigger cache
    invalidation, and be accordingly updated.

    **Warning.** Since context abuses sys frame trace, this may conflict with
    debugging tools or libraries that also use `sys.settrace`.

    Args:
        name: the name of the cache, used to set saving path- to manually
            invalidate the cache, change the name.
        save_path: the folder in which to save the cache, defaults to
            `__marimo__/cache` in the directory of the notebook file
        method: the serialization method to use, current options are "json",
            and "pickle" (default).
        pin_modules: if True, the cache will be invalidated if module versions
            differ between runs, defaults to False.
        store: optional store.
        **kwargs: keyword arguments passed to `cache()`
        *args: positional arguments passed to `cache()`


    ## Decorator for persistently caching the return value of a function.

    `persistent_cache` can also be used as a drop in function-level memoization
    for `@mo.cache` or `@mo.lru_cache`. This is much slower than cache, but
    can be useful for saving function values between kernel restarts. For more
    details, refer to `mo.cache`.

    **Usage.**

    ```python
    import marimo as mo


    @mo.persistent_cache
    def my_expensive_function():
        # Do expensive things

    # or

    @mo.persistent_cache(save_path="my/path/to/cache")
    def my_expensive_function_cached_in_a_certain_location():
        # Do expensive things
    ```

    Args:
        fn: the wrapped function if no settings are passed.
        save_path: the folder in which to save the cache, defaults to
            `__marimo__/cache` in the directory of the notebook file
        method: the serialization method to use, current options are "json",
            and "pickle" (default).
        pin_modules: if True, the cache will be invalidated if module versions
            differ between runs, defaults to False.
    """

    arg = name
    del name

    if {"loader"} & set(kwargs.keys()):
        raise ValueError(
            "loader is not a valid argument "
            "for persistent_cache, use mo.cache instead."
        )
    if method not in PERSISTENT_LOADERS:
        raise ValueError(
            f"Invalid method {method}, expected one of "
            f"{PERSISTENT_LOADERS.keys()}"
        )
    if save_path is not None and store is not None:
        raise ValueError(
            "save_path and store cannot both be provided, "
            "provide one or the other."
        )

    # Providing a save_path forces the store to be a FileStore
    if save_path is not None:
        store = FileStore(save_path)

    partial_args: dict[str, Any] = {}
    if store is not None:
        partial_args["store"] = store

    loader = PERSISTENT_LOADERS[method].partial(**partial_args)
    # Injection hook for testing
    if "_loader" in kwargs:
        loader = kwargs.pop("_loader")

    if fn is not None:
        raise TypeError("Do not use fn directly, use positional arguments.")

    return cast(
        Union[_cache_call, _cache_context],
        cache(  # type: ignore[call-overload]
            arg,
            *args,
            loader=loader,
            _frame_offset=2,
            pin_modules=pin_modules,
            **kwargs,
        ),
    )
