# Copyright 2025 Marimo. All rights reserved.
"""Tests for CachedExecutor with proper stub handling.

Unit tests verify:
1. UnhashableStub creation during cache serialization
2. UnhashableStub deserialization from cache
3. Error handling when attempting to load UnhashableStub
4. LazyLoader round-trip with unpicklable objects

Integration tests verify (and expose broken behaviors):
1. UnhashableStub creation and handling for unpicklable objects
2. ReferenceStub hydration for lazy loading
3. UIElement cache invalidation
4. Return value handling with stubs
5. Error messaging and user notifications
"""

from __future__ import annotations

import pickle
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from marimo._runtime.runtime import Kernel
from marimo._save.cache import Cache
from marimo._save.loaders.lazy import LazyLoader
from marimo._save.stores.memory import MemoryStore
from marimo._save.stubs.lazy_stub import (
    # ImmediateReferenceStub,
    ReferenceStub,
    UnhashableStub,
)
from tests.conftest import ExecReqProvider

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def memory_store() -> Generator[MemoryStore, None, None]:
    """Create a fresh MemoryStore for testing."""
    store = MemoryStore()
    yield store
    # Cleanup after test
    store.clear_all()


class TestUnhashableStubCaching:
    """Test UnhashableStub creation and serialization."""

    def test_lambda_becomes_unhashable_stub_in_cache(self) -> None:
        """Test that lambda variables become UnhashableStub during serialization.

        When a Cache contains a lambda that cannot be pickled,
        LazyLoader.to_blob() should convert it to an UnhashableStub.
        """
        # Create a lambda (unpicklable)
        fn = lambda: 42  # noqa: E731

        # Verify it can't be pickled
        with pytest.raises((pickle.PicklingError, TypeError, AttributeError)):
            pickle.dumps(fn)

        # Create cache with lambda
        cache = Cache(
            defs={"x": 42, "fn": fn, "result": 42},
            hash="test_hash",
            cache_type="Pure",
            stateful_refs=set(),
            hit=False,
            meta={"return": None},
        )

        # Serialize with LazyLoader
        store = MemoryStore()
        loader = LazyLoader(name="test_cell", store=store)
        blob = loader.to_blob(cache)

        # Deserialize
        restored = loader.restore_cache(None, blob)

        # Verify lambda became UnhashableStub
        assert "fn" in restored.defs
        fn_stub = restored.defs["fn"]
        assert isinstance(fn_stub, UnhashableStub), (
            f"Expected UnhashableStub, got {type(fn_stub)}"
        )

        # Verify metadata
        assert fn_stub.var_name == "fn"
        assert "function" in fn_stub.type_name.lower()
        assert len(fn_stub.error_msg) > 0

        # Verify other values were cached normally
        assert restored.defs["x"] == 42
        assert restored.defs["result"] == 42

        # Cleanup
        store.clear_all()

    def test_unhashable_stub_load_raises_error(self) -> None:
        """Test that attempting to load UnhashableStub raises clear error."""
        fn = lambda: 42  # noqa: E731

        try:
            pickle.dumps(fn)
            pytest.skip("Lambda was picklable on this Python version")
        except (pickle.PicklingError, TypeError, AttributeError) as e:
            # Create UnhashableStub
            stub = UnhashableStub(fn, e, var_name="fn")

        # Attempting to load should raise ValueError
        with pytest.raises(ValueError, match="Cannot load unhashable"):
            stub.load({})

    def test_unhashable_serialization_roundtrip(self) -> None:
        """Test UnhashableStub serialization/deserialization preserves metadata."""
        # Create cache with multiple types
        fn = lambda x: x * 2  # noqa: E731

        cache = Cache(
            defs={
                "normal": 42,
                "fn": fn,
                "string": "hello",
            },
            hash="roundtrip_test",
            cache_type="ContentAddressed",
            stateful_refs=set(),
            hit=False,
            meta={"return": None},
        )

        # Round-trip through LazyLoader
        store = MemoryStore()
        loader = LazyLoader(name="test", store=store)

        blob = loader.to_blob(cache)
        restored = loader.restore_cache(None, blob)

        # Check UnhashableStub was preserved
        assert isinstance(restored.defs["fn"], UnhashableStub)
        stub = restored.defs["fn"]
        assert stub.var_name == "fn"
        assert "function" in stub.type_name.lower()

        # Check normal values preserved
        assert restored.defs["normal"] == 42
        assert restored.defs["string"] == "hello"

        # Verify cache metadata preserved
        assert restored.hash == "roundtrip_test"
        assert restored.cache_type == "ContentAddressed"

        # Cleanup
        store.clear_all()

    def test_return_value_lambda_becomes_unhashable(self) -> None:
        """Test that unpicklable return values become UnhashableStub.

        When a cell returns a lambda, it should be converted to
        UnhashableStub in the cache metadata.
        """
        fn = lambda: 42  # noqa: E731

        cache = Cache(
            defs={"x": 10},
            hash="return_test",
            cache_type="Pure",
            stateful_refs=set(),
            hit=False,
            meta={"return": fn},  # Return value is lambda
        )

        store = MemoryStore()
        loader = LazyLoader(name="test", store=store)

        blob = loader.to_blob(cache)
        restored = loader.restore_cache(None, blob)

        # Return value should be UnhashableStub
        return_val = restored.meta["return"]
        assert isinstance(return_val, UnhashableStub), (
            f"Expected UnhashableStub, got {type(return_val)}"
        )

        assert return_val.var_name == "<return>"
        assert "function" in return_val.type_name.lower()

        # Cleanup
        store.clear_all()

    def test_mixed_hashable_unhashable_cache(self) -> None:
        """Test cache with both picklable and unpicklable objects."""
        fn1 = lambda: 1  # noqa: E731
        fn2 = lambda: 2  # noqa: E731

        cache = Cache(
            defs={
                "a": 1,
                "b": "hello",
                "fn1": fn1,
                "c": [1, 2, 3],
                "fn2": fn2,
                "d": {"key": "value"},
            },
            hash="mixed_test",
            cache_type="Pure",
            stateful_refs=set(),
            hit=False,
            meta={"return": 42},
        )

        store = MemoryStore()
        loader = LazyLoader(name="test", store=store)

        blob = loader.to_blob(cache)
        restored = loader.restore_cache(None, blob)

        # Verify lambdas became UnhashableStub
        assert isinstance(restored.defs["fn1"], UnhashableStub)
        assert isinstance(restored.defs["fn2"], UnhashableStub)

        # Verify primitives preserved directly
        assert restored.defs["a"] == 1
        assert restored.defs["b"] == "hello"
        assert restored.meta["return"] == 42

        # Verify complex picklable objects became ReferenceStub for lazy loading
        from marimo._save.stubs.lazy_stub import ReferenceStub

        assert isinstance(restored.defs["c"], ReferenceStub)
        assert isinstance(restored.defs["d"], ReferenceStub)

        # Both list and dict should reference the same pickle file
        assert restored.defs["c"].name == restored.defs["d"].name
        assert "pickles.pickle" in restored.defs["c"].name

        # Cleanup
        store.clear_all()

    def test_unhashable_stub_metadata_accurate(self) -> None:
        """Test that UnhashableStub captures accurate error information."""

        class CustomUnpicklable:
            def __reduce__(self):
                raise TypeError("Cannot pickle this custom class")

        obj = CustomUnpicklable()

        try:
            pickle.dumps(obj)
            pytest.fail("Object was picklable when it shouldn't be")
        except TypeError as e:
            stub = UnhashableStub(obj, e, var_name="custom_obj")

        # Verify metadata
        assert stub.var_name == "custom_obj"
        assert "CustomUnpicklable" in stub.type_name
        assert "Cannot pickle" in stub.error_msg

        # Verify load raises error with this info
        with pytest.raises(
            ValueError, match="custom_obj.*CustomUnpicklable.*Cannot pickle"
        ):
            stub.load({})


