# Copyright 2026 Marimo. All rights reserved.
"""Tests for CachedLifecycle — cell-level caching as a per-cell lifecycle.

Ported from the original cell-caching test suite and adapted to the
integrated `executor/lifecycles` framework (the source branch's
`CachedStage`/`wrappers` names were abandoned intermediate renames).
UnhashableStub tripwire assertions follow the shipped design: `__call__`
is the only tripwire; other accesses fall through to Python defaults.
"""

from __future__ import annotations

import copy
import dataclasses
from typing import TYPE_CHECKING

import pytest

from marimo._runtime.exceptions import (
    MarimoRescheduleError,
)
from marimo._runtime.executor.lifecycles.cached import CachedLifecycle
from marimo._save.loaders.lazy import LazyLoader

try:
    # Ships with the stub serialization toolkit; the lifecycle detects
    # stubs through the __marimo_unhashable__ protocol attribute and has
    # no hard dependency on the class.
    from marimo._save.stubs.lazy_stub import UnhashableStub
except ImportError:  # pragma: no cover
    UnhashableStub = None  # type: ignore[assignment]

# The end-to-end tripwire tests additionally need the lazy loader that
# *produces* UnhashableStub on serialization failure.
try:
    from marimo._save.loaders.lazy import LazyStore as _LazyStore
except ImportError:  # pragma: no cover
    _LazyStore = None  # type: ignore[assignment]

requires_stub_loader = pytest.mark.skipif(
    UnhashableStub is None or _LazyStore is None,
    reason="needs the stub toolkit + per-def lazy store",
)


@dataclasses.dataclass
class _MarkerStub:
    """Minimal stand-in carrying the unhashable-stub protocol marker."""

    # Class-level protocol marker (no annotation → not a dataclass field).
    __marimo_unhashable__ = True

    var_name: str


if TYPE_CHECKING:
    from pathlib import Path

    from tests.conftest import ExecReqProvider, MockedKernel


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect FileStore's default save path to a tmp dir for the test."""
    cache_path = tmp_path / "cache"
    cache_path.mkdir()

    def _default_save_path(_self: object) -> Path:
        return cache_path

    monkeypatch.setattr(
        "marimo._save.stores.file.FileStore._default_save_path",
        _default_save_path,
    )
    return cache_path


@pytest.fixture
def tracked_loaders(monkeypatch: pytest.MonkeyPatch) -> list[LazyLoader]:
    """Capture every LazyLoader instance constructed during the test.

    Lifecycles live on each Runner instance and are GC'd between runs, so
    there's no kernel-level handle on the loader. Tracking via __init__
    lets tests call .flush() on every loader to drain background save
    threads deterministically (instead of sleeping).
    """
    instances: list[LazyLoader] = []
    original_init = LazyLoader.__init__

    def _tracking_init(
        self: LazyLoader,
        *args: object,
        **kwargs: object,
    ) -> None:
        original_init(self, *args, **kwargs)  # type: ignore[arg-type]
        instances.append(self)

    monkeypatch.setattr(LazyLoader, "__init__", _tracking_init)
    return instances


@pytest.fixture
def caching_kernel(
    mocked_kernel: MockedKernel,
    cache_dir: Path,  # noqa: ARG001 — needed for side effect
    tracked_loaders: list[LazyLoader],  # noqa: ARG001 — needed for side effect
) -> MockedKernel:
    """A kernel with cache_cells enabled and a tmp cache dir."""
    # Deep-copy so we don't mutate the shared DEFAULT_CONFIG dict.
    mocked_kernel.k.user_config = copy.deepcopy(mocked_kernel.k.user_config)
    mocked_kernel.k.user_config["runtime"]["cache_cells"] = True
    return mocked_kernel


# ---------------------------------------------------------------------------
# CachedLifecycle._preflight_refs — stub-ref detection routes to requeue
# ---------------------------------------------------------------------------


