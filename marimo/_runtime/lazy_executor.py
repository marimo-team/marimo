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


def _hydrate_value_recursive(
    value: Any,
    glbls: dict[str, Any],
    graph: DirectedGraph,
    memo: dict[int, Any] | None = None,
) -> Any:
    """Recursively hydrate all stubs in a value.

    This walks through data structures (dicts, lists, tuples, sets) and
    restores any stubs found within them.

    Args:
        value: The value to hydrate
        glbls: Global scope for stub restoration
        graph: Dataflow graph for finding defining cells
        memo: Memoization dict to handle cycles

    Returns:
        The hydrated value with all stubs restored

    Raises:
        MarimoUnhashableCacheError: If any UnhashableStubs are found
    """
    from marimo._save.cache import _restore_from_stub_if_needed
    from marimo._save.stubs.lazy_stub import UnhashableStub

    if memo is None:
        memo = {}

    # Check for cycles
    obj_id = id(value)
    if obj_id in memo:
        return memo[obj_id]

    # Check for UnhashableStub - these need to error out
    if isinstance(value, UnhashableStub):
        from marimo._runtime.exceptions import MarimoUnhashableCacheError

        # Find which cells define this variable
        cells_to_rerun = set()
        try:
            defining_cells = graph.get_defining_cells(value.var_name)
            cells_to_rerun.update(defining_cells)
        except KeyError:
            # Variable not found in graph
            LOGGER.warning(
                f"Unhashable variable '{value.var_name}' not found in graph"
            )

        raise MarimoUnhashableCacheError(
            cells_to_rerun=cells_to_rerun,
            variables=[value.var_name],
            error_details=f"{value.var_name} ({value.type_name}): {value.error_msg}",
        )

    # Use the existing restoration logic which handles all stub types
    result = _restore_from_stub_if_needed(value, glbls, memo)

    return result