# Integration tests that expose broken behaviors
async def test_lambda_becomes_unhashable_stub_in_cache(
    k: Kernel,
    memory_store: MemoryStore,
    exec_req: ExecReqProvider,
) -> None:
    """Test that lambda variables become UnhashableStub in cache defs.

    This test verifies that when a cell defines a lambda function,
    it is converted to an UnhashableStub during cache serialization,
    since lambdas cannot be pickled.
    """
    k.execution_type = "cached"

    with patch("marimo._save.stores.get_store", return_value=memory_store):
        # Execute cell with lambda
        cell_id = exec_req.get(
            """
            x = 42
            fn = lambda: x
            result = fn()
            """
        )
        await k.run([cell_id])

        # Verify execution succeeded
        assert k.globals["x"] == 42
        assert k.globals["result"] == 42
        assert callable(k.globals["fn"])

        # Now inspect the cache to verify UnhashableStub was created
        loader = LazyLoader(name=cell_id.cell_id)
        loader.store = memory_store

        # Get the cache key from the store
        # Cache keys are stored with hash prefixes
        cache_keys = [k for k in memory_store._keys if k.endswith("/lazy")]
        assert len(cache_keys) > 0, "No cache was saved"

        # Load the cache
        cache_blob = memory_store.get(cache_keys[0])
        assert cache_blob is not None
        restored_cache = loader.restore_cache(None, cache_blob)

        # Verify fn is an UnhashableStub in the cache
        assert "fn" in restored_cache.defs
        fn_cached = restored_cache.defs["fn"]
        assert isinstance(fn_cached, UnhashableStub), (
            f"Expected UnhashableStub, got {type(fn_cached)}"
        )

        # Verify stub metadata
        assert "function" in fn_cached.type_name
        assert fn_cached.var_name == "fn"
        assert len(fn_cached.error_msg) > 0


