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
import pickle
from typing import TYPE_CHECKING

import pytest

from marimo._runtime.exceptions import (
    MarimoCancelCellError,
    MarimoUnhashableCacheError,
)
from marimo._runtime.executor.lifecycles.cached import CachedLifecycle
from marimo._save.cache import Cache
from marimo._save.loaders.lazy import LazyLoader
from marimo._save.stubs.lazy_stub import UnhashableStub

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
    """A kernel with cell_caching enabled and a tmp cache dir."""
    # Deep-copy so we don't mutate the shared DEFAULT_CONFIG dict.
    mocked_kernel.k.user_config = copy.deepcopy(mocked_kernel.k.user_config)
    mocked_kernel.k.user_config["runtime"]["cell_caching"] = True
    return mocked_kernel


# ---------------------------------------------------------------------------
# UnhashableStub: data + tripwire semantics
# ---------------------------------------------------------------------------


class TestUnhashableStub:
    def test_init_captures_type_info(self) -> None:
        stub = UnhashableStub(
            lambda x: x, var_name="f", error_msg="lambdas not pickleable"
        )
        assert stub.var_name == "f"
        assert "function" in stub.type_name.lower()
        assert stub.error_msg == "lambdas not pickleable"

    def test_load_raises_unhashable_error(self) -> None:
        stub = UnhashableStub(None, var_name="f", error_msg="cannot pickle")
        with pytest.raises(MarimoUnhashableCacheError) as exc_info:
            stub.load({})
        assert "f" in exc_info.value.variables
        assert "cannot pickle" in exc_info.value.error_details

    def test_inherits_cancel_cell_parent(self) -> None:
        """MarimoUnhashableCacheError funnels through the parent class
        in the runner's classifier."""
        err = MarimoUnhashableCacheError(
            cells_to_rerun=set(), variables=[], error_details=""
        )
        assert isinstance(err, MarimoCancelCellError)

    def test_pickle_roundtrip(self) -> None:
        original = UnhashableStub(None, var_name="f", error_msg="oops")
        original.type_name = "builtins.function"
        round_tripped = pickle.loads(pickle.dumps(original))
        assert round_tripped.var_name == "f"
        assert round_tripped.type_name == "builtins.function"
        assert round_tripped.error_msg == "oops"

    def test_isinstance_works(self) -> None:
        """Tripwires must not interfere with isinstance — the restore
        path uses isinstance to decide whether to install the marker."""
        stub = UnhashableStub(None, var_name="f")
        assert isinstance(stub, UnhashableStub)

    def test_repr_does_not_trip(self) -> None:
        """repr is safe to invoke for debugging / logging."""
        stub = UnhashableStub(None, var_name="f", error_msg="oops")
        stub.type_name = "builtins.function"
        text = repr(stub)
        assert "UnhashableStub" in text
        assert "f" in text


class TestUnhashableStubTripwire:
    """`__call__` is the only tripwire (see UnhashableStub docstring).

    Other accesses deliberately fall through to Python defaults so
    framework probes (`getattr(value, "_repr_mimebundle_", None)`,
    `isinstance`, `hasattr`, storage-engine introspection, etc.) stay
    inert and don't cancel innocent cells.
    """

    def _stub(self) -> UnhashableStub:
        return UnhashableStub(None, var_name="x", error_msg="cannot pickle")

    def test_call_trips(self) -> None:
        with pytest.raises(MarimoUnhashableCacheError) as ei:
            self._stub()(42)
        assert ei.value.variables == ["x"]

    def test_getattr_does_not_trip(self) -> None:
        # Falls through to Python's default: a missing attribute raises
        # AttributeError, not the cache tripwire.
        with pytest.raises(AttributeError):
            _ = self._stub().some_method

    def test_len_does_not_trip(self) -> None:
        with pytest.raises(TypeError):
            len(self._stub())

    def test_iter_does_not_trip(self) -> None:
        with pytest.raises(TypeError):
            list(self._stub())

    def test_internal_attrs_dont_trip(self) -> None:
        """var_name / type_name / error_msg / load / to_bytes are
        intentionally accessible — pickling and the runner's classifier
        rely on them."""
        s = self._stub()
        assert s.var_name == "x"
        assert s.type_name == "<unknown>"
        assert s.error_msg == "cannot pickle"
        # load() raises (by design); just confirm the method is reachable.
        with pytest.raises(MarimoUnhashableCacheError):
            s.load({})
        # to_bytes() pickles successfully.
        assert s.to_bytes() == pickle.dumps(s)


