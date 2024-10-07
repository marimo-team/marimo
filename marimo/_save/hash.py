# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import base64
import hashlib
import struct
import sys
import types
from typing import TYPE_CHECKING, Any, Iterable, NamedTuple, Optional

from marimo._ast.visitor import Name, ScopedVisitor
from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._core.ui_element import UIElement
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
    from marimo._runtime.context.types import RuntimeContext
    from marimo._runtime.dataflow import DirectedGraph
    from marimo._save.loaders import Loader

    # Union[list, torch.Tensor, jax.numpy.ndarray,
    #             np.ndarray, scipy.sparse.spmatrix]
    Tensor = Any


# Default hash type is generally inconsequential, there may be implications of
# malicious hash collision or performance. Malicious hash collision can be
# mitigated with a signed cache, and performance is neligible compared to the
# rest of the hashing mechanism.
DEFAULT_HASH = "sha256"


# NamedTuple over dataclass for unpacking.
class SerialRefs(NamedTuple):
    refs: set[Name]
    content_serialization: dict[Name, bytes]
    stateful_refs: set[Name]


class ShadowedRef:
    """Stub for scoped variables that may shadow global references"""


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


def attempt_signed_bytes(value: bytes, label: str) -> bytes:
    # Prevents hash collisions like:
    # >>> fib(1)
    # >>> s, _ = state(1)
    # >>> fib(s)
    # ^ would be a cache hit as is even though fib(s) would fail by
    # itself
    try:
        return type_sign(common_container_to_bytes(value), label)
    # Fallback to raw state for eval in content hash.
    except TypeError:
        return value