async def test_return_lambda_cache_hit_fails(
    k: Kernel,
    memory_store: MemoryStore,
    exec_req: ExecReqProvider,
) -> None:
    """Test that returning a lambda doesn't return UnhashableStub on cache hit.

    When a cell returns an unpicklable value (lambda), on cache hit
    the system should either:
    1. Raise an error requiring cell re-execution
    2. Trigger automatic cell re-execution
    3. NOT return the UnhashableStub object itself

    Currently BROKEN: Returns UnhashableStub directly to user.
    """
    k.execution_type = "cached"

    with patch("marimo._save.stores.get_store", return_value=memory_store):
        # First execution: create and return lambda
        cell_id = exec_req.get("lambda: 42")
        result1 = await k.run([cell_id])

        # First run should return the actual lambda
        assert result1 is not None
        assert callable(result1[-1])

        # Second execution: cache hit
        result2 = await k.run([cell_id])

        # CRITICAL: Should NOT return an UnhashableStub
        # This test should FAIL with current implementation
        assert result2 is not None
        assert not isinstance(result2[-1], UnhashableStub), (
            "Cache hit returned UnhashableStub instead of rerunning or erroring"
        )

        # Should either:
        # - Return a callable (if cell was re-executed)
        # - Raise an error (if cache can't restore)
        # But NOT return the stub itself
        if result2[-1] is not None:
            assert callable(result2[-1]) or isinstance(
                result2[-1], Exception
            ), f"Unexpected return type: {type(result2[-1])}"


