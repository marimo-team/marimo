# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import base64
import hashlib
import sys
import types
from typing import TYPE_CHECKING, Any, Optional

from marimo._ast.visitor import ScopedVisitor
from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._runtime.primitives import (
    FN_CACHE_TYPE,
    is_data_primitive,
    is_primitive,
    is_pure_function,
)
from marimo._runtime.state import SetFunctor, State, StateRegistry
from marimo._save.cache import Cache, CacheType
from marimo._utils.variables import (
    get_cell_from_local,
    if_local_then_mangle,
    unmangle_local,
)

if TYPE_CHECKING:
    from hashlib import _Hash as Hash
    from types import CodeType

    from marimo._ast.cell import CellId_t, CellImpl
    from marimo._runtime.dataflow import DirectedGraph
    from marimo._save.loaders import Loader

    # Union[list, torch.Tensor, jax.numpy.ndarray,
    #             np.ndarray, scipy.sparse.spmatrix]
    Tensor = Any


DEFAULT_HASH = "sha256"


def hash_module(
    code: Optional[CodeType], hash_type: str = DEFAULT_HASH
) -> bytes:
    hash_alg = hashlib.new(hash_type, usedforsecurity=False)
    if not code:
        # Hash of zeros, in the case of no code object as a recognizable noop.
        # Artifact of typing for mypy, but reasonable fallback.
        return b"0" * len(hash_alg.digest())

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


def hash_raw_module(
    module: ast.Module, hash_type: str = DEFAULT_HASH
) -> bytes:
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


def hash_cell_impl(cell: CellImpl, hash_type: str = DEFAULT_HASH) -> bytes:
    return hash_module(cell.body, hash_type) + hash_module(
        cell.last_expr, hash_type
    )