class TestCachedLifecyclePreflight:
    def test_stub_ref_invalidates_producer_and_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When a consumer's transitive ref resolves to an UnhashableStub in
        scope, pre-flight marks the producers as stale (so it re-runs live
        rather than re-hitting the same unusable value) and raises
        MarimoRescheduleError with cells_to_rerun populated, so run_all can
        requeue the producer (plus this cell).
        """
        from unittest.mock import MagicMock

        graph = MagicMock()
        graph.get_defining_cells.return_value = {"producer"}

        life = CachedLifecycle(graph)
        producer_manifest = "lazy/E_producer.jsonl"
        life._restored_keys["producer"] = producer_manifest

        # Invalidation both clears the store entry (for on-disk/in-memory
        # stores) and marks it stale (so the lazy WASM store can't re-fetch
        # and re-hit the same value over HTTP).
        stale_calls: list[str] = []
        clear_calls: list[str] = []
        monkeypatch.setattr(
            life._loader, "mark_stale", lambda key: stale_calls.append(key)
        )
        monkeypatch.setattr(
            life._loader.store,
            "clear",
            lambda key: bool(clear_calls.append(key)),
        )

        cell = _FakeCell("consumer", refs={"f"})
        glbls = {"f": _MarkerStub("f")}

        with pytest.raises(MarimoRescheduleError) as ei:
            life._preflight_refs(cell, glbls)  # type: ignore[arg-type]

        assert stale_calls == [producer_manifest]
        assert clear_calls == [producer_manifest]
        assert {"producer", "consumer"} <= ei.value.cells_to_rerun

    def test_persistent_stub_producer_not_requeued_twice(self) -> None:
        """A producer already invalidated once that still hands back a stub
        is not requeued again: pre-flight returns cleanly so the body runs
        and the tripwire raises on access, rather than looping forever.
        """
        from unittest.mock import MagicMock

        graph = MagicMock()
        graph.get_defining_cells.return_value = {"producer"}

        life = CachedLifecycle(graph)
        # Producer already had its rerun and still yields a stub.
        life._invalidated.add("producer")

        cell = _FakeCell("consumer", refs={"f"})
        glbls = {"f": _MarkerStub("f")}
        # No MarimoRescheduleError — falls through to run the body.
        life._preflight_refs(cell, glbls)  # type: ignore[arg-type]

    def test_invalidated_guard_resets_on_clean_rerun(self) -> None:
        """A producer guarded after invalidation is released once it runs
        cleanly, so a later pre-flight can requeue it again. Only a cell that
        keeps erroring stays guarded — that is the loop the bound stops.
        """
        from unittest.mock import MagicMock

        from marimo._runtime.runner.result import RunResult

        life = CachedLifecycle(MagicMock())
        producer = _FakeCell("producer")
        producer.defs = {"g"}

        # A clean run that replaced the stub releases the guard.
        life._invalidated.add("producer")
        life.teardown(
            producer,  # type: ignore[arg-type]
            {"g": 123},
            RunResult(output=None, exception=None),
        )
        assert "producer" not in life._invalidated

        # A clean run that still PROPAGATES a stub stays guarded (e.g. `g = f`
        # where f is a stub) — otherwise the consumer requeues it forever.
        life._invalidated.add("producer")
        life.teardown(
            producer,  # type: ignore[arg-type]
            {"g": _MarkerStub("g")},
            RunResult(output=None, exception=None),
        )
        assert "producer" in life._invalidated

        # An erroring run keeps it guarded (so it can't loop).
        life._invalidated.add("producer")
        life.teardown(
            producer,  # type: ignore[arg-type]
            {},
            RunResult(output=None, exception=ValueError("boom")),
        )
        assert "producer" in life._invalidated

    def test_no_stub_refs_is_noop(self) -> None:
        """Pre-flight returns cleanly when no ref is an UnhashableStub."""
        from unittest.mock import MagicMock

        life = CachedLifecycle(MagicMock())
        cell = _FakeCell("consumer", refs={"x"})
        # No exception expected.
        life._preflight_refs(cell, {"x": 123})  # type: ignore[arg-type]

    def test_restore_cache_exception_falls_through_to_miss(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`Cache.restore` can raise `CacheException`, which subclasses
        `BaseException` (not `Exception`). Setup must catch it explicitly
        so a corrupt-cache hit falls through to miss-path execution rather
        than escaping as a hard cell error.
        """
        from unittest.mock import MagicMock

        import marimo._runtime.executor.lifecycles.cached as cached_mod
        from marimo._save.cache import CacheException

        life = CachedLifecycle(MagicMock())

        attempt = MagicMock()
        attempt.hit = True
        attempt.restore.side_effect = CacheException("corrupt blob")
        monkeypatch.setattr(
            cached_mod, "cache_attempt_from_hash", lambda *_a, **_k: attempt
        )

        cell = _FakeCell("consumer", refs=set())
        # Must not raise; returns None (miss path) and drops the attempt.
        assert life.setup(cell, {}) is None  # type: ignore[arg-type]
        assert "consumer" not in life._attempts
        attempt.restore.assert_called_once()