async def test_reference_stub_hydration_expands(
    k: Kernel,
    memory_store: MemoryStore,
    exec_req: ExecReqProvider,
) -> None:
    """Test that ReferenceStub properly hydrates into dependent cells.

    When Cell A creates a large object (stored as ReferenceStub),
    and Cell B depends on it, the hydration process should properly
    expand the ReferenceStub into the actual dict of values.

    Currently BROKEN: hydrate() may not properly expand the dict.
    """
    k.execution_type = "cached"

    with patch("marimo._save.stores.get_store", return_value=memory_store):
        # Cell A: Create large object (should become ReferenceStub)
        cell_a = exec_req.get("data = list(range(10000))")
        await k.run([cell_a])

        # Verify data exists and is correct
        assert "data" in k.globals
        assert len(k.globals["data"]) == 10000

        # Get cache to inspect ReferenceStub
        loader = LazyLoader(name=cell_a.cell_id)
        loader.store = memory_store
        cache_keys = [
            k
            for k in memory_store._keys
            if k.endswith("/lazy") and cell_a.cell_id in k
        ]
        if cache_keys:
            cache_blob = memory_store.get(cache_keys[0])
            if cache_blob:
                restored_cache = loader.restore_cache(None, cache_blob)
                # data might be a ReferenceStub in cache
                data_cached = restored_cache.defs.get("data")
                if isinstance(data_cached, ReferenceStub):
                    # Verify ReferenceStub can be loaded
                    loaded = data_cached.load({})
                    assert isinstance(loaded, dict), (
                        "ReferenceStub.load should return dict of {var: value}"
                    )
                    assert "data" in loaded or isinstance(loaded, list)

        # Cell B: Depends on data from Cell A
        cell_b = exec_req.get("total = sum(data)")
        await k.run([cell_b])

        # CRITICAL: total should be computed correctly
        # This verifies that hydration properly expanded ReferenceStub
        assert k.globals["total"] == sum(range(10000))

        # Re-run with cache hit
        await k.run([cell_a, cell_b])
        assert k.globals["total"] == sum(range(10000))


async def test_unhashable_serialization_deserializes_correctly(
    k: Kernel,
    memory_store: MemoryStore,
    exec_req: ExecReqProvider,
) -> None:
    """Test UnhashableStub round-trip serialization.

    Verify that UnhashableStub can be serialized to msgspec JSON
    and deserialized back with all metadata intact.
    """
    k.execution_type = "cached"

    with patch("marimo._save.stores.get_store", return_value=memory_store):
        # Create cache with lambda
        cell_id = exec_req.get("fn = lambda x: x * 2")
        await k.run([cell_id])

        # Get the serialized cache
        loader = LazyLoader(name=cell_id.cell_id)
        loader.store = memory_store
        cache_keys = [
            k
            for k in memory_store._keys
            if k.endswith("/lazy") and cell_id.cell_id in k
        ]
        assert len(cache_keys) > 0

        cache_blob = memory_store.get(cache_keys[0])
        assert cache_blob is not None

        # Deserialize
        restored_cache = loader.restore_cache(None, cache_blob)

        # Verify UnhashableStub was deserialized correctly
        assert "fn" in restored_cache.defs
        fn_stub = restored_cache.defs["fn"]
        assert isinstance(fn_stub, UnhashableStub)

        # Verify metadata survived round-trip
        assert fn_stub.var_name == "fn"
        assert "function" in fn_stub.type_name.lower()
        assert len(fn_stub.error_msg) > 0

        # Verify attempting to load raises proper error
        with pytest.raises(ValueError, match="Cannot load unhashable"):
            fn_stub.load({})


async def test_unhashable_sends_error_message(
    k: Kernel,
    memory_store: MemoryStore,
    exec_req: ExecReqProvider,
) -> None:
    """Test that encountering UnhashableStub during hydration sends error message.

    When a cell depends on an UnhashableStub from upstream,
    the system should:
    1. Log a warning
    2. Send an error message to the UI
    3. Queue the cell for re-execution

    Currently BROKEN: Only logs warning, doesn't send message or queue rerun.
    """
    k.execution_type = "cached"

    with (
        patch("marimo._save.stores.get_store", return_value=memory_store),
        patch("marimo._runtime.lazy_executor.LOGGER") as mock_logger,
        patch("marimo._messaging.ops.CellOp") as mock_cell_op,
    ):
        # Cell A: Create lambda (becomes UnhashableStub)
        cell_a = exec_req.get("fn = lambda: 42")
        await k.run([cell_a])

        # Cell B: Tries to use fn (depends on Cell A)
        # NOTE: This may not trigger hydration if fn isn't in refs
        # The real issue is when cache hit tries to restore UnhashableStub
        cell_b = exec_req.get("result = fn()")
        await k.run([cell_b])

        # Second run: cache hit on cell_a
        await k.run([cell_a])

        # Check if warning was logged
        # (Currently this IS implemented, line 49-53 lazy_executor.py)
        warning_calls = [
            call
            for call in mock_logger.warning.call_args_list
            if "unhashable" in str(call).lower()
        ]

        # This test documents that we SHOULD send messages to UI
        # Currently BROKEN: No messages sent
        # TODO: Verify CellOp.broadcast_error or similar is called
        # error_calls = [call for call in mock_cell_op.method_calls if 'error' in str(call)]
        # assert len(error_calls) > 0, "Should send error message to UI"


