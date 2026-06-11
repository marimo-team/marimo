# Copyright 2026 Marimo. All rights reserved.
"""CachedLifecycle — cell-level caching as setup/teardown.

On setup: hash the cell + consult the lazy store.

  - HIT  → restore defs into globals, return `Skip` with the cached
           return value so the Evaluator short-circuits the body.
  - MISS → pre-flight `cell.refs`: if any ref in `glbls` is an
           `UnhashableStub` (a stale placeholder left over from an
           upstream cached producer whose value resisted serialization),
           invalidate the producer's manifest and raise
           `MarimoCancelCellError(cells_to_rerun=producers ∪ self)`.
           `Runner.run_all` catches the signal and hands it to
           `Scheduler.requeue_for_rerun`; the body never runs this turn.
           Otherwise, fall through and let the body run.

On teardown: backfill on successful miss; drop the attempt on a raised
body. No body-trip handling — the pre-flight at setup catches it
strictly earlier, against the *refs* rather than reacting to a partial
body's runtime access.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._runtime.exceptions import MarimoCancelCellError
from marimo._runtime.executor.lifecycles import Skip
from marimo._runtime.runner.result import RunResult
from marimo._save.cache import Cache
from marimo._save.hash import cache_attempt_from_hash
from marimo._save.loaders.lazy import LazyLoader
from marimo._save.stubs.lazy_stub import UnhashableStub

if TYPE_CHECKING:
    from marimo._ast.cell import CellImpl
    from marimo._runtime.dataflow import DirectedGraph
    from marimo._types.globals import MutableGlobals
    from marimo._types.ids import CellId_t

LOGGER = _loggers.marimo_logger()


class CachedLifecycle:
    """Skip cell exec on cache hit; backfill cell results on miss success.

    Inner wrap relative to `StrictLifecycle`: when both are configured, the
    Evaluator runs Strict.setup → Cached.setup → body → Cached.teardown →
    Strict.teardown. Caching sees a sanitized scope (Strict already ran),
    and Strict's restore happens after Cached's backfill (so the cache
    captures the cell's real defs).
    """

    name = "cached"

    def __init__(self, graph: DirectedGraph) -> None:
        self._graph = graph
        self._loader = LazyLoader(name="lazy")
        # Per-cell state — populated in setup, consumed in teardown.
        self._attempts: dict[CellId_t, Cache] = {}
        self._exec_starts: dict[CellId_t, float] = {}
        # Per-cell manifest path, recorded on hit/save. Consumed when
        # this cell's pre-flight invalidates an upstream producer.
        self._manifest_keys: dict[CellId_t, str] = {}

    def setup(self, cell: CellImpl, glbls: MutableGlobals) -> Skip | None:
        cell_id = cell.cell_id

        attempt = cache_attempt_from_hash(
            cell.mod,
            self._graph,
            cell_id,
            glbls,
            loader=self._loader,
            pin_modules=True,
        )
        self._attempts[cell_id] = attempt

        if attempt.hit:
            try:
                attempt.restore(glbls)
            except Exception as e:
                LOGGER.warning("Cache restore failed for %s: %s", cell_id, e)
                self._attempts.pop(cell_id, None)
                # Fall through to miss-path execution.
            else:
                self._manifest_keys[cell_id] = str(
                    self._loader.build_path(attempt.key)
                )
                return Skip(
                    result=RunResult(
                        output=attempt.meta.get("return"), exception=None
                    )
                )

        # Pre-flight refs against UnhashableStubs left in scope by upstream
        # cached producers. Raises MarimoCancelCellError if any ref is a
        # stub — body never runs this turn.
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
        attempt = self._attempts.pop(cell_id, None)
        exec_start = self._exec_starts.pop(cell_id, None)

        if attempt is None:
            return
        if attempt.hit:
            return
        if run_result.exception is not None:
            return

        runtime = time.time() - (exec_start if exec_start else time.time())
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
                self._manifest_keys[cell_id] = str(
                    self._loader.build_path(attempt.key)
                )
        except BaseException as e:
            # Best-effort: save failures (incl. CacheException, which
            # extends BaseException) must never break the teardown chain.
            LOGGER.warning("Cache save failed for %s: %s", cell_id, e)

    def _preflight_refs(self, cell: CellImpl, glbls: MutableGlobals) -> None:
        """Detect UnhashableStub residues in refs; requeue producers.

        Walks `cell.refs` and checks each name in `glbls` for an
        `UnhashableStub` instance — a placeholder left behind by an
        upstream cached cell whose def couldn't be serialized. If any
        are found, invalidates each producer's recorded manifest, drops
        this cell's attempt so teardown won't try to backfill, and
        raises `MarimoCancelCellError` with `cells_to_rerun` populated
        so `Runner.run_all` can `Scheduler.requeue_for_rerun` the
        producers (plus this cell, which retries after they produce real
        values).

        Cheap top-level scan: only directly-stub refs trip. Stubs
        embedded inside other values are not detected here — those would
        surface during body execution as a `MarimoUnhashableCacheError`
        from the stub's `__call__`.
        """
        cell_id = cell.cell_id
        stub_vars: list[str] = []
        for ref in cell.refs:
            value = glbls.get(ref) if ref in glbls else None
            if isinstance(value, UnhashableStub):
                stub_vars.append(ref)

        if not stub_vars:
            return

        cells_to_rerun: set[CellId_t] = {cell_id}
        for var_name in stub_vars:
            try:
                cells_to_rerun.update(self._graph.get_defining_cells(var_name))
            except KeyError:
                pass

        for producer_id in cells_to_rerun - {cell_id}:
            self._invalidate(producer_id)

        # Drop our own attempt — body is being skipped this turn, so
        # teardown must not backfill against the partially-restored scope.
        self._attempts.pop(cell_id, None)
        self._exec_starts.pop(cell_id, None)

        LOGGER.info(
            "Pre-flight requeue for %s: stub refs %s; producers %s",
            cell_id,
            stub_vars,
            cells_to_rerun - {cell_id},
        )
        raise MarimoCancelCellError(cells_to_rerun=cells_to_rerun)

    def _invalidate(self, cell_id: CellId_t) -> None:
        """Delete the recorded manifest for `cell_id` (if any)."""
        key = self._manifest_keys.pop(cell_id, None)
        if key is None:
            return
        try:
            self._loader.store.clear(key)
        except Exception as e:
            LOGGER.warning("Manifest clear failed for %s: %s", key, e)
