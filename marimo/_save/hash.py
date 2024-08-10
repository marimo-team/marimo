# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import base64
import hashlib
import sys
import types
from typing import TYPE_CHECKING, Any, Optional

from marimo._ast.visitor import ScopedVisitor
from marimo._runtime.context import get_context
from marimo._runtime.primitives import (
    FN_CACHE_TYPE,
    is_data_primitive,
    is_primitive,
    is_pure_class,
    is_pure_function,
)
from marimo._runtime.state import SetFunctor, State, StateRegistry
from marimo._save.cache import Cache, CacheType
from marimo._utils.variables import if_local_then_mangle, unmangle_local

if TYPE_CHECKING:
    from hashlib import _Hash as HASH
    from types import CodeType

    from marimo._ast.cell import CellId_t, CellImpl
    from marimo._runtime.dataflow import DirectedGraph
    from marimo._save.loaders import Loader


def hash_module(code: Optional[CodeType], hash_type: str = "sha256") -> bytes:
    if not code:
        # SHA256 hash of 32 zero bytes, in the case of no code object
        # Artifact of typing for mypy, but reasonable fallback.
        return b"0" * 32

    hash_alg = hashlib.new(hash_type)

    def process(code_obj: CodeType) -> None:
        # Recursively hash the constants that are also code objects
        for const in code_obj.co_consts:
            if isinstance(const, types.CodeType):
                process(const)
            else:
                hash_alg.update(str(const).encode("utf8"))
        # Concatenate the names and bytecode of the current code object
        # Will cause invalidation of variable naming at the top level
        hash_alg.update(bytes("|".join(code_obj.co_names), "utf8"))
        hash_alg.update(code_obj.co_code)

    process(code)
    return hash_alg.digest()


def hash_raw_module(module: ast.Module, hash_type: str = "sha256") -> bytes:
    # AST has to be compiled to code object prior to process.
    return hash_module(
        compile(
            module,
            "<hash>",
            mode="exec",
            flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
        ),
        hash_type,
    )


def hash_cell_impl(cell: CellImpl, hash_type: str = "sha256") -> bytes:
    return hash_module(cell.body, hash_type) + hash_module(
        cell.last_expr, hash_type
    )


def hash_and_dequeue_execution_refs(
    hash_alg: HASH,
    cell_id: CellId_t,
    graph: DirectedGraph,
    refs: set[str],
) -> None:
    # Execution path works by just analyzing the input cells to hash.
    ancestors = graph.ancestors(cell_id)
    # Prune to only the ancestors that are tied to the references.
    ref_cells = set().union(
        *[graph.definitions.get(ref, set()) for ref in refs]
    )
    to_hash = ancestors & ref_cells
    for ancestor_id in sorted(to_hash):
        cell_impl = graph.cells[ancestor_id]
        hash_alg.update(hash_cell_impl(cell_impl, hash_alg.name))
        for ref in cell_impl.defs:
            # Look for both, since mangle reference depends on the context of
            # the definition.
            if ref in refs:
                refs.remove(ref)
            unmangled_ref, _ = unmangle_local(ref)
            if unmangled_ref in refs:
                refs.remove(unmangled_ref)


def hash_and_dequeue_content_refs(
    hash_alg: HASH,
    cell_id: CellId_t,
    defs: dict[str, Any],
    refs: set[str],
    graph: DirectedGraph,
    pin_modules: bool = False,
) -> None:
    # Content addressed hash is valid if every reference is accounted for and
    # can be shown to be a primitive value.
    fn_cache: FN_CACHE_TYPE = {}
    for local_ref in sorted(refs):
        ref = if_local_then_mangle(local_ref, cell_id)
        if ref in sys.modules:
            # TODO: ask Akshay about module watching
            version = ""
            if pin_modules:
                version = getattr(sys.modules[ref], "__version__", "")
                hash_alg.update(f"module:{ref}:{version}".encode("utf8"))
            # No need to watch the module otherwise. If the block depends on it
            # then it should be caught when hashing the block.
            refs.remove(ref)
        if ref not in defs:
            # ref is somehow not defined, because of execution path
            # so do not utilize content hash in this case.
            continue
        value = defs[ref]

        # TODO: Maybe recursively explore standard containers.
        if is_primitive(value):
            hash_alg.update(str(value).encode("utf8"))
            refs.remove(local_ref)
        elif is_data_primitive(value):
            hash_alg.update(str(value).encode("utf8"))
            refs.remove(local_ref)
        elif is_pure_function(ref, value, defs, fn_cache, graph):
            if isinstance(value, types.FunctionType):
                hash_alg.update(hash_module(value.__code__, hash_alg.name))
            refs.remove(local_ref)