# ---------------------------------------------------------------------------
# Cache.restore — total-restore semantics for UnhashableStub
# ---------------------------------------------------------------------------


class TestRestoreUnhashableMarker:
    def test_top_level_marker_preserved(self) -> None:
        """UnhashableStub at the top level of defs is placed in scope as-is,
        not loaded (which would raise)."""
        stub = UnhashableStub(None, var_name="f", error_msg="cannot pickle")
        cache = Cache(
            defs={"f": stub},
            hash="h",
            cache_type="ExecutionPath",
            stateful_refs=set(),
            hit=True,
            meta={},
        )
        scope: dict[str, object] = {}
        cache.restore(scope)
        assert isinstance(scope["f"], UnhashableStub)

    def test_nested_marker_in_container_preserved(self) -> None:
        """UnhashableStub nested in tuple/list/dict survives the recursive
        restore unchanged — the marker propagates instead of triggering
        `.load()` (which raises)."""
        stub = UnhashableStub(None, var_name="g", error_msg="cannot pickle")
        cache = Cache(
            defs={
                "in_tuple": (1, stub, 3),
                "in_list": [stub, "x"],
                "in_dict": {"k": stub},
            },
            hash="h",
            cache_type="ExecutionPath",
            stateful_refs=set(),
            hit=True,
            meta={},
        )
        scope: dict[str, object] = {}
        cache.restore(scope)
        assert scope["in_tuple"][1] is stub  # type: ignore[index]
        assert scope["in_list"][0] is stub  # type: ignore[index]
        assert scope["in_dict"]["k"] is stub  # type: ignore[index]


# ---------------------------------------------------------------------------
# CachedLifecycle._preflight_refs — stub-ref detection routes to requeue
# ---------------------------------------------------------------------------


class TestCachedLifecyclePreflight:
    def test_stub_ref_invalidates_producer_and_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When a consumer's transitive ref resolves to an UnhashableStub
        in scope, pre-flight invalidates the producer's recorded manifest
        and raises MarimoCancelCellError with cells_to_rerun populated, so
        run_all can requeue the producer (plus this cell).
        """
        from unittest.mock import MagicMock

        graph = MagicMock()
        graph.get_defining_cells.return_value = {"producer"}

        life = CachedLifecycle(graph)
        producer_manifest = "lazy/E_producer.jsonl"
        life._manifest_keys["producer"] = producer_manifest

        clear_calls: list[str] = []

        def _spy_clear(key: str) -> bool:
            clear_calls.append(key)
            return True

        monkeypatch.setattr(life._loader.store, "clear", _spy_clear)

        cell = _FakeCell("consumer", refs={"f"})
        glbls = {"f": UnhashableStub(None, var_name="f", error_msg="lambda")}

        with pytest.raises(MarimoCancelCellError) as ei:
            life._preflight_refs(cell, glbls)  # type: ignore[arg-type]

        assert clear_calls == [producer_manifest]
        assert {"producer", "consumer"} <= ei.value.cells_to_rerun

    def test_no_stub_refs_is_noop(self) -> None:
        """Pre-flight returns cleanly when no ref is an UnhashableStub."""
        from unittest.mock import MagicMock

        life = CachedLifecycle(MagicMock())
        cell = _FakeCell("consumer", refs={"x"})
        # No exception expected.
        life._preflight_refs(cell, {"x": 123})  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Integration tests — full kernel with cell_caching enabled
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
        assert any(ld._hits > 0 for ld in new_loaders), (
            "Expected the second run's LazyLoader to record a cache hit"
        )

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
        assert any(ld._hits > 0 for ld in new_loaders)

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
        assert all(ld._hits == 0 for ld in new_loaders)

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
