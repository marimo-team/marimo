# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import base64
import hashlib
import numbers
import types
from typing import TYPE_CHECKING, Any, Optional

from marimo._ast.visitor import ScopedVisitor
from marimo._save.cache import Cache, ValidCacheSha
from marimo._utils.variables import is_local_then_mangle

if TYPE_CHECKING:
    from types import CodeType

    from marimo._ast.cell import CellId_t, CellImpl
    from marimo._runtime.dataflow import DirectedGraph
    from marimo._save.loaders import Loader

BASE_PRIMITIVES = (str, numbers.Number, type(None))


def hash_module(code: Optional[CodeType]) -> bytes:
    if not code:
        # SHA256 hash of 32 zero bytes, in the case of no code object
        # Artifact of typing for mypy, but reasonable fallback.
        return b"0" * 32

    sha = hashlib.sha256()

    def process(code_obj: CodeType) -> None:
        # Recursively hash the constants that are also code objects
        for const in code_obj.co_consts:
            if isinstance(const, types.CodeType):
                process(const)
            else:
                sha.update(str(const).encode("utf8"))
        # Concatenate the names and bytecode of the current code object
        # Will cause invalidation of variable naming at the top level
        sha.update(bytes("|".join(code_obj.co_names), "utf8"))
        sha.update(code_obj.co_code)

    process(code)
    return sha.digest()


def hash_raw_module(module: ast.Module) -> bytes:
    # AST has to be compiled to code object prior to process.
    return hash_module(
        compile(
            module,
            "<hash>",
            mode="exec",
            flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
        )
    )


def hash_cell_impl(cell: CellImpl) -> bytes:
    return hash_module(cell.body) + hash_module(cell.last_expr)


def build_execution_hash(
    graph: DirectedGraph, cell_id: CellId_t
) -> Optional[ValidCacheSha]:
    # Execution path works by just analyzing the input cells to hash.
    sha = hashlib.sha256()
    ancestors = graph.ancestors(cell_id)
    references = sorted(
        [hash_cell_impl(graph.cells[cell_id]) for cell_id in ancestors]
    )
    for code in references:
        sha.update(code)
    return ValidCacheSha(sha, "ExecutionPath")


def build_content_hash(
    graph: DirectedGraph,
    cell_id: CellId_t,
    visitor: ScopedVisitor,
    defs: dict[str, Any],
) -> Optional[ValidCacheSha]:
    # Content addressed hash is valid if every reference is accounted for and
    # can be shown to be a primitive value.
    sha = hashlib.sha256()
    for ref in sorted(
        graph.get_transitive_references(visitor.defs, inclusive=False)
        | visitor.refs
    ):
        ref = is_local_then_mangle(ref, cell_id)
        if ref not in defs:
            if ref in defs["__builtins__"]:
                continue
            # ref is somehow not defined, because of unexpected execution path,
            # do not utilize content hash in this case.
            return None
        else:
            value = defs[ref]
        # TODO: Hash module, and maybe recursively explore containers.
        if isinstance(value, BASE_PRIMITIVES):
            sha.update(str(value).encode("utf8"))
            continue
        return None
    return ValidCacheSha(sha, "ContentAddressed")


def cache_attempt_from_hash(
    module: ast.Module,
    graph: DirectedGraph,
    cell_id: CellId_t,
    defs: dict[str, Any],
    *,
    context: Optional[ast.Module] = None,
    loader: Loader,
) -> Cache:
    """Hash the context of the module, and return a cache object.

    Hashing occurs 2 exclusive methods, content addressed, and execution path:

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

    TODO: Account for UI and state.

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

    # Attempt content hash
    valid_cache_sha = build_content_hash(graph, cell_id, visitor, defs)
    if not valid_cache_sha:
        # Execution path hash
        valid_cache_sha = build_execution_hash(graph, cell_id)
        assert valid_cache_sha
        if context:
            valid_cache_sha.sha.update(hash_raw_module(context))

    sha, cache_type = valid_cache_sha
    sha.update(hash_raw_module(module))
    hashed_context = (
        base64.urlsafe_b64encode(sha.digest()).decode("utf-8").strip("=")
    )

    return loader.cache_attempt(visitor.defs, hashed_context, cache_type)
