# Copyright 2026 Marimo. All rights reserved.
"""CachedLifecycle for cell-level caching.

Cached Execution is a lifecycle that attempts to skip and stub cell execution
if results have already been computed.

In the "setup" of a cached execution, a cell hash and look up is attempted.
The "teardown" of a cached execution records timing and results to the cache if
the cell ran live.
There are 4 potential outcomes from attempted restoration:

1. Cache hit
   In this case, cache can be successfully loaded from disk, allowing the body
   to skip execution. Resortation populate defs into globals and returns the
   associated value.
2. Stale cache
   In this case, a "UnhashableStub" requirement or cache mechanism failure
   indicates that the cell must rerun live, and may have ancestors that require
   a re-run as well. In this case, the cell raises a MarimoCancelCellError with
   the set of cells to requeue.
3. Cache miss
   Cache was not found, ancestors do not require re-run, so the cell can run as
   normal with its results saved to cache on teardown.
4. Non-cache related exception
   During a "Cache Miss" execution, the cell body may raise an exception. In
   this case, the exception is propagated to the caller, and the cache is not
   saved.

At the moment, a special carve out for UI elements is made, since UI hydration
requires consistent ID lookup.

The full flow from mermaid ascii demonstrated this below:

+---------------+
|  cell enters  |
|   lifecycle   |
+---------------+
        |
        v
+---------------+
|   hash cell   |
+---------------+
        |
        v
+---------------+
|   cache hit?  |----miss----+
+---------------+            |
        |                    |
       hit                   |
        v                    v
+---------------+       +----------------+
|  restore defs |       |   refs have    |
|   to globals  |-fail->|     stub?      |------+
+---------------+       +----------------+      |
        |                    ^                  |
       ok         +------->stub                 |
        v         |          v                  v
+---------------+ | +--------------+     +-------------+
|    defs are   | | |  are cells   |     |  body runs  |
|    live UI?   |-+ |  stale?      |-no->|             |
+---------------+   +--------------+     +-------------+
        |                    |                  |
       no                   yes                 |
        v                    v                  v
+---------------+   +----------------+   +-------------+
|   skip body,  |   |                |   |             |
|   record key  |   |  raise Cancel  |   |   raised?   |---yes-----+
+---------------+   +----------------+   +-------------+           |
        |                    |                  |                  |
        |                    |                 no                  |
        v                    |                  v                  v
+---------------+    +--------------+    +-------------+   +--------------+
|   teardown:   |    |  teardown:   |    |  teardown:  |   |  teardown:   |
|     no-op     |    |    no-op     |    | save defs + |   | drop attempt |
|               |    |              |    |    return   |   |              |
+---------------+    +--------------+    +-------------+   +--------------+
        |                    |                  |                  |
        v                    v                  v                  v
+---------------+   +----------------+   +-------------+   +--------------+
| 1.  return    |   | 2. scheduler   |   | 3. return   |   | 4. propagate |
|   cached val  |   |     handles    |   |   real val  |   |   exception  |
|               |   |    requeues    |   |             |   |              |
+---------------+   +----------------+   +-------------+   +--------------+
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, cast

from marimo import _loggers
from marimo._runtime.exceptions import MarimoCancelCellError
from marimo._runtime.executor.lifecycles import Skip
from marimo._runtime.runner.result import RunResult
from marimo._save.cache import Cache, CacheException
from marimo._save.hash import cache_attempt_from_hash
from marimo._save.loaders import (
    PERSISTENT_LOADERS,
    BasePersistenceLoader,
    LoaderKey,
    resolve_loader,
)

if TYPE_CHECKING:
    from marimo._ast.cell import CellImpl
    from marimo._runtime.dataflow import DirectedGraph
    from marimo._types.globals import MutableGlobals
    from marimo._types.ids import CellId_t

LOGGER = _loggers.marimo_logger()


def _is_unhashable_stub(value: object) -> bool:
    return getattr(type(value), "__marimo_unhashable__", False) is True


class CachedLifecycle:
    """Skip cell exec on cache hit, populates definitions on cache hit."""

    name = "cached"

    def __init__(
        self,
        graph: DirectedGraph,
        pin_modules: bool = True,
        loader: LoaderKey = "lazy",
    ) -> None:
        self._graph = graph
        self._pin_modules = pin_modules
        # BasePersistenceLoader is the base class for all persistent loaders.
        self._loader = cast(
            BasePersistenceLoader,
            resolve_loader(PERSISTENT_LOADERS[loader])(name="cell_cache"),
        )
        # Per-cell state — populated in setup, consumed in teardown.
        self._attempts: dict[CellId_t, Cache] = {}
        self._exec_starts: dict[CellId_t, float] = {}
        # Per-cell keylookup path, recorded on hit/save.
        self._restored_keys: dict[CellId_t, str] = {}
        # Cells that failed to rehydrate on pre-flight, so we don't requeue
        # them again and again.
        self._invalidated: set[CellId_t] = set()

    def setup(self, cell: CellImpl, glbls: MutableGlobals) -> Skip | None:
        cell_id = cell.cell_id

        attempt = cache_attempt_from_hash(
            cell.mod,
            self._graph,
            cell_id,
            glbls,
            loader=self._loader,
            pin_modules=self._pin_modules,
        )
        self._attempts[cell_id] = attempt

        restored = False
        if attempt.hit:
            try:
                attempt.restore(glbls)
                restored = True
            except (Exception, CacheException) as e:
                LOGGER.warning("Cache restore failed for %s: %s", cell_id, e)
                self._attempts.pop(cell_id, None)
                # Fall through to miss-path execution.

        if restored:
            # Defer loading if restored and not a UI element.
            # TODO(dmadisetti): Attempt to restore UI elements as well.
            # Currently the UIElement class has UIDs that are session-specific.
            # For now, UI construction is cheap and inherently session state.
            if not self._restored_ui_defs(attempt, glbls):
                self._restored_keys[cell_id] = str(
                    self._loader.build_path(attempt.key)
                )
                return Skip(
                    result=RunResult(
                        output=attempt.meta.get("return"), exception=None
                    )
                )

            LOGGER.debug(
                "Cache hit for %s defines UI elements; running "
                "live to register them with this session",
                cell_id,
            )
            self._attempts.pop(cell_id, None)
            # Fall through to miss-path execution.

        # Raises MarimoCancelCellError if any ref requires rehydration.
        self._preflight_refs(cell, glbls)

        self._exec_starts[cell_id] = time.time()
        return None

    def teardown(
        self,
        cell: CellImpl,
        glbls: MutableGlobals,
        run_result: RunResult,
    ) -> None:
        cell_id = cell.cell_id
        # A cell that does have an exception, nor a stub defined in its globals,
        # is considered a successful run and can be totally cached.
        # As a result, it is also removed from the "invalid" set, which can
        # potentially be triggered in a re-run of its ancestors.
        if run_result.exception is None and not self._defines_stub(
            cell, glbls
        ):
            self._invalidated.discard(cell_id)
        attempt = self._attempts.pop(cell_id, None)
        exec_start = self._exec_starts.pop(cell_id, None)

        # Teardown is a no-op a exception or cache hit occurs.
        if attempt is None or run_result.exception is not None:
            return
        if attempt.hit:
            return

        runtime = (time.time() - exec_start) if exec_start else 0.0
        try:
            attempt.update(
                {**glbls},
                meta={
                    "return": run_result.output,
                    "runtime": runtime,
                },
                preserve_pointers=False,
            )
            saved = self._loader.save_cache(attempt)
            if saved:
                self._restored_keys[cell_id] = str(
                    self._loader.build_path(attempt.key)
                )
        except BaseException as e:
            # Best-effort: save failures (incl. CacheException, which
            # extends BaseException) must never break the teardown chain.
            LOGGER.warning("Cache save failed for %s: %s", cell_id, e)

    @staticmethod
    def _defines_stub(cell: CellImpl, glbls: MutableGlobals) -> bool:
        """True if any name the cell defines is still an UnhashableStub."""
        return any(_is_unhashable_stub(glbls.get(name)) for name in cell.defs)

    @staticmethod
    def _restored_ui_defs(attempt: Cache, glbls: MutableGlobals) -> bool:
        """True if any def restored from the cache is a live UIElement."""
        from marimo._plugins.ui._core.ui_element import UIElement

        return any(
            isinstance(glbls.get(name), UIElement) for name in attempt.defs
        )

    def _preflight_refs(self, cell: CellImpl, glbls: MutableGlobals) -> None:
        """Detect UnhashableStub residues in refs and requeue producers.

        Walks `cell.refs` and checks each name in `glbls` for an
        `UnhashableStub` instance. If any are found, invalidates each producer's
        recorded manifest, drops this cell's attempt so teardown will no-op, and
        raises `MarimoCancelCellError` with `cells_to_rerun` populated.
        """
        cell_id = cell.cell_id
        stub_vars: list[str] = []
        for ref in cell.refs:
            value = glbls.get(ref) if ref in glbls else None
            if _is_unhashable_stub(value):
                stub_vars.append(ref)

        if not stub_vars:
            return

        producers: set[CellId_t] = set()
        for var_name in stub_vars:
            try:
                producers.update(self._graph.get_defining_cells(var_name))
            except KeyError:
                pass
        producers.discard(cell_id)

        # Get the cells we have not previously marked as invalidated.
        fresh = {p for p in producers if p not in self._invalidated}
        if not fresh:
            LOGGER.warning(
                "Unsatisfiable reschedule for %s: stub refs %s persist after "
                "rerun; not requeuing",
                cell_id,
                stub_vars,
            )
            return

        for producer_id in fresh:
            self._invalidate(producer_id)

        # Drop our own attempt — body is being skipped this turn, so
        # teardown must not restore defs from the partial scope.
        self._attempts.pop(cell_id, None)
        self._exec_starts.pop(cell_id, None)

        LOGGER.info(
            "Rescheudling for %s: stub refs %s; Cell Ids %s",
            cell_id,
            stub_vars,
            fresh,
        )
        raise MarimoCancelCellError(cells_to_rerun={cell_id} | fresh)

    def _invalidate(self, cell_id: CellId_t) -> None:
        """Invalidate `cell_id`'s manifest so it re-runs live.

        Cells marked invalidated are skipped in future pre-flight check
        to force reruns and prevent recursive deadlocks.
        """
        key = self._restored_keys.pop(cell_id, None)
        self._invalidated.add(cell_id)
        if key is None:
            return
        try:
            self._loader.store.clear(key)
            self._loader.mark_stale(key)
        except Exception as e:
            LOGGER.warning("Manifest invalidate failed for %s: %s", key, e)