def hash_and_dequeue_execution_refs(
    hash_alg: Hash,
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


def standardize_tensor(tensor: Tensor) -> Optional[Tensor]:
    # TODO: Consider moving to a more general utility module.
    if hasattr(tensor, "__array__") or hasattr(tensor, "toarray"):
        if not hasattr(tensor, "__array_interface__"):
            DependencyManager.numpy.require(
                "to render images from generic arrays in `mo.image`"
            )
            import numpy

            # Capture those sparse cases
            if hasattr(tensor, "toarray"):
                tensor = tensor.toarray()
            tensor = numpy.array(tensor)
        return tensor
    raise ValueError(
        f"Expected an image object, but got {type(tensor)} instead."
    )


def data_to_buffer(data: Tensor) -> bytes:
    data = standardize_tensor(data)
    # From joblib.hashing
    if data.shape == ():
        # 0d arrays need to be flattened because viewing them as bytes
        # raises a ValueError exception.
        data_c_contiguous = data.flatten()
    elif data.flags.c_contiguous:
        data_c_contiguous = data
    elif data.flags.f_contiguous:
        data_c_contiguous = data.T
    else:
        # Cater for non-single-segment arrays, this creates a copy, and thus
        # alleviates this issue. Note: There might be a more efficient way of
        # doing this, check for joblib updates.
        data_c_contiguous = data.flatten()
    return memoryview(data_c_contiguous.view("uint8"))


def hash_and_dequeue_content_refs(
    hash_alg: Hash,
    cell_id: CellId_t,
    defs: dict[str, Any],
    refs: set[str],
    graph: DirectedGraph,
    pin_modules: bool = False,
) -> None:
    # Content addressed hash is valid if every reference is accounted for and
    # can be shown to be a primitive value.
    fn_cache: FN_CACHE_TYPE = {}
    imports = graph.get_imports()
    for local_ref in sorted(refs):
        ref = if_local_then_mangle(local_ref, cell_id)
        if ref in imports:
            # TODO: There may be a way to tie this in with module watching.
            # e.g. module watcher could mutate the version number based last
            # updated timestamp.
            version = ""
            if pin_modules:
                module = sys.modules[imports[ref].namespace]
                version = getattr(module, "__version__", "")
                hash_alg.update(f"module:{ref}:{version}".encode("utf8"))
            # No need to watch the module otherwise. If the block depends on it
            # then it should be caught when hashing the block.
            refs.remove(ref)
        if ref not in defs:
            # ref is somehow not defined, because of execution path
            # so do not utilize content hash in this case.
            continue
        value = defs[ref]

        if is_primitive(value):
            hash_alg.update(bytes(value))
            refs.remove(local_ref)
        elif is_data_primitive(value):
            hash_alg.update(data_to_buffer(value))
            refs.remove(local_ref)
        elif is_pure_function(ref, value, defs, fn_cache, graph):
            hash_alg.update(hash_module(value.__code__, hash_alg.name))
            refs.remove(local_ref)
        # An external module variable is assumed to be pure, with module
        # pinning being the mechanism for invalidation.
        elif getattr(value, "__module__", "__main__") != "__main__":
            refs.remove(local_ref)


def normalize_and_extract_ref_state(
    visitor_refs: set[str],
    refs: set[str],
    defs: dict[str, Any],
    cell_id: CellId_t,
) -> set[str]:
    stateful_refs = set()

    # State Setters that are not directly consumed, are not needed.
    for ref in visitor_refs:
        ref = if_local_then_mangle(ref, cell_id)
        # If the setter is consumed, let the hash be tied to the state value.
        if ref in defs and isinstance(defs[ref], SetFunctor):
            stateful_refs.add(ref)
            defs[ref] = defs[ref]._state

    for ref in set(refs):
        if ref in defs["__builtins__"]:
            refs.remove(ref)
            continue

        ref = if_local_then_mangle(ref, cell_id)

        # The block will likely throw a NameError, so remove and defer to
        # execution.
        if ref not in defs:
            refs.remove(ref)
            continue

        # State relevant to the context, should be dependent on it's value- not
        # the object.
        if isinstance(defs[ref], State):
            value = defs[ref]()
            for state_name in StateRegistry.get_references(defs[ref]):
                defs[state_name] = value

        # Likewise, UI objects should be dependent on their value.
        if isinstance(defs[ref], UIElement):
            ui = defs[ref]
            defs[ref] = ui.value
            # If the UI is directly consumed, then hold on to the reference
            # for proper cache update.
            stateful_refs.add(ref)
    return stateful_refs


def cache_attempt_from_hash(
    module: ast.Module,
    graph: DirectedGraph,
    cell_id: CellId_t,
    defs: dict[str, Any],
    *,
    context: Optional[ast.Module] = None,
    pin_modules: bool = False,
    hash_type: str = DEFAULT_HASH,
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

    # Get stateful registers
    # This is typically done in post execution hook, but it will not be called
    # in script mode.
    StateRegistry.register_scope(set(defs.keys()), defs)
    stateful_refs = normalize_and_extract_ref_state(
        visitor.refs, refs, defs, cell_id
    )

    # usedforsecurity=False used to satisfy some static analysis tools.
    hash_alg = hashlib.new(hash_type, usedforsecurity=False)
    # Default type, means that there are no references at all.
    cache_type: CacheType = "Pure"

    # Attempt content hash
    if refs:
        cache_type = "ContentAddressed"
        hash_and_dequeue_content_refs(
            hash_alg, cell_id, defs, refs, graph, pin_modules=pin_modules
        )
        # Determine _all_ additional relevant references
        transitive_state_refs = graph.get_transitive_references(
            visitor.refs, inclusive=False
        )
        refs |= set(
            filter(
                lambda ref: (
                    StateRegistry.lookup(ref)
                    or isinstance(defs[ref], UIElement)
                ),
                transitive_state_refs,
            )
        )
        # Need to run extract again for the expanded ref set.
        stateful_refs |= normalize_and_extract_ref_state(
            visitor.refs, refs, defs, cell_id
        )

        # Attempt content hash
        hash_and_dequeue_content_refs(
            hash_alg, cell_id, defs, refs, graph, pin_modules=pin_modules
        )

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
                if (cell := get_cell_from_local(ref, cell_id))
            ]
        )
        assert len(ref_cells) == 1, (
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

    # Finally, utilize the unrun block itself, and clean up.
    hash_alg.update(hash_raw_module(module, hash_type))
    hashed_context = (
        base64.urlsafe_b64encode(hash_alg.digest()).decode("utf-8").strip("=")
    )

    return loader.cache_attempt(
        visitor.defs, hashed_context, stateful_refs, cache_type
    )
