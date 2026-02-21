# Copyright 2026 Marimo. All rights reserved.
"""Tests for cache invalidation when function body changes."""

from __future__ import annotations

import textwrap

from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


class TestCacheInvalidation:
    async def test_numeric_return_invalidation(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        """@mo.cache with numeric return types must invalidate on body change."""
        # First run: return 11 + 19 = 30
        await k.run(
            [
                exec_req.get_with_id(
                    cell_id="0",
                    code=textwrap.dedent("""
                    import marimo as mo

                    @mo.cache
                    def query():
                        return 11 + 19

                    result = query()
                """),
                ),
            ]
        )

        assert k.globals["result"] == 30
        first_hash = k.globals["query"]._last_hash

        # Second run: return 5 + 3 = 8 (same cell, different code)
        await k.run(
            [
                exec_req.get_with_id(
                    cell_id="0",
                    code=textwrap.dedent("""
                    import marimo as mo

                    @mo.cache
                    def query():
                        return 5 + 3

                    result = query()
                """),
                ),
            ]
        )

        second_hash = k.globals["query"]._last_hash

        # Hashes should be different
        assert first_hash != second_hash, (
            "Hash should change when function body changes"
        )
        # Should get 8, not stale 30
        assert k.globals["result"] == 8, (
            f"Expected 8, got {k.globals['result']} (stale cache)"
        )

    async def test_string_return_invalidation(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        """@mo.cache with string return types must invalidate on body change."""
        # First run
        await k.run(
            [
                exec_req.get_with_id(
                    cell_id="0",
                    code=textwrap.dedent("""
                    import marimo as mo

                    @mo.cache
                    def query():
                        return "hello"

                    result = query()
                """),
                ),
            ]
        )

        assert k.globals["result"] == "hello"
        first_hash = k.globals["query"]._last_hash

        # Second run: different function body
        await k.run(
            [
                exec_req.get_with_id(
                    cell_id="0",
                    code=textwrap.dedent("""
                    import marimo as mo

                    @mo.cache
                    def query():
                        return "world"

                    result = query()
                """),
                ),
            ]
        )

        second_hash = k.globals["query"]._last_hash

        # Hashes should be different
        assert first_hash != second_hash, (
            "Hash should change when function body changes"
        )
        assert k.globals["result"] == "world", (
            f"Expected 'world', got {k.globals['result']} (stale cache)"
        )

    async def test_float_return_invalidation(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        """@mo.cache with float return types must invalidate on body change."""
        # First run: return 1.5 + 2.5 = 4.0
        await k.run(
            [
                exec_req.get_with_id(
                    cell_id="0",
                    code=textwrap.dedent("""
                    import marimo as mo

                    @mo.cache
                    def query():
                        return 1.5 + 2.5

                    result = query()
                """),
                ),
            ]
        )

        assert k.globals["result"] == 4.0

        # Second run: return 0.1 + 0.2 ≈ 0.3
        await k.run(
            [
                exec_req.get_with_id(
                    cell_id="0",
                    code=textwrap.dedent("""
                    import marimo as mo

                    @mo.cache
                    def query():
                        return 0.1 + 0.2

                    result = query()
                """),
                ),
            ]
        )

        # Should get approximately 0.3, not stale 4.0
        assert abs(k.globals["result"] - 0.3) < 0.0001, (
            f"Expected ~0.3, got {k.globals['result']} (stale cache)"
        )