# ---------------------------------------------------------------------------
# Integration tests — full kernel with cache_cells enabled
# ---------------------------------------------------------------------------


class TestCachedLifecycleIntegration:
    async def test_basic_hit_miss_cycle(
        self,
        caching_kernel: MockedKernel,
        exec_req: ExecReqProvider,
        tracked_loaders: list[LazyLoader],
    ) -> None:
        """First run misses + executes; second run with same code hits."""
        k = caching_kernel.k
        er = exec_req.get(code="x = 1 + 2")

        await k.run([er])
        assert k.globals["x"] == 3

        for loader in tracked_loaders:
            loader.flush()

        loaders_before_second = list(tracked_loaders)
        await k.run([er])
        assert k.globals["x"] == 3

        new_loaders = [
            ld for ld in tracked_loaders if ld not in loaders_before_second
        ]
        assert new_loaders, "Expected a fresh LazyLoader for the second run"
        assert any(ld.hits > 0 for ld in new_loaders), (
            "Expected the second run's LazyLoader to record a cache hit"
        )

    @requires_stub_loader
    async def test_unhashable_own_def_does_not_auto_rerun(
        self,
        caching_kernel: MockedKernel,
        exec_req: ExecReqProvider,
        tracked_loaders: list[LazyLoader],
    ) -> None:
        """Cell whose own def is a lambda: cache hit on next session,
        body skipped, marker in scope. Not auto-rerun (that would defeat
        caching for cells where downstream never needs the real value).
        """
        k = caching_kernel.k
        er = exec_req.get(code="f = lambda x: x + 1")

        await k.run([er])
        assert callable(k.globals["f"])
        assert k.globals["f"](2) == 3

        for loader in tracked_loaders:
            loader.flush()

        # Simulate fresh session.
        k.globals.pop("f", None)

        loaders_before_second = list(tracked_loaders)
        await k.run([er])
        new_loaders = [
            ld for ld in tracked_loaders if ld not in loaders_before_second
        ]

        # Body skipped — `f` in scope is the UnhashableStub marker.
        assert isinstance(k.globals.get("f"), UnhashableStub)
        assert any(ld.hits > 0 for ld in new_loaders)

    async def test_failed_run_not_cached(
        self,
        caching_kernel: MockedKernel,
        exec_req: ExecReqProvider,
        tracked_loaders: list[LazyLoader],
    ) -> None:
        k = caching_kernel.k
        er = exec_req.get(code="raise RuntimeError('boom')")

        await k.run([er])

        for loader in tracked_loaders:
            loader.flush()

        loaders_before_second = list(tracked_loaders)
        await k.run([er])

        new_loaders = [
            ld for ld in tracked_loaders if ld not in loaders_before_second
        ]
        assert new_loaders
        assert all(ld.hits == 0 for ld in new_loaders)

    @requires_stub_loader
    async def test_consumer_calling_lambda_recovers(
        self,
        caching_kernel: MockedKernel,
        exec_req: ExecReqProvider,
        tracked_loaders: list[LazyLoader],
    ) -> None:
        """Producer A defines a lambda; consumer B references it directly.
        After fresh-kernel reset, A hits cache (stub in scope), B's hash
        differs and misses, B's pre-flight sees the stub in its refs →
        invalidates A and requeues. A re-runs with the real lambda; B
        retries; `g == 15`.
        """
        k = caching_kernel.k
        producer = exec_req.get(code="f = lambda x: x + 10")
        consumer = exec_req.get(code="g = f(5)")

        await k.run([producer, consumer])
        assert k.globals["g"] == 15

        for loader in tracked_loaders:
            loader.flush()

        # Simulate fresh session.
        k.globals.pop("f", None)
        k.globals.pop("g", None)

        await k.run([producer, consumer])
        assert k.globals["g"] == 15
        assert callable(k.globals["f"])
        assert not isinstance(k.globals["f"], UnhashableStub)
        assert not isinstance(k.globals["g"], UnhashableStub)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeCell:
    def __init__(self, cell_id: str, refs: set[str] | None = None) -> None:
        self.cell_id = cell_id
        self.refs = refs or set()
        self.defs: set[str] = set()
        self.mod = None