def get_and_update_context_from_scope(
    scope: dict[str, Any],
    scope_refs: Optional[set[Name]] = None,
) -> Optional[RuntimeContext]:
    """Get stateful registers"""

    # Remove non-global references
    ctx_scope = set(scope)
    if scope_refs is None:
        scope_refs = set()
    for ref in scope_refs:
        if ref in ctx_scope:
            ctx_scope.remove(ref)

    # This is typically done in post execution hook, but it will not be
    # called in script mode.
    # TODO: Strip this out to allow for hash based look up. Name based
    # lookup fails for anonymous instances of state and UI Elements.
    try:
        ctx = get_context()
        ctx.ui_element_registry.register_scope(scope)
        ctx.state_registry.register_scope(scope)
        return ctx
    except ContextNotInitializedError:
        return None


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
        apply_content_hash: bool = True,
        scoped_refs: Optional[set[Name]] = None,
    ) -> None:
        """Hash the context of the module, and return a cache object.

        Hashing uses 3 combined methods: pure hashing, content addressed, and
        execution path:

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

        For optimization, the content hash is performed after the execution
        cache- however the content references are collected first. This
        deferred content hash is useful in cases like repeated calls to a
        cached function.

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
          - apply_content_hash: If True, then the content hash will be
            attempted, otherwise only use execution path hash.
          - scoped_refs: A set of references that cannot be traced via
            execution path, and must be accounted for via content hashing.
        """

        # Hash should not be pinned to cell id
        scope = {unmangle_local(k, cell_id).name: v for k, v in scope.items()}
        self.module = DeprivateVisitor().visit(module)

        if not scoped_refs:
            scoped_refs = set()
        else:
            assert (
                not apply_content_hash
            ), "scoped_refs should only be used with deferred hashing."

        self._hash: Optional[str] = None
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

        # Deferred hashing (i.e. instantiation without applying content hash),
        # may yield missing references.
        self.missing: set[Name] = set()
        if not apply_content_hash:
            refs, self.missing = self.extract_missing_ref(refs, scope)

        ctx = get_and_update_context_from_scope(scope)
        refs, _, stateful_refs = self.extract_ref_state_and_normalize_scope(
            refs, scope, ctx
        )
        self.stateful_refs = stateful_refs

        # usedforsecurity=False used to satisfy some static analysis tools.
        self.hash_alg = hashlib.new(hash_type, usedforsecurity=False)

        # Hold on to each ref type
        self.content_refs = set(refs)
        self.execution_refs = set(refs)
        self.context_refs = set(refs)

        # Default type, means that there are no references at all.
        cache_type: CacheType = "Pure"

        # TODO: Consider memoizing the serialized contents and hashed cells,
        # such that a parent cell's BlockHasher can be used to speed up the
        # hashing of child.

        # Collect references that will be utilized for a content hash.
        content_serialization: dict[Name, bytes] = {}
        if refs:
            cache_type = "ContentAddressed"
            refs, content_serialization, stateful_refs = (
                self.collect_for_content_hash(
                    refs, scope, ctx, scoped_refs, apply_hash=False
                )
            )
            self.stateful_refs |= stateful_refs
        self.content_refs -= refs

        # If there are still unaccounted for references, then fallback on
        # execution hashing.
        if refs:
            cache_type = "ExecutionPath"
            refs = self.hash_and_dequeue_execution_refs(refs)
        self.execution_refs -= refs | self.content_refs

        # Remove values that should be provided by external scope.
        refs -= scoped_refs

        # If there are remaining references, they should be part of the
        # provided context.
        if refs:
            cache_type = "ContextExecutionPath"
            self.hash_and_verify_context_refs(refs, context)
        self.context_refs -= refs | self.content_refs | self.execution_refs

        # Now run the content hash on the content refs.
        if apply_content_hash:
            self._apply_content_hash(content_serialization)
        elif self.missing:
            cache_type = "Deferred"

        # Finally, utilize the unrun block itself, and clean up.
        self.cache_type = cache_type
        self.hash_alg.update(hash_raw_module(module, hash_type))

    @staticmethod
    def from_parent(
        parent: BlockHasher,
    ) -> BlockHasher:
        # Use a previous block as the basis of a new block.
        block = BlockHasher.__new__(BlockHasher)
        block.module = parent.module
        block.graph = parent.graph
        block.cell_id = parent.cell_id
        block.pin_modules = parent.pin_modules
        block.fn_cache = {}
        if parent.fn_cache is not None:
            block.fn_cache = dict(parent.fn_cache)
        block.visitor = parent.visitor
        block.defs = set(parent.defs)
        block.stateful_refs = set(parent.stateful_refs)
        block.hash_alg = parent.hash_alg.copy()
        block._hash = None
        block.cache_type = parent.cache_type
        block.content_refs = set(parent.content_refs)
        block.execution_refs = set(parent.execution_refs)
        block.context_refs = set(parent.context_refs)
        return block

    @property
    def hash(self) -> str:
        if self._hash is None:
            assert self.hash_alg is not None, "Hash algorithm not initialized."
            self._hash = (
                base64.urlsafe_b64encode(self.hash_alg.digest())
                .decode("utf-8")
                .strip("=")
            )
        return self._hash

    def __hash__(self) -> int:
        return hash(self.hash)

    def _apply_content_hash(
        self, content_serialization: dict[Name, bytes]
    ) -> None:
        self._hash = None
        for ref in sorted(content_serialization):
            self.hash_alg.update(content_serialization[ref])

    def collect_for_content_hash(
        self,
        refs: set[Name],
        scope: dict[str, Any],
        ctx: Optional[RuntimeContext],
        scoped_refs: set[Name],
        apply_hash: bool = True,
    ) -> SerialRefs:
        self._hash = None
        refs, content_serialization, _ = (
            self.serialize_and_dequeue_content_refs(refs, scope)
        )
        # If scoped refs are present, then they are unhashable
        # and we should fallback to normal hash or fail.
        if unhashable := (refs & scoped_refs) - self.execution_refs:
            # pickle is a python default
            import pickle

            failed = []
            exceptions = []
            # By rights, could just fail here - but this final attempt should
            # provide better user experience.
            for ref in unhashable:
                try:
                    _hashed = pickle.dumps(scope[ref])
                    content_serialization[ref] = type_sign(_hashed, "pickle")
                    refs.remove(ref)
                except (pickle.PicklingError, TypeError) as e:
                    exceptions.append(e)
                    failed.append(ref)
            if failed:
                # Ruff didn't like a lambda here
                def get_type(ref: Name) -> str:
                    return (
                        str(type(item)) if (item := scope[ref]) else "missing"
                    )

                ref_list = ", ".join(
                    [
                        f"{ref}: {get_type(ref)} ({str(e)})"
                        for ref, e in zip(failed, exceptions)
                    ]
                )
                # Note ExceptionGroup nicest here, but only available in 3.11
                # ExceptionGroup(msg, exceptions)
                raise TypeError(
                    "Content addressed hash could not be utilized. "
                    "Try defining the dependent sections in a separate cell. "
                    "The unhashable arguments/ references are: " + ref_list
                )

        # Given an active thread, extract state based variables that
        # influence the graph, and hash them accordingly.
        if ctx:
            (
                refs,
                content_serialization_tmp,
                stateful_refs,
            ) = self.serialize_and_dequeue_stateful_content_refs(
                refs, scope, ctx
            )
            content_serialization.update(content_serialization_tmp)
        else:
            stateful_refs = set()

        if apply_hash:
            self._apply_content_hash(content_serialization)
        return SerialRefs(refs, content_serialization, stateful_refs)

    def extract_missing_ref(
        self,
        refs: set[Name],
        scope: dict[str, Any],
    ) -> tuple[set[Name], set[Name]]:
        _refs = set(refs)
        missing = set()
        for ref in refs:
            # The block will likely throw a NameError, so remove and defer to
            # execution.
            if ref in scope.get("__builtins__", ()):
                continue
            if ref not in scope:
                _refs.remove(ref)
                missing.add(ref)
        return _refs, missing

    def extract_ref_state_and_normalize_scope(
        self,
        refs: set[Name],
        scope: dict[str, Any],
        ctx: Optional[RuntimeContext] = None,
    ) -> SerialRefs:
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
            SerialRefs tuple containing the following elements:
                - The filtered references.
                - _
                - The stateful references.
        """
        refs = set(refs)
        stateful_refs = set()

        for ref in set(refs):
            if ref in scope.get("__builtins__", ()):
                refs.remove(ref)
                continue

            # Clean up the scope, and extract missing references.
            refs, _ = self.extract_missing_ref(refs, scope)

            # State relevant to the context, should be dependent on it's value-
            # not the object.
            value: Optional[State[Any]]
            # Prefer actual object over reference.
            # Skip if the reference has already been subbed in, or if it is
            # a shadowed reference.
            if ref in scope and isinstance(scope[ref], State):
                value = scope[ref]
            elif ctx:
                value = ctx.state_registry.lookup(ref)

            if value is not None and (
                ref not in scope or isinstance(scope[ref], State)
            ):
                scope[ref] = attempt_signed_bytes(value(), "state")
                if ctx:
                    for state_name in ctx.state_registry.bound_names(value):
                        scope[state_name] = scope[ref]

            # Likewise, UI objects should be dependent on their value.
            if ref in scope and isinstance(scope[ref], UIElement):
                ui = scope[ref]
            elif ctx:
                ui = ctx.ui_element_registry.lookup(ref)
            if ui is not None and (
                ref not in scope or isinstance(scope[ref], UIElement)
            ):
                scope[ref] = attempt_signed_bytes(ui.value, "ui")
                if ctx:
                    for ui_name in ctx.ui_element_registry.bound_names(ui._id):
                        scope[ui_name] = scope[ref]
                # If the UI is directly consumed, then hold on to the
                # reference for proper cache update.
                stateful_refs.add(ref)

        # State Setters that are not directly consumed, are not needed.
        for ref in self.visitor.refs:
            # If the setter is consumed, let the hash be tied to the state
            # value.
            if ref in scope and isinstance(scope[ref], SetFunctor):
                stateful_refs.add(ref)
                scope[ref] = scope[ref]._state

        return SerialRefs(refs, {}, stateful_refs)

    def serialize_and_dequeue_content_refs(
        self, refs: set[Name], scope: dict[Name, Any]
    ) -> SerialRefs:
        """Use hashable references to update the hash object and dequeue them.

        NB. "Hashable" types are primitives, data primitives, and pure
        functions. With modules being "hashed" by version number, or ignored.

        Args:
            refs: A set of reference names unaccounted for.
            scope: A dictionary representing the current scope.

        Returns a filtered list of remaining references that were not utilized
        in updating the hash, and a dictionary of the content serialization.
        """
        self._hash = None

        content_serialization = {}
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

                content_serialization[ref] = type_sign(
                    bytes(f"module:{ref}:{version}", "utf-8"), "module"
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

            serial_value = None
            if is_primitive(value):
                serial_value = primitive_to_bytes(value)
            elif is_data_primitive(value):
                serial_value = data_to_buffer(value)
            elif is_data_primitive_container(value):
                serial_value = common_container_to_bytes(value)
            elif is_pure_function(
                local_ref, value, scope, self.fn_cache, self.graph
            ):
                serial_value = hash_module(value.__code__, self.hash_alg.name)
            # An external module variable is assumed to be pure, with module
            # pinning being the mechanism for invalidation.
            elif getattr(value, "__module__", "__main__") == "__main__":
                continue

            if serial_value is not None:
                content_serialization[ref] = serial_value
            # Fall through means that the references should be dequeued.
            refs.remove(local_ref)
        return SerialRefs(refs, content_serialization, set())

    def serialize_and_dequeue_stateful_content_refs(
        self,
        refs: set[Name],
        scope: dict[str, Any],
        ctx: RuntimeContext,
    ) -> SerialRefs:
        """Determines and uses stateful references that impact the code block.

        Args:
            refs: A set of reference names.
            scope: A dictionary representing the current scope.
            ctx: Runtime context for stateful lookup.

        Returns:
            tuple of:
                - The updated references.
                - A dictionary of the content serialization.
                - additional stateful references.
        """
        refs = set(refs)
        # Determine _all_ additional relevant references
        transitive_state_refs = self.graph.get_transitive_references(
            refs, inclusive=False
        )

        for ref in transitive_state_refs:
            if ref in scope and isinstance(scope[ref], ShadowedRef):
                # TODO(akshayka, dmadisetti): Lift this restriction once
                # function args are rewritten.
                #
                # This makes more sense as a NameError, but the marimo's
                # explainer text for NameError's doesn't make sense in this
                # context. ("Definition expected in ...")
                raise RuntimeError(
                    f"The cached function declares an argument '{ref}'"
                    "but a captured function or class uses the "
                    f"global variable '{ref}'. Please rename "
                    "the argument, or restructure the use "
                    f"of the global variable."
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
        refs, _, stateful_refs = self.extract_ref_state_and_normalize_scope(
            refs, scope, ctx
        )
        # Attempt content hash again on the extracted stateful refs.
        refs, content_serialization, _ = (
            self.serialize_and_dequeue_content_refs(refs, scope)
        )
        return SerialRefs(refs, content_serialization, stateful_refs)

    def hash_and_dequeue_execution_refs(self, refs: set[Name]) -> set[Name]:
        """Determines and uses the hash of refs' cells to update the hash.

        Args:
          refs: List of references to account for in cell lookup.

        Returns a list of references that were not utilized in updating the
        hash. This should only be possible in the case where a cell context is
        provided, as those references should be accounted for in that context.
        """
        self._hash = None

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
        self._hash = None

        # Native save won't pass down context, so if we are here,
        # then something is wrong with the remaining references.
        assert context is not None, (
            "Execution path could not be resolved. "
            "There may be cyclic definitions in the code. "
            f"The unresolved references are: {refs}. "
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
    scoped_refs: Optional[set[Name]] = None,
    loader: Loader,
    as_fn: bool = False,
) -> Cache:
    """Hash a code block with context from the same cell, and return a cache
    object.

    Extra args
          - loader: The loader to use for cache operations.
          - as_fn: If True, then the block is treated as a function

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
        scoped_refs=scoped_refs,
    )

    if as_fn:
        hasher.defs.clear()

    return loader.cache_attempt(
        hasher.defs,
        hasher.hash,
        hasher.stateful_refs,
        hasher.cache_type,
    )


