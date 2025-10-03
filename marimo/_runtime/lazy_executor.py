from __future__ import annotations

import pickle
import traceback
from typing import TYPE_CHECKING, Any

from marimo import _loggers
from marimo._messaging.ops import CellOp
from marimo._runtime.context import ContextNotInitializedError, get_context
from marimo._runtime.dataflow import DirectedGraph
from marimo._runtime.executor import Executor
from marimo._runtime.side_effect import CellHash
from marimo._save.hash import cache_attempt_from_hash
from marimo._save.loaders import LazyLoader, Loader
from marimo._save.stubs.lazy_stubs import ReferenceStub

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from marimo._ast.cell import CellImpl
    from marimo._save.cache import Cache

    Name = str


def deserializer_by_suffix(suffix: str) -> Any:
    """Get the appropriate loader based on the file suffix."""
    return pickle.loads


def hydrate(
    refs: set[Name],
    glbls: dict[str, Any],
    graph: DirectedGraph,
    loader: Loader,
) -> None:
    """Hydrate references in the global scope."""
    for ref in refs:
        obj = glbls.get(ref, None)
        if isinstance(obj, ReferenceStub):
            for var, value in obj.load(glbls).items():
                # TODO: Set privates too
                glbls[var] = value


def process(
    cell: CellImpl, glbls: dict[str, Any], graph: DirectedGraph, loader
) -> Cache:
    attempt = None
    try:
        attempt = cache_attempt_from_hash(
            cell.mod,
            graph,
            cell.cell_id,
            scope=glbls,
            pin_modules=True,
            loader=loader,
        )
        # TODO: Do not restore if there are known side effects.
        if attempt.hit:
            LOGGER.info(f"Cache hit for cell {cell.cell_id}")
            attempt.restore(glbls)
    except Exception as e:
        LOGGER.info(f"Cache attempt failed for cell {cell.cell_id}: {e}")
        if attempt is None:
            raise e
    # Also register the cell hash for memoized speedup.
    # Still need to register, since it would have been cleaned up otherwise.
    attempt_register(attempt)
    return attempt


def backfill(
    cell: CellImpl, glbls: dict[str, Any], result: Any, attempt: Cache, loader
) -> Any:
    attempt.update({**glbls}, {"return": result}, preserve_pointers=False)
    try:
        loader.save_cache(attempt)
    except Exception as e:
        LOGGER.info(f"Cache save failed for cell {cell.cell_id}: {e}")
    return result


def attempt_register(attempt: Cache) -> None:
    try:
        ctx = get_context()
        # NB: This should never collide with the recursive cell hash method
        # as such, an assertion error should be raised if somehow the recursive
        # method gets out of sync with the cell lifecycle registry.
        ctx.cell_lifecycle_registry.add(
            CellHash(bytes(f"execution:{attempt.hash}", "utf-8")),
        )
    except ContextNotInitializedError as e:
        LOGGER.info(f"Context not initialized for cell: {e}")


class CachedExecutor(Executor):
    def execute_cell(
        self,
        cell: CellImpl,
        glbls: dict[str, Any],
        graph: DirectedGraph,
    ) -> Any:
        LOGGER.info(f"{glbls.keys()=}")
        loader = LazyLoader(name=cell.cell_id)
        attempt = process(cell, glbls, graph, loader)
        if attempt.hit:
            CellOp.broadcast_cache(cell_id=cell.cell_id, cache="hit")
            return attempt.meta.get("return")
        hydrate(cell.refs, glbls, graph, loader)
        result = self.base.execute_cell(cell, glbls, graph)
        backfilled_result = backfill(cell, glbls, result, attempt, loader)
        CellOp.broadcast_cache(cell_id=cell.cell_id, cache="cached")
        return backfilled_result

    async def execute_cell_async(
        self,
        cell: CellImpl,
        glbls: dict[str, Any],
        graph: DirectedGraph,
    ) -> Any:
        LOGGER.info(f"??{glbls.keys()=}")
        loader = LazyLoader(name=cell.cell_id)
        attempt = process(cell, glbls, graph, loader)
        if attempt.hit:
            CellOp.broadcast_cache(cell_id=cell.cell_id, cache="hit")
            return attempt.meta.get("return")
        hydrate(cell.refs, glbls, graph, loader)
        result = await self.base.execute_cell_async(cell, glbls, graph)
        backfilled_result = backfill(cell, glbls, result, attempt, loader)
        CellOp.broadcast_cache(cell_id=cell.cell_id, cache="cached")
        return backfilled_result