def hydrate(
    refs: set[Name],
    glbls: dict[str, Any],
    graph: DirectedGraph,
    _loader: Loader,
) -> None:
    """Hydrate references in the global scope by loading stubs.

    Only hydrates the transitive dependencies of the cell's refs, not the
    entire scope. This mirrors the approach in StrictExecutor.

    Args:
        refs: Set of reference names that the cell depends on
        glbls: Global scope dictionary to update with loaded values
        graph: Dataflow graph for computing transitive references
        _loader: Loader instance (unused for now)

    Raises:
        ValueError: If any UnhashableStubs are found that cannot be loaded
    """
    from marimo._runtime.primitives import (
        CLONE_PRIMITIVES,
        build_ref_predicate_for_primitives,
    )
    from marimo._save.stubs.lazy_stub import UnhashableStub

    # Get transitive references like StrictExecutor does
    # This prevents us from hydrating the entire scope unnecessarily
    transitive_refs = graph.get_transitive_references(
        refs,
        predicate=build_ref_predicate_for_primitives(glbls, CLONE_PRIMITIVES),
    )

    unhashable_stubs = []

    # Check all transitive refs mentioned by the cell
    for ref in transitive_refs:
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
        from marimo._runtime.exceptions import MarimoUnhashableCacheError

        # Find which cells define these variables
        cells_to_rerun = set()
        for stub in unhashable_stubs:
            try:
                defining_cells = graph.get_defining_cells(stub.var_name)
                cells_to_rerun.update(defining_cells)
            except KeyError:
                # Variable not found in graph
                LOGGER.warning(
                    f"Unhashable variable '{stub.var_name}' not found in graph"
                )

        variables = [s.var_name for s in unhashable_stubs]
        error_details = "; ".join(
            f"{s.var_name} ({s.type_name}): {s.error_msg}"
            for s in unhashable_stubs
        )
        raise MarimoUnhashableCacheError(
            cells_to_rerun=cells_to_rerun,
            variables=variables,
            error_details=error_details,
        )

    # Now recursively hydrate only the transitive refs to handle nested stubs
    # This catches cases like dicts of functions that were stubbed
    for ref in transitive_refs:
        if ref in glbls:
            try:
                glbls[ref] = _hydrate_value_recursive(glbls[ref], glbls, graph)
            except Exception as e:
                # Re-raise unhashable errors with context
                LOGGER.error(f"[hydrate] Failed to hydrate '{ref}': {e}")
                raise


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
    # TODO: Observed to fail in the instance where we can't extract function
    # source. Maybe just mark as unhashable in this case?

    # Extract variable hashes from memo, or compute them for child cell speedup
    # IMPORTANT: Skip stateful_refs (UIElements, State setters) - these need
    # to invalidate cache when their values change
    variable_hashes = {}
    try:
        import base64
        from marimo._save.hash import serialize_and_hash_value

        ctx = get_context()
        # Extract/compute hashes for variables defined by this cell
        # Skip stateful refs - they're handled by the cache restoration logic
        for var in attempt.defs.keys():
            if var in attempt.stateful_refs:
                # Skip UIElements and State setters - their values can change
                # and need to invalidate the cache
                continue

            if var in ctx.cell_hash_memo:
                # Use cached hash from memo
                hash_bytes = ctx.cell_hash_memo[var]
            else:
                # Compute hash for this variable
                value = glbls.get(var)
                if value is not None:
                    hash_bytes = serialize_and_hash_value(value)
                    if hash_bytes is not None:
                        # Store in memo for future reuse
                        ctx.cell_hash_memo[var] = hash_bytes
                    else:
                        # Cannot hash this variable, skip it
                        continue
                else:
                    # Variable not in scope, skip it
                    continue

            # Encode bytes to base64 string for storage
            hash_str = base64.urlsafe_b64encode(hash_bytes).decode("utf-8")
            variable_hashes[var] = hash_str

        if variable_hashes:
            LOGGER.debug(
                f"[backfill] Extracted/computed {len(variable_hashes)} hashes "
                f"for cell {cell.cell_id} (skipped {len(attempt.stateful_refs)} stateful refs)"
            )
    except ContextNotInitializedError:
        pass

    attempt.update(
        {**glbls},
        {"return": result, "runtime": runtime, "variable_hashes": variable_hashes},
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
        loader = LazyLoader(name="lazy")

        # Check if this cell should skip cache due to previous unhashable error
        try:
            ctx = get_context()
            if cell.cell_id in ctx.cells_skip_cache:
                LOGGER.info(
                    f"Skipping cache for cell {cell.cell_id} due to unhashable error"
                )
                ctx.cells_skip_cache.discard(cell.cell_id)
                self._record_cache_miss()
                # Execute directly without cache
                assert self.base is not None, "CachedExecutor requires a base executor"
                return self.base.execute_cell(cell, glbls, graph)
        except ContextNotInitializedError:
            pass

        load_start = time.time()
        attempt = process(cell, glbls, graph, loader)
        load_time = time.time() - load_start

        if attempt.hit:
            self._record_cache_hit(cell.cell_id, load_time, attempt)

            # Populate memo from cached hashes for child cell speedup
            try:
                ctx = get_context()
                variable_hashes = attempt.meta.get("variable_hashes", {})
                if variable_hashes:
                    import base64
                    for var_name, hash_str in variable_hashes.items():
                        # Decode base64 string to bytes for memo storage
                        hash_bytes = base64.urlsafe_b64decode(hash_str)
                        ctx.cell_hash_memo[var_name] = hash_bytes
                    LOGGER.debug(
                        f"[CachedExecutor] Populated memo with {len(variable_hashes)} "
                        f"hashes from cache for cell {cell.cell_id}"
                    )
            except ContextNotInitializedError:
                pass

            # Hydrate the return value to restore any nested stubs
            return_value = attempt.meta.get("return")
            if return_value is not None:
                return_value = _hydrate_value_recursive(return_value, glbls, graph)
            return return_value

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
        loader = LazyLoader(name="lazy")

        # Check if this cell should skip cache due to previous unhashable error
        try:
            ctx = get_context()
            if cell.cell_id in ctx.cells_skip_cache:
                LOGGER.info(
                    f"Skipping cache for cell {cell.cell_id} due to unhashable error"
                )
                ctx.cells_skip_cache.discard(cell.cell_id)
                self._record_cache_miss()
                # Execute directly without cache
                assert self.base is not None, "CachedExecutor requires a base executor"
                return await self.base.execute_cell_async(cell, glbls, graph)
        except ContextNotInitializedError:
            pass

        load_start = time.time()
        attempt = process(cell, glbls, graph, loader)
        load_time = time.time() - load_start

        if attempt.hit:
            self._record_cache_hit(cell.cell_id, load_time, attempt)

            # Populate memo from cached hashes for child cell speedup
            try:
                ctx = get_context()
                variable_hashes = attempt.meta.get("variable_hashes", {})
                if variable_hashes:
                    import base64
                    for var_name, hash_str in variable_hashes.items():
                        # Decode base64 string to bytes for memo storage
                        hash_bytes = base64.urlsafe_b64decode(hash_str)
                        ctx.cell_hash_memo[var_name] = hash_bytes
                    LOGGER.debug(
                        f"[CachedExecutor] Populated memo with {len(variable_hashes)} "
                        f"hashes from cache for cell {cell.cell_id}"
                    )
            except ContextNotInitializedError:
                pass

            # Hydrate the return value to restore any nested stubs
            return_value = attempt.meta.get("return")
            if return_value is not None:
                return_value = _hydrate_value_recursive(return_value, glbls, graph)
            return return_value

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