def normalize_and_extract_ref_state(
    visitor_refs: set[str], refs: set[str], defs: dict[str, Any]
) -> set[str]:
    stateful_refs = set()
    ui_registry = get_context().ui_element_registry

    # State Setters that are not directly consumed, are not needed.
    for ref in visitor_refs:
        # If the setter is consumed, let the hash be tied to the state value.
        if ref in defs and isinstance(defs[ref], SetFunctor):
            stateful_refs.add(ref)
            defs[ref] = defs[ref]._state

    for ref in set(refs):
        # State relevant to the context, should be dependent on it's value- not
        # the object.
        state: Optional[State[Any]]
        if state := StateRegistry.lookup(ref):
            defs[ref] = state()

        # Likewise, UI objects should be dependent on their value.
        if ui_id := ui_registry.lookup(ref):
            ui = ui_registry.get_object(ui_id)
            defs[ref] = ui.value
            # If the UI is directly consumed, then hold on to the reference
            # for proper cache update.
            if ref in visitor_refs:
                stateful_refs.add(ref)

        if ref in defs["__builtins__"]:
            refs.remove(ref)
    return stateful_refs


def cache_attempt_from_hash(
    module: ast.Module,
    graph: DirectedGraph,
    cell_id: CellId_t,
    defs: dict[str, Any],
    *,
    context: Optional[ast.Module] = None,
    pin_modules: bool = False,
    hash_type: str = "sha256",
    loader: Loader,
) -> Cache:
    """Hash the context of the module, and return a cache object.

    Hashing occurs 2 combined methods, content addressed, and execution path:

    1) "Content Addressed" hashing is used when all references are known and
    are shown to be primitive types (like a "pure" function).

    2) "Execution Path" hashing is when objects may contain state or other
    hidden values that are difficult to hash deterministically. For this, the
    code used to produce the object is used as the basis of the hash. It
    follows that code which does not change, will produce the same output. This
    draws inspiration from hashing methods in Nix. One notable difference
    between these methods is that Nix sandboxes all execution, preventing
    external file access, and internet. Sources of non-determinism are not
    accounted for in this implementation, and are left to the user.

    In both cases, as long as the module is deterministic, the output will be
    deterministic.

    Args:
      - module: The code content to create a hash for (e.g. persistent_cache,
        the body of the `With` statement).
      - graph: The dataflow graph of the notebook.
      - cell_id: The cell id attached to the module.
      - defs: The definitions of (globals) available in execution context.
      - context: The "context" of the module, is a module corresponding
        additional execution context for the cell. For instance, in
        persistent_cache case, this applies to the code prior to invocation,
        but still in the same cell.
      - loader: The loader object to create/ save a cache object.

    Returns:
      - A cache object that may, or may not be fully populated.
    """
    # Empty name, so we can match and fill in cell context on load.
    visitor = ScopedVisitor("", ignore_local=True)
    visitor.visit(module)

    # Determine immediate references
    refs = set(visitor.refs)
    stateful_refs = normalize_and_extract_ref_state(visitor.refs, refs, defs)

    hash_alg = hashlib.new(hash_type)
    cache_type: CacheType = "ContentAddressed"
    # Attempt content hash
    hash_and_dequeue_content_refs(
        hash_alg, cell_id, defs, refs, graph, pin_modules=pin_modules
    )
    # Determine _all_ additional relevant references
    refs |= (
        graph.get_transitive_references(
            visitor.defs,
            inclusive=False,
        )
        - visitor.refs
    )
    # Need to run extract again for the expanded ref set.
    stateful_refs |= normalize_and_extract_ref_state(visitor.refs, refs, defs)

    # If there are still unaccounted for references, then fallback on execution
    # hashing.
    if refs:
        cache_type = "ExecutionPath"
        # Execution path hash
        hash_and_dequeue_execution_refs(hash_alg, cell_id, graph, refs)

    # If there are remaining references, they should be part of the provided
    # context.
    if refs:
        cache_type = "ContextExecutionPath"
        ref_cells = set().union(
            *[graph.definitions.get(ref, set()) for ref in refs]
        )
        ref_cells |= set(
            [
                cell
                for ref in refs
                if (
                    cell := unmangle_local(
                        if_local_then_mangle(ref, cell_id)
                    ).cell
                )
            ]
        )
        assert len(ref_cells) <= 1, (
            "Inconsistent references, cannot determine execution path. "
            f"Got {ref_cells} expected set({cell_id}). "
            "This is unexpected, please report this issue to "
            "https://github.com/marimo-team/marimo/issues"
        )
        assert ref_cells == {cell_id}, (
            "Unexpected execution cell residual "
            f"{ref_cells.pop()} expected {cell_id}."
            "This is unexpected, please report this issue to "
            "https://github.com/marimo-team/marimo/issues"
        )
        # Native save won't pass down context, so if we are here,
        # then something is wrong with the remaining references.
        assert context is not None, (
            "Execution path could not be resolved. "
            "There may be cyclic definitions in the code."
        )
        hash_alg.update(hash_raw_module(context, hash_type))

    hash_alg.update(hash_raw_module(module, hash_type))
    hashed_context = (
        base64.urlsafe_b64encode(hash_alg.digest()).decode("utf-8").strip("=")
    )

    return loader.cache_attempt(
        visitor.defs, hashed_context, stateful_refs, cache_type
    )
