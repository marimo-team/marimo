# Copyright 2025 Marimo. All rights reserved.
"""Integration tests for lazy cache behavior (TDD edge cases).

These tests codify desired behaviors for caching and hydration.
They intentionally fail today to drive implementation (assertion failures only).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from marimo._runtime.runtime import Kernel
from marimo._save.stores.memory import MemoryStore
from tests.conftest import ExecReqProvider

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def memory_store() -> Generator[MemoryStore, None, None]:
    store = MemoryStore()
    try:
        yield store
    finally:
        store.clear_all()


async def test_successful_run_writes_cache(
    k: Kernel, memory_store: MemoryStore, exec_req: ExecReqProvider
) -> None:
    """A successful run should always result in a saved cache artifact."""
    k.execution_type = "cached"

    with patch("marimo._save.stores.get_store", return_value=memory_store):
        cell = exec_req.get("x = 1; x")
        await k.run([cell])

        # A cache record (.txtpb) should exist for this cell id
        keys = [
            key
            for key in memory_store._keys
            if key.endswith(".txtpb") and cell.cell_id in key
        ]
        assert keys, "Expected a cache entry (*.txtpb) for the executed cell"


async def test_immediate_reference_return_is_hydrated_on_hit(
    k: Kernel, memory_store: MemoryStore, exec_req: ExecReqProvider
) -> None:
    """Large return should be restored from an ImmediateReference on cache hit."""
    k.execution_type = "cached"

    with patch("marimo._save.stores.get_store", return_value=memory_store):
        cell = exec_req.get("list(range(10000))")

        result1 = await k.run([cell])
        assert result1 is not None
        assert isinstance(result1[-1], list)
        assert len(result1[-1]) == 10000

        # Second run should hydrate from cache (not return a stub)
        result2 = await k.run([cell])
        assert result2 is not None
        assert isinstance(result2[-1], list), (
            f"Expected hydrated list, got {type(result2[-1])}"
        )
        assert len(result2[-1]) == 10000


async def test_unhashable_return_cache_hit_should_rerun(
    k: Kernel, memory_store: MemoryStore, exec_req: ExecReqProvider
) -> None:
    """On cache hit, an unpicklable return should not be returned as a stub.

    Desired behavior: auto-rerun the cell and return a callable function.
    Current behavior: returns an UnhashableStub; this test should fail
    with an assertion error until behavior is implemented.
    """
    k.execution_type = "cached"

    with patch("marimo._save.stores.get_store", return_value=memory_store):
        cell = exec_req.get("(lambda: 42)")
        result1 = await k.run([cell])
        assert result1 is not None
        assert callable(result1[-1])  # cold run returns the actual lambda

        result2 = await k.run([cell])
        # TDD expectation: hit should re-execute (not return a stub)
        assert callable(result2[-1]), (
            "Cache hit should return a callable (rerun), not a stub"
        )
