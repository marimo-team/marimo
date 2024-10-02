# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import numbers
import weakref
from typing import TYPE_CHECKING, Any, Callable, Optional, Union

from marimo._ast.visitor import Name, VariableData

if TYPE_CHECKING:
    from marimo._runtime.dataflow import DirectedGraph

PRIMITIVES: tuple[type, ...] = (bytes, str, numbers.Number, type(None))
# Weakref instances should be disassociated from related references, as should
# other "primitives" as they are results and hopefully not hiding some scoped
# reference.
CLONE_PRIMITIVES = (weakref.ref,) + PRIMITIVES

FN_CACHE_TYPE = Optional[dict[Union[Callable[..., Any], type], bool]]


def is_external(value: Any) -> bool:
    return "_marimo__cell_" not in inspect.getfile(value)


def is_primitive(value: Any) -> bool:
    # Tuples don't allow for write access
    if isinstance(value, tuple):
        return all(map(is_primitive, value))
    return isinstance(value, PRIMITIVES)


def is_primitive_type(value: type) -> bool:
    return any(issubclass(value, primitive) for primitive in PRIMITIVES)


def is_clone_primitive(value: Any) -> bool:
    return isinstance(value, CLONE_PRIMITIVES)


def is_data_primitive(value: Any) -> bool:
    if is_primitive(value):
        return True

    # If a numpy array, ensure that it's not an object array.
    if hasattr(value, "__array_interface__"):
        dtype = getattr(value, "dtype", None)
        return not (
            dtype is not None
            and hasattr(dtype, "hasobject")
            and dtype.hasobject
        )

    # Otherwise may be a closely related array object like a pandas DataFrame.
    return hasattr(value, "__array__") or hasattr(value, "toarray")


def _is_primitive_container(
    value: Any, predicate: Callable[[Any], bool]
) -> bool:
    visited = set()

    def recurse_container(value: Any) -> bool:
        if is_primitive(value):
            return True

        if id(value) in visited:
            return True

        if isinstance(value, dict):
            visited.add(id(value))
            return all(map(predicate, value.items()))
        # Tuple has to be considered too, since a tuple can contain containers.
        if isinstance(value, (set, list, tuple)):
            visited.add(id(value))
            return all(map(predicate, value))

        return False

    return recurse_container(value)


def is_data_primitive_container(value: Any) -> bool:
    return _is_primitive_container(value, is_data_primitive)


def is_primitive_container(value: Any) -> bool:
    return _is_primitive_container(value, is_primitive)


def is_pure_scope(
    ref: Name,
    defs: dict[str, Any],
    cache: FN_CACHE_TYPE = None,
) -> bool:
    return inspect.ismodule(defs[ref]) or is_pure_function(
        ref, defs[ref], defs, cache
    )


def is_pure_function(
    ref: Name,
    value: Any,
    defs: dict[str, Any],
    cache: FN_CACHE_TYPE = None,
    graph: Optional[DirectedGraph] = None,
) -> bool:
    if cache is None:
        cache = {}
    # Explicit removal of __hash__ indicates this is potentially mutable.
    # (e.g. list)
    if getattr(value, "__hash__", None) is None:
        return False
    if value in cache:
        return cache[value]
    # Trivial enough not to cache.
    if inspect.isclass(value) or not callable(value):
        return False
    # builtin_function_or_method are C functions, which we assume to be pure
    if inspect.isbuiltin(value):
        return True

    # Note: isfunction still covers lambdas, coroutines, etc.
    if not inspect.isfunction(value):
        return False

    # We assume all external module function references to be pure. Cache can
    # still be be invalidated by pin_modules attribute. Note this also captures
    # cases like functors from an external module.
    # TODO: Investigate embedded notebook values.
    if getattr(value, "__module__", None) != "__main__":
        return True

    cache[value] = True  # Prevent recursion

    def cancel_predicate(ref: Name, _data: VariableData) -> bool:
        if not cache[value]:
            return False

        # A pure function can only refer to other functions, classes, or
        # modules.
        # External variable reference makes it inherently impure.
        if ref in defs:
            # Recursion allows for effective DFS
            if not (
                inspect.ismodule(defs[ref])
                or is_pure_function(ref, defs[ref], defs, cache, graph)
            ):
                cache[value] = False
                return False
        return True

    if graph is not None:
        graph.get_transitive_references(
            {ref}, inclusive=False, predicate=cancel_predicate
        )

    return cache[value]


def build_ref_predicate_for_primitives(
    glbls: dict[str, Any],
    primitives: Optional[tuple[type, ...]] = None,
) -> Callable[[Name, VariableData], bool]:
    """
    Builds a predicate function to determine if a reference should be included

    Args:
        glbls: The global variables dictionary to base the predicate on
        primitives: A tuple of types that should be considered as base types
    Returns:
        A function that takes a variable name and associated data and
        returns True if its reference should be included in a reference search.

    All declared variables are tied together under the graph of required_refs.
    Strict execution gets the minimum graph of definitions for execution.
    Certain definitions, like lambdas, functions, and classes contain an
    executable body and require their `required_refs` to be scope (included in
    this graph). This function determines if a potential reference should be
    included in the graph based on its computed type. Consider:

    >>> def foo():
    ...     return bar()

    here `foo` is a function with `bar` as a reference in the execution body,
    so if `foo` is a reference, both `bar` and `foo` should be included in the
    graph, otherwise we'll get a NameError on `bar` if `foo` is called.
    Compare that to:

    >>> x = foo()

    if `x` is the only reference, should `foo` be included in the graph? It
    depends on the context, so we defer to the type of `x` which has already
    been computed at this point. If `x` is a known 'primitive' type, and thus
    does not have an executable body, we can exclude `foo` from the graph.
    However, `foo` may return a object or another function, which in turn may
    have references; so if x doesn't match the very low bar 'primitive', its
    `required_refs` are included in the graph.

    NB: The builtin `inspect.getclosurevars` exists, but it fails on some of
    these edgecases.

    NB: lambdas, as anonymous functions, do not have a name to refer to them-
    so visitor injects the dummy variable `_lambda` into the `required_refs` to
    denote their presence.
    """

    if primitives is None:
        primitives = PRIMITIVES

    def check_ref(ref: Name) -> bool:
        return ref in glbls and (
            inspect.isfunction(glbls[ref])
            or inspect.ismodule(glbls[ref])
            or inspect.isclass(glbls[ref])
            or callable(glbls[ref])
        )

    def only_scoped_refs(ref: Name, data: VariableData) -> bool:
        # TODO: Other common types could be added here, like numpy arrays that
        # are not dtype=object, etc.. that are known not to be dependent on the
        # functions that created them.

        # This errs on the side of including too much, but that's a better user
        # experience than not having definitions available.
        return (
            ref in glbls
            and not isinstance(glbls[ref], primitives)
            and (
                "_lambda" in data.required_refs
                or any(map(check_ref, data.required_refs | {ref}))
            )
        )

    return only_scoped_refs
