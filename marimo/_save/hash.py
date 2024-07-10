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

if TYPE_CHECKING:
    from types import CodeType

    from marimo._ast.cell import CellId_t, CellImpl
    from marimo._runtime.dataflow import DirectedGraph
    from marimo._save.loaders import Loader

BASE_PRIMITIVES = (str, numbers.Number, type(None))

# marimo: __marimo__.__version__
# Module refs
# UI refs
# get_context().ui_element_registry._bindings
# State refs
# Need the same for state

# depth == 1

# "pure" Function refs
# primitive refs
# other


def hash_module(code: Optional[CodeType]) -> bytes:
    if not code:
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
    sha = hashlib.sha256()
    ancestors = graph.ancestors(cell_id)
    references = sorted(
        [hash_cell_impl(graph.cells[cell_id]) for cell_id in ancestors]
    )
    for code in references:
        sha.update(code)
    return ValidCacheSha(sha, "ExecutionPath")


def build_content_hash(
    graph: DirectedGraph, visitor: ScopedVisitor, defs: dict[str, Any]
) -> Optional[ValidCacheSha]:
    sha = hashlib.sha256()
    for ref in sorted(
        graph.get_transitive_references(visitor.defs, inclusive=False)
    ):
        if ref not in defs:
            # Key lookup for mypy
            if ref in defs["__builtins__"]:
                continue
            return None
        else:
            value = defs[ref]
        if isinstance(value, BASE_PRIMITIVES):
            sha.update(str(value).encode("utf8"))
            continue
        return None
    return ValidCacheSha(sha, "ContentAddressed")


def hash_context(
    module: ast.Module,
    graph: DirectedGraph,
    cell_id: CellId_t,
    defs: dict[str, Any],
    *,
    context: Optional[ast.Module] = None,
    loader: Loader,
) -> Cache:
    # Empty name, so we can match and fill in cell context on load.
    visitor = ScopedVisitor("")
    visitor.visit(module)

    # Attempt content hash
    valid_cache_sha = build_content_hash(graph, visitor, defs)
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
