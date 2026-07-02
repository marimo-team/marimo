# Copyright 2026 Marimo. All rights reserved.
"""CachedLifecycle — cell-level caching as setup/teardown.

On setup: hash the cell + consult the store.

  - HIT  → restore defs into globals, return `Skip` with the cached
           return value so the Evaluator short-circuits the body.
  - MISS → pre-flight `cell.refs`: if any ref in `glbls` is an
           `UnhashableStub` (a stale placeholder left over from an
           upstream cached producer whose value resisted serialization),
           invalidate the producer's manifest and raise
           `MarimoCancelCellError(cells_to_rerun=producers | self)`.
           `Runner.run_all` catches the signal and hands it to
           `Scheduler.requeue_for_rerun`; the body never runs this turn.
           Otherwise, fall through and let the body run.

On teardown: backfill on successful miss; drop the attempt on a raised
body.
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
    """Skip cell exec on cache hit; backfill cell results on miss success."""

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
        # Per-cell manifest path, recorded on hit/save. Consumed when
        # this cell's pre-flight invalidates an upstream producer.
        self._manifest_keys: dict[CellId_t, str] = {}
        # Producers already invalidated for re-execution during THIS run. A
        # `CachedLifecycle` lives for one `Runner` (one `run_all`), so this
        # set resets every reactive round — a later round self-heals once an
        # upstream value recovers. Within a round, a producer that still
        # yields a stub after its rerun is not requeued again, so a stub that
        # can't be recomputed falls through to a tripwire raise instead of
        # looping forever.
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
            if not self._restored_ui_defs(attempt, glbls):
                self._manifest_keys[cell_id] = str(
                    self._loader.build_path(attempt.key)
                )
                return Skip(
                    result=RunResult(
                        output=attempt.meta.get("return"), exception=None
                    )
                )

            # UI construction is cheap and inherently
            # session state.
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
        # Release the requeue guard only once the rerun actually replaced the
        # stubbed value. A run can finish without raising yet still propagate
        # a stub (e.g. `g = f` where `f` is a stub), which must stay guarded
        # or the consumer requeues this producer forever.
        if run_result.exception is None and not self._defines_stub(
            cell, glbls
        ):
            self._invalidated.discard(cell_id)
        attempt = self._attempts.pop(cell_id, None)
        exec_start = self._exec_starts.pop(cell_id, None)

        if attempt is None:
            return
        if attempt.hit:
            return
        if run_result.exception is not None:
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
                self._manifest_keys[cell_id] = str(
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
        """Detect UnhashableStub residues in refs; requeue producers.

        Walks `cell.refs` and checks each name in `glbls` for an
        `UnhashableStub` instance — a placeholder left behind by an
        upstream cached cell whose def couldn't be serialized. If any
        are found, invalidates each producer's recorded manifest, drops
        this cell's attempt so teardown won't try to backfill, and
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

        # Only requeue producers that haven't already been re-run once. A
        # producer we already invalidated that still hands back a stub can't
        # recompute the value here (e.g. it needs an absent dependency), so
        # requeuing again would loop. In that case let the body run: touching
        # the stub raises a clear tripwire error instead of hanging.
        fresh = {p for p in producers if p not in self._invalidated}
        if not fresh:
            LOGGER.warning(
                "Pre-flight for %s: stub refs %s persist after producer "
                "rerun; not requeuing (tripwire raises on access)",
                cell_id,
                stub_vars,
            )
            return

        for producer_id in fresh:
            self._invalidate(producer_id)

        # Drop our own attempt — body is being skipped this turn, so
        # teardown must not backfill against the partially-restored scope.
        self._attempts.pop(cell_id, None)
        self._exec_starts.pop(cell_id, None)

        LOGGER.info(
            "Pre-flight requeue for %s: stub refs %s; producers %s",
            cell_id,
            stub_vars,
            fresh,
        )
        raise MarimoCancelCellError(cells_to_rerun={cell_id} | fresh)

    def _invalidate(self, cell_id: CellId_t) -> None:
        """Invalidate `cell_id`'s manifest so it re-runs live.

        Clears the store entry (the invalidation that on-disk / in-memory
        stores need) and marks it stale: the lazy WASM store would otherwise
        just re-fetch the cleared key over HTTP and re-hit it, so the stale
        mark is what forces a miss there. Together they cover every loader.
        """
        key = self._manifest_keys.pop(cell_id, None)
        self._invalidated.add(cell_id)
        if key is None:
            return
        try:
            self._loader.store.clear(key)
            self._loader.mark_stale(key)
        except Exception as e:
            LOGGER.warning("Manifest invalidate failed for %s: %s", key, e)
