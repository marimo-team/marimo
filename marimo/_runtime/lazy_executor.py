# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import pickle
import time
from typing import TYPE_CHECKING, Any

from marimo import _loggers
from marimo._messaging.ops import CellOp
from marimo._runtime.context import ContextNotInitializedError, get_context
from marimo._runtime.dataflow import DirectedGraph
from marimo._runtime.executor import Executor
from marimo._runtime.side_effect import CellHash
from marimo._save.hash import cache_attempt_from_hash
from marimo._save.loaders import LazyLoader, Loader
from marimo._save.stubs.lazy_stub import ReferenceStub

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from marimo._ast.cell import CellImpl
    from marimo._save.cache import Cache

    Name = str


def deserializer_by_suffix(_suffix: str) -> Any:
    """Get the appropriate loader based on the file suffix."""
    return pickle.loads


def hydrate(
    refs: set[Name],
    glbls: dict[str, Any],
    _graph: DirectedGraph,
    _loader: Loader,
) -> None:
    """Hydrate references in the global scope by loading stubs.

    Args:
        refs: Set of reference names that the cell depends on
        glbls: Global scope dictionary to update with loaded values
        _graph: Dataflow graph (unused for now)
        _loader: Loader instance (unused for now)

    Raises:
        ValueError: If any UnhashableStubs are found that cannot be loaded
    """
    from marimo._save.stubs.lazy_stub import UnhashableStub

    unhashable_stubs = []

    # Check all refs mentioned by the cell
    for ref in refs:
        obj = glbls.get(ref, None)
        if obj is None:
            continue

        if isinstance(obj, ReferenceStub):
            # Load the pickled data
            try:
                loaded_vars = obj.load(glbls)
                # Update scope with all loaded variables
                for var, value in loaded_vars.items():
                    glbls[var] = value
                    LOGGER.debug(
                        f"[hydrate] Loaded reference stub for '{var}'"
                    )
            except Exception as e:
                LOGGER.error(
                    f"[hydrate] Failed to load reference stub '{ref}': {e}"
                )
                raise

        elif isinstance(obj, UnhashableStub):
            # Cannot hydrate - collect for error reporting
            unhashable_stubs.append(obj)
            LOGGER.debug(
                f"[hydrate] Found unhashable stub '{obj.var_name}' "
                f"of type {obj.type_name}"
            )

    # If we found unhashable stubs, we cannot proceed
    if unhashable_stubs:
        stub_info = ", ".join(
            f"'{s.var_name}' ({s.type_name})" for s in unhashable_stubs
        )
        error_details = "; ".join(s.error_msg for s in unhashable_stubs)
        raise ValueError(
            f"Cannot restore cache: found {len(unhashable_stubs)} unhashable variable(s): {stub_info}. "
            f"These cells need to be re-executed. "
            f"Errors: {error_details}"
        )


def process(
    cell: CellImpl, glbls: dict[str, Any], graph: DirectedGraph, loader: Loader
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
            # TODO: Could be default behavior.
            # Technically cache breaking, so gate it for now.
            lazy=True,
        )
        # TODO: Do not restore if there are known side effects.
        if attempt.hit:
            LOGGER.info(f"Cache hit for cell {cell.cell_id}")
            attempt.restore(glbls)
    except Exception as e:
        LOGGER.info(f"Cache attempt failed for cell {cell.cell_id}: {e}")
        # if attempt is None:
        raise e
    # Also register the cell hash for memoized speedup.
    # Still need to register, since it would have been cleaned up otherwise.
    attempt_register(attempt)
    return attempt


def backfill(
    cell: CellImpl,
    glbls: dict[str, Any],
    result: Any,
    attempt: Cache,
    loader: Loader,
    runtime: float,
) -> Any:
    attempt.update(
        {**glbls},
        {"return": result, "runtime": runtime},
        preserve_pointers=False,
    )
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
    def _record_cache_hit(
        self, cell_id: str, load_time: float, attempt: Cache
    ) -> None:
        """Record cache hit with time saved."""
        try:
            ctx = get_context()
            original_runtime = attempt.meta.get("runtime", 0)
            time_saved = max(0, original_runtime - load_time)
            ctx.cell_cache_context.record_hit(time_saved)
        except ContextNotInitializedError:
            pass
        CellOp.broadcast_cache(cell_id=cell_id, cache="hit")

    def _record_cache_miss(self) -> None:
        """Record cache miss."""
        try:
            ctx = get_context()
            ctx.cell_cache_context.record_miss()
        except ContextNotInitializedError:
            pass

    def execute_cell(
        self,
        cell: CellImpl,
        glbls: dict[str, Any],
        graph: DirectedGraph,
    ) -> Any:
        LOGGER.info(f"{glbls.keys()=}")
        # TODO: Loader should persist on the context level.
        loader = LazyLoader(name=cell.cell_id)

        load_start = time.time()
        attempt = process(cell, glbls, graph, loader)
        load_time = time.time() - load_start

        if attempt.hit:
            self._record_cache_hit(cell.cell_id, load_time, attempt)
            return attempt.meta.get("return")

        self._record_cache_miss()
        hydrate(cell.refs, glbls, graph, loader)

        # Measure execution time
        exec_start = time.time()
        assert self.base is not None, "CachedExecutor requires a base executor"
        result = self.base.execute_cell(cell, glbls, graph)
        runtime = time.time() - exec_start

        backfilled_result = backfill(
            cell, glbls, result, attempt, loader, runtime
        )
        CellOp.broadcast_cache(cell_id=cell.cell_id, cache="cached")
        return backfilled_result

    async def execute_cell_async(
        self,
        cell: CellImpl,
        glbls: dict[str, Any],
        graph: DirectedGraph,
    ) -> Any:
        LOGGER.info(f"{glbls.keys()=}")
        # TODO: Loader should persist on the context level.
        loader = LazyLoader(name=cell.cell_id)

        load_start = time.time()
        attempt = process(cell, glbls, graph, loader)
        load_time = time.time() - load_start

        if attempt.hit:
            self._record_cache_hit(cell.cell_id, load_time, attempt)
            return attempt.meta.get("return")

        self._record_cache_miss()
        hydrate(cell.refs, glbls, graph, loader)

        # Measure execution time
        exec_start = time.time()
        assert self.base is not None, "CachedExecutor requires a base executor"
        result = await self.base.execute_cell_async(cell, glbls, graph)
        runtime = time.time() - exec_start

        backfilled_result = backfill(
            cell, glbls, result, attempt, loader, runtime
        )
        CellOp.broadcast_cache(cell_id=cell.cell_id, cache="cached")
        return backfilled_result