def content_cache_attempt_from_base(
    previous_block: BlockHasher,
    scope: dict[str, Any],
    loader: Loader,
    scoped_refs: Optional[set[Name]] = None,
    required_refs: Optional[set[Name]] = None,
    *,
    as_fn: bool = False,
    sensitive: bool = False,
) -> Cache:
    """Hash a code block with context from the same cell, and attempt a cache
    lookup.

    Args:
      - previous_block: The block to base the new block on.
      - scope: The scope of the new block.
      - loader: The loader to use for cache operations.
      - scoped_refs: A set of references that cannot be traced via
        execution path, and must be accounted for via content hashing.
      - as_fn: If True, then the block is treated as a function, and will not
        cache definitions in scope.
      - sensitive: If True, then the cache hash will to rehash references
        resolved with path execution. This will invalidate the cache more
        frequently.
    """
    if scoped_refs is None:
        scoped_refs = set()

    if required_refs is None:
        required_refs = set()

    scope = {
        unmangle_local(k, previous_block.cell_id).name: v
        for k, v in scope.items()
    }

    # Manually add back missing refs, which should now be in scope.
    scoped_refs |= previous_block.missing
    scoped_refs |= required_refs

    # refine to values present
    refs = scoped_refs & previous_block.visitor.refs
    # Required refs are made explicit incase the examined block does not
    # specify them e.g.
    # @cache
    # def foo(x):
    #    return random.random()
    # assert foo(0) != foo(1)
    refs |= required_refs
    # Assume all execution refs could be content refs
    # but only if sensitive is set.
    if sensitive:
        refs |= previous_block.execution_refs
    refs |= previous_block.content_refs
    refs |= previous_block.context_refs

    hasher = BlockHasher.from_parent(previous_block)
    ctx = get_and_update_context_from_scope(scope, required_refs)
    refs, _, stateful_refs = hasher.extract_ref_state_and_normalize_scope(
        refs, scope, ctx
    )

    refs, content, tmp_stateful_refs = hasher.collect_for_content_hash(
        refs, scope, ctx, scoped_refs, apply_hash=True
    )
    # If the execution block covers this variable, then that's OK
    refs -= previous_block.execution_refs

    stateful_refs |= tmp_stateful_refs

    assert not refs, (
        "Content addressed hash could not be resolved. "
        "Try defining the cached block in a separate cell. "
        f"The unresolved references are: {refs}. "
    )

    if as_fn:
        hasher.defs.clear()

    return loader.cache_attempt(
        hasher.defs,
        hasher.hash,
        stateful_refs,
        hasher.cache_type,
    )