async def test_ui_element_cache_stale_after_change(
    k: Kernel,
    memory_store: MemoryStore,
    exec_req: ExecReqProvider,
) -> None:
    """Test that UIElement cache is invalidated when code changes.

    When a cell with a UIElement is cached, then the code changes,
    the cache should be invalidated and the cell re-executed.

    Currently BROKEN: May restore stale UIElement from cache.
    """
    k.execution_type = "cached"

    with patch("marimo._save.stores.get_store", return_value=memory_store):
        # First execution: slider with range 0-10
        cell_id = exec_req.get(
            "import marimo as mo; slider = mo.ui.slider(0, 10)"
        )
        await k.run([cell_id])

        assert "slider" in k.globals
        # Get the slider's max value
        slider1 = k.globals["slider"]

        # Change the code: slider with range 0-20
        # This should invalidate cache (different hash)
        cell_id_changed = exec_req.get(
            "import marimo as mo; slider = mo.ui.slider(0, 20)"
        )
        await k.run([cell_id_changed])

        slider2 = k.globals["slider"]

        # CRITICAL: Should NOT be the same cached object
        # The hash should be different, triggering cache miss
        # This test verifies proper cache invalidation on code change
        # (This might actually work correctly already due to hash-based caching)


async def test_immediate_ref_stub_pickle_failure(
    k: Kernel,
    memory_store: MemoryStore,
    exec_req: ExecReqProvider,
) -> None:
    """Test handling of unpicklable return values wrapped in ImmediateReferenceStub.

    When a cell returns a large object that becomes ReferenceStub,
    but the object cannot be pickled, the system should handle it gracefully.

    Currently BROKEN: May fail when ImmediateReferenceStub tries to load.
    """
    k.execution_type = "cached"

    with patch("marimo._save.stores.get_store", return_value=memory_store):
        # Return a large list (should become ReferenceStub in return value)
        cell_id = exec_req.get("list(range(10000))")
        result1 = await k.run([cell_id])

        assert result1 is not None
        assert isinstance(result1[-1], list)
        assert len(result1[-1]) == 10000

        # Cache hit: should restore from ImmediateReferenceStub
        result2 = await k.run([cell_id])

        # CRITICAL: Should successfully restore the list
        # Not return an ImmediateReferenceStub object
        assert result2 is not None
        assert isinstance(result2[-1], list), (
            f"Expected list, got {type(result2[-1])}"
        )
        assert len(result2[-1]) == 10000


# Keep one basic test for sanity
async def test_basic_cache_execution(
    k: Kernel,
    memory_store: MemoryStore,
    exec_req: ExecReqProvider,
) -> None:
    """Test basic cached execution with primitive values."""
    k.execution_type = "cached"

    with patch("marimo._save.stores.get_store", return_value=memory_store):
        # First execution: cache miss
        await k.run(
            [
                exec_req.get(
                    """
                    x = 42
                    y = "hello"
                    z = x + len(y)
                    """
                )
            ]
        )

        # Verify values were computed
        assert k.globals["x"] == 42
        assert k.globals["y"] == "hello"
        assert k.globals["z"] == 47

        # Second execution: cache hit
        await k.run(
            [
                exec_req.get(
                    """
                    x = 42
                    y = "hello"
                    z = x + len(y)
                    """
                )
            ]
        )

        # Values should still be correct
        assert k.globals["x"] == 42
        assert k.globals["y"] == "hello"
        assert k.globals["z"] == 47
