# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import base64
import hashlib
import struct
import sys
import types
from typing import TYPE_CHECKING, Any, Iterable, Optional

from marimo._ast.visitor import ScopedVisitor
from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.context import ContextNotInitializedError, get_context
from marimo._runtime.primitives import (
    FN_CACHE_TYPE,
    is_data_primitive,
    is_data_primitive_container,
    is_primitive,
    is_pure_function,
)
from marimo._runtime.state import SetFunctor, State
from marimo._save.ast import DeprivateVisitor
from marimo._save.cache import Cache, CacheType
from marimo._utils.variables import (
    get_cell_from_local,
    if_local_then_mangle,
    unmangle_local,
)

if TYPE_CHECKING:
    from types import CodeType

    from marimo._ast.cell import CellId_t, CellImpl
    from marimo._ast.visitor import Name
    from marimo._runtime.context.types import RuntimeContext
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


def standardize_tensor(tensor: Tensor) -> Optional[Tensor]:
    # TODO: Consider moving to a more general utility module.
    if hasattr(tensor, "__array__") or hasattr(tensor, "toarray"):
        if not hasattr(tensor, "__array_interface__"):
            DependencyManager.numpy.require(
                "to access data buffer for hashing."
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


def type_sign(value: bytes, label: str) -> bytes:
    # Appending all strings with a key disambiguates it from other types. e.g.
    # when the string value is the same as a float pack, or is the literal
    # ":none". If our content strings take the form: integrity + delimiter then
    # these types of collisions become very hard.
    #
    # Note that this does not fully protect against cache poisoning, as an
    # attacker can override python internals to provide a matched hash. A key
    # signed cache result is the only way to properly protect against this.
    #
    # Additionally, (less meaningful, but still possible)- a byte collision can
    # be manufactured by choosing data so long that the length of the data acts
    # as the data injection.
    #
    # TODO: Benchmark something like `sha1 (integrity) + delimiter`, this
    # method is chosen because it was assumed to be fast, but might be slow
    # with a copy of large data.
    return b"".join([value, bytes(len(value)), bytes(":" + label, "utf-8")])


def iterable_sign(value: Iterable[Any], label: str) -> bytes:
    values = list(value)
    return b"".join(
        [b"".join(values), bytes(len(values)), bytes(":" + label, "utf-8")]
    )


def primitive_to_bytes(value: Any) -> bytes:
    if value is None:
        return b":none"
    if isinstance(value, str):
        return type_sign(bytes(f"{value}", "utf-8"), "str")
    if isinstance(value, float):
        return type_sign(struct.pack("d", value), "float")
    if isinstance(value, int):
        return type_sign(struct.pack("q", value), "int")
    if isinstance(value, tuple):
        return iterable_sign(map(primitive_to_bytes, value), "tuple")
    return type_sign(bytes(value), "bytes")


def common_container_to_bytes(value: Any) -> bytes:
    visited: dict[int, int] = {}

    def recurse_container(value: Any) -> bytes:
        if id(value) in visited:
            return type_sign(bytes(visited[id(value)]), "id")
        if isinstance(value, dict):
            visited[id(value)] = len(visited)
            return iterable_sign(
                map(recurse_container, sorted(value.items())), "dict"
            )
        if isinstance(value, list):
            visited[id(value)] = len(visited)
            return iterable_sign(map(recurse_container, value), "list")
        if isinstance(value, set):
            visited[id(value)] = len(visited)
            return iterable_sign(map(recurse_container, sorted(value)), "set")
        # Tuple may be only data primitive, not fully primitive.
        if isinstance(value, tuple):
            return iterable_sign(map(recurse_container, value), "tuple")

        if is_primitive(value):
            return primitive_to_bytes(value)
        return data_to_buffer(value)

    return recurse_container(value)


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
    return type_sign(memoryview(data_c_contiguous.view("uint8")), "data")


class BlockHasher:
    def __init__(
        self,
        module: ast.Module,
        graph: DirectedGraph,
        cell_id: CellId_t,
        scope: dict[str, Any],
        *,
        context: Optional[ast.Module] = None,
        pin_modules: bool = False,
        hash_type: str = DEFAULT_HASH,
        content_hash: bool = True,
    ) -> None:
        """Hash the context of the module, and return a cache object.

        Hashing occurs 3 combined methods, content addressed, and execution
        path:

        1) "Pure" hashing is used when a block has no references. The hash is
        computed from the code itself.

        2) "Content Addressed" hashing is used when all references are known
        and are shown to be primitive types (like a "pure" function).

        3) "Execution Path" hashing is when objects may contain state or other
        hidden values that are difficult to hash deterministically. For this,
        the code used to produce the object is used as the basis of the hash.
        It follows that code which does not change, will produce the same
        output. This draws inspiration from hashing methods in Nix. One notable
        difference between these methods is that Nix sandboxes all execution,
        preventing external file access, and internet. Sources of
        non-determinism are not accounted for in this implementation, and are
        left to the user.

        In both cases, as long as the module is deterministic, the output will
        be deterministic. NB. The ContextExecutionPath is an extended case of
        ExecutionPath hashing, just utilizing additional context.

        Args:
          - module: The code content to create a hash for (e.g.
            for persistent_cache, the body of the `With` statement).
          - graph: The dataflow graph of the notebook.
          - cell_id: The cell id attached to the module.
          - scope: The definitions of (globals) available in execution context.
          - context: The "context" of the module, is a module corresponding
            additional execution context for the cell. For instance, in
            persistent_cache case, this applies to the code prior to
            invocation, but still in the same cell.
          - pin_modules: If True, then the module will be pinned to the version
          - hash_type: The type of hash to use.
          - content_hash: If True, then the content hash will be attempted,
            otheriwise only use execution path hash.

        """

        # Hash should not be pinned to cell id
        scope = {unmangle_local(k, cell_id).name: v for k, v in scope.items()}
        self.module = DeprivateVisitor().visit(module)

        self.graph = graph
        self.cell_id = cell_id
        self.pin_modules = pin_modules
        self.fn_cache: FN_CACHE_TYPE = {}

        # Empty name, so we can match and fill in cell context on load.
        self.visitor = ScopedVisitor("", ignore_local=True)
        self.visitor.visit(module)
        # Determine immediate references
        refs = set(self.visitor.refs)
        self.defs = self.visitor.defs

        # Get stateful registers
        # This is typically done in post execution hook, but it will not be
        # called in script mode.
        # TODO: Strip this out to allow for hash based look up. Name based
        # lookup fails for anonymous instances of state and UI Elements.
        try:
            ctx = get_context()
            ctx.ui_element_registry.register_scope(scope)
            ctx.state_registry.register_scope(scope)
        except ContextNotInitializedError:
            ctx = None

        refs, stateful_refs = self.extract_ref_state_and_normalize_scope(
            refs, scope, ctx
        )
        self.stateful_refs = stateful_refs

        # usedforsecurity=False used to satisfy some static analysis tools.
        self.hash_alg = hashlib.new(hash_type, usedforsecurity=False)
        # Default type, means that there are no references at all.
        cache_type: CacheType = "Pure"

        # TODO: Consider memoizing the hash contents and hashed cells, such
        # that a parent cell's BlockHasher can be used to speed up the hashing
        # of child.

        # Attempt content hash on the cell references
        if refs and content_hash:
            cache_type = "ContentAddressed"
            refs = self.hash_and_dequeue_content_refs(refs, scope)
            # Given an active thread, extract state based variables that
            # influence the graph, and hash them accordingly.
            if ctx:
                (
                    refs,
                    stateful_refs,
                ) = self.hash_and_dequeue_stateful_content_refs(
                    refs, scope, ctx
                )
                self.stateful_refs |= stateful_refs

        # If there are still unaccounted for references, then fallback on
        # execution
        # hashing.
        if refs:
            cache_type = "ExecutionPath"
            # Execution path hash
            refs = self.hash_and_dequeue_execution_refs(refs)

        # If there are remaining references, they should be part of the
        # provided context.
        if refs:
            cache_type = "ContextExecutionPath"
            self.hash_and_verify_context_refs(refs, context)

        # Finally, utilize the unrun block itself, and clean up.
        self.cache_type = cache_type
        self.hash_alg.update(hash_raw_module(module, hash_type))
        self.hash = (
            base64.urlsafe_b64encode(self.hash_alg.digest())
            .decode("utf-8")
            .strip("=")
        )

    def extract_ref_state_and_normalize_scope(
        self,
        refs: set[Name],
        scope: dict[str, Any],
        ctx: Optional[RuntimeContext] = None,
    ) -> tuple[set[Name], set[Name]]:
        """
        Preprocess the scope and references, and extract state references.

        This method performs the following operations:
        1. Removes references that are not present in the scope.
        2. Identifies and returns stateful references.
        3. Adjusts the scope, replacing UI elements and state setters with
           their corresponding values.

        Args:
            refs: A set of reference names.
            scope: A dictionary representing the current scope.
            ctx: An optional runtime context for stateful lookup.

        Returns:
            tuple of:
                - The filtered references.
                - The stateful references.
        """
        refs = set(refs)
        stateful_refs = set()

        # State Setters that are not directly consumed, are not needed.
        for ref in self.visitor.refs:
            # If the setter is consumed, let the hash be tied to the state
            # value.
            if ref in scope and isinstance(scope[ref], SetFunctor):
                stateful_refs.add(ref)
                scope[ref] = scope[ref]._state

        for ref in set(refs):
            if ref in scope.get("__builtins__", ()):
                refs.remove(ref)
                continue

            # The block will likely throw a NameError, so remove and defer to
            # execution.
            if ref not in scope:
                refs.remove(ref)
                continue

            # State relevant to the context, should be dependent on it's value-
            # not the object.
            value: Optional[State[Any]]
            if ctx and (value := ctx.state_registry.lookup(ref)):
                for state_name in ctx.state_registry.bound_names(value):
                    scope[state_name] = value()

            # Likewise, UI objects should be dependent on their value.
            if ctx and (ui := ctx.ui_element_registry.lookup(ref)) is not None:
                for ui_name in ctx.ui_element_registry.bound_names(ui._id):
                    scope[ui_name] = ui.value
                # If the UI is directly consumed, then hold on to the reference
                # for proper cache update.
                stateful_refs.add(ref)
        return refs, stateful_refs

    def hash_and_dequeue_content_refs(
        self, refs: set[Name], scope: dict[Name, Any]
    ) -> set[Name]:
        """Use hashable references to update the hash object and dequeue them.

        NB. "Hashable" types are primitives, data primitives, and pure
        functions. With modules being "hashed" by version number, or ignored.

        Args:
            refs: A set of reference names unaccounted for.
            scope: A dictionary representing the current scope.

        Returns a filtered list of remaining references that were not utilized
        in updating the hash.
        """
        refs = set(refs)
        # Content addressed hash is valid if every reference is accounted for
        # and can be shown to be a primitive value.
        imports = self.graph.get_imports()
        for local_ref in sorted(refs):
            ref = if_local_then_mangle(local_ref, self.cell_id)
            if ref in imports:
                # TODO: There may be a way to tie this in with module watching.
                # e.g. module watcher could mutate the version number based
                # last updated timestamp.
                version = ""
                if self.pin_modules:
                    module = sys.modules[imports[ref].namespace]
                    version = getattr(module, "__version__", "")
                    self.hash_alg.update(
                        f"module:{ref}:{version}".encode("utf8")
                    )
                # No need to watch the module otherwise. If the block depends
                # on it then it should be caught when hashing the block.
                refs.remove(local_ref)
                continue
            if local_ref not in scope:
                # ref is somehow not defined, because of execution path
                # so do not utilize content hash in this case.
                continue
            value = scope[local_ref]

            if is_primitive(value):
                self.hash_alg.update(primitive_to_bytes(value))
            elif is_data_primitive(value):
                self.hash_alg.update(data_to_buffer(value))
            elif is_data_primitive_container(value):
                self.hash_alg.update(common_container_to_bytes(value))
            elif is_pure_function(
                local_ref, value, scope, self.fn_cache, self.graph
            ):
                self.hash_alg.update(
                    hash_module(value.__code__, self.hash_alg.name)
                )
            # An external module variable is assumed to be pure, with module
            # pinning being the mechanism for invalidation.
            elif getattr(value, "__module__", "__main__") == "__main__":
                continue
            # Fall through means that the references should be dequeued.
            refs.remove(local_ref)
        return refs

    def hash_and_dequeue_stateful_content_refs(
        self, refs: set[Name], scope: dict[str, Any], ctx: RuntimeContext
    ) -> tuple[set[Name], set[Name]]:
        """Determines and uses stateful references that impact the code block.

        Args:
            refs: A set of reference names.
            scope: A dictionary representing the current scope.
            ctx: Runtime context for stateful lookup.

        Returns:
            tuple of:
                - The updated references.
                - additional stateful references.
        """
        # TODO: Utilize registry to associate stateful instances with top level
        # variables.
        refs = set(refs)
        # Determine _all_ additional relevant references
        transitive_state_refs = self.graph.get_transitive_references(
            refs, inclusive=False
        )
        # Filter for relevant stateful cases.
        refs |= set(
            filter(
                lambda ref: (
                    ctx.state_registry.lookup(ref) is not None
                    or ctx.ui_element_registry.lookup(ref) is not None
                ),
                transitive_state_refs,
            )
        )
        # Need to run extract again for the expanded ref set.
        refs, stateful_refs = self.extract_ref_state_and_normalize_scope(
            refs, scope, ctx
        )
        # Attempt content hash again on the extracted stateful refs.
        return self.hash_and_dequeue_content_refs(refs, scope), stateful_refs

    def hash_and_dequeue_execution_refs(self, refs: set[Name]) -> set[Name]:
        """Determines and uses the hash of refs' cells to update the hash.

        Args:
          refs: List of references to account for in cell lookup.

        Returns a list of references that were not utilized in updating the
        hash. This should only be possible in the case where a cell context is
        provided, as those references should be accounted for in that context.
        """
        refs = set(refs)
        # Execution path works by just analyzing the input cells to hash.
        ancestors = self.graph.ancestors(self.cell_id)
        # Prune to only the ancestors that are tied to the references.
        ref_cells = set().union(
            *[self.graph.definitions.get(ref, set()) for ref in refs]
        )
        to_hash = ancestors & ref_cells
        for ancestor_id in sorted(to_hash):
            cell_impl = self.graph.cells[ancestor_id]
            self.hash_alg.update(hash_cell_impl(cell_impl, self.hash_alg.name))
            for ref in cell_impl.defs:
                # Look for both, since mangle reference depends on the context
                # of the definition.
                if ref in refs:
                    refs.remove(ref)
                unmangled_ref, _ = unmangle_local(ref)
                if unmangled_ref in refs:
                    refs.remove(unmangled_ref)
        return refs

    def hash_and_verify_context_refs(
        self, refs: set[Name], context: Optional[ast.Module]
    ) -> None:
        """Utilizes the provided context to update the hash with sanity check.

        If there are remaining references, they must be part of the provided
        context. This ensures this is the case, and updates the hash.

        Args:
          refs: List of references to account for in cell lookup.
          context: The context of the module, is a module corresponding
            additional execution context for the cell. For instance, in
            persistent_cache case, this applies to the code prior to
            invocation, but still in the same cell.
        """
        # Native save won't pass down context, so if we are here,
        # then something is wrong with the remaining references.
        assert context is not None, (
            "Execution path could not be resolved. "
            "There may be cyclic definitions in the code."
            "This is unexpected, please report this issue to "
            "https://github.com/marimo-team/marimo/issues"
        )

        ref_cells = set().union(
            *[self.graph.definitions.get(ref, set()) for ref in refs]
        )
        ref_cells |= set(
            [
                cell
                for ref in refs
                if (cell := get_cell_from_local(ref, self.cell_id))
            ]
        )
        assert len(ref_cells) == 1, (
            "Inconsistent references, cannot determine execution path. "
            f"Got {ref_cells} expected set({self.cell_id}). "
            "This is unexpected, please report this issue to "
            "https://github.com/marimo-team/marimo/issues"
        )
        assert ref_cells == {self.cell_id}, (
            "Unexpected execution cell residual "
            f"{ref_cells.pop()} expected {self.cell_id}."
            "This is unexpected, please report this issue to "
            "https://github.com/marimo-team/marimo/issues"
        )
        self.hash_alg.update(hash_raw_module(context, self.hash_alg.name))
        # refs have been accounted for at this point. Nothing to return


def cache_attempt_from_hash(
    module: ast.Module,
    graph: DirectedGraph,
    cell_id: CellId_t,
    scope: dict[str, Any],
    *,
    context: Optional[ast.Module] = None,
    pin_modules: bool = False,
    hash_type: str = DEFAULT_HASH,
    loader: Loader,
) -> Cache:
    """Hash a code block with context from the same cell, and return a cache
    object.

    Returns:
      - A cache object that may, or may not be fully populated.
    """

    hasher = BlockHasher(
        module=module,
        graph=graph,
        cell_id=cell_id,
        scope=scope,
        context=context,
        pin_modules=pin_modules,
        hash_type=hash_type,
    )

    return loader.cache_attempt(
        hasher.defs,
        hasher.hash,
        hasher.stateful_refs,
        hasher.cache_type,
    )
