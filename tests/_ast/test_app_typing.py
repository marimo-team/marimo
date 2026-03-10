# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("basedpyright") is None,
    reason="basedpyright not installed",
)


def _check_pyright(code: str) -> None:
    """Run basedpyright on *code* and assert zero errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "check.py"
        p.write_text(textwrap.dedent(code))
        result = subprocess.run(
            [
                "basedpyright",
                "--pythonpath",
                sys.executable,
                "--level",
                "error",
                str(p),
            ],
            capture_output=True,
            text=True,
        )
    assert result.returncode == 0, (
        f"basedpyright exited with code {result.returncode}\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )


_PREAMBLE = """
    from typing_extensions import TypeGuard, TypeIs, assert_type
    import marimo as mo

    def _int_or_str() -> int | str:
        return 0
"""


class TestAppFunctionTyping:
    def test_typeis_narrowing(self) -> None:
        _check_pyright("""
            from typing_extensions import TypeIs, assert_type
            import marimo

            app = marimo.App()

            @app.function
            def is_int(x: object) -> TypeIs[int]:
                return isinstance(x, int)

            def _int_or_str() -> int | str:
                return 0

            val = _int_or_str()
            if is_int(val):
                assert_type(val, int)
        """)

    def test_typeguard_narrowing(self) -> None:
        _check_pyright("""
            from typing_extensions import TypeGuard, assert_type
            import marimo

            app = marimo.App()

            @app.function
            def guard_int(x: object) -> TypeGuard[int]:
                return isinstance(x, int)

            def _int_or_str() -> int | str:
                return 0

            val = _int_or_str()
            if guard_int(val):
                assert_type(val, int)
        """)

    def test_regular_function_signature(self) -> None:
        _check_pyright("""
            from typing_extensions import assert_type
            import marimo

            app = marimo.App()

            @app.function
            def add(a: int, b: int) -> int:
                return a + b

            assert_type(add(1, 2), int)
        """)


@pytest.fixture(params=["cache", "lru_cache", "persistent_cache"])
def cache_func(request: pytest.FixtureRequest) -> str:
    return request.param


class TestCacheTyping:
    def test_cache_preserves_return_type(self, cache_func: str) -> None:
        _check_pyright(
            _PREAMBLE
            + f"""
    @mo.{cache_func}
    def compute(x: int) -> int:
        return x * 2

    assert_type(compute(1), int)
"""
        )

    def test_cache_async_preserves_return_type(self, cache_func: str) -> None:
        _check_pyright(
            _PREAMBLE
            + f"""
    @mo.{cache_func}
    async def compute(x: int) -> int:
        return x * 2

    async def main():
        val = await compute(1)
        assert_type(val, int)
"""
        )

    def test_cache_method_preserves_return_type(self, cache_func: str) -> None:
        _check_pyright(
            _PREAMBLE
            + f"""
    class A:
        @mo.{cache_func}
        def method(self, x: int) -> int:
            return x

    assert_type(A().method(1), int)
"""
        )

    def test_cache_async_method_preserves_return_type(
        self, cache_func: str
    ) -> None:
        _check_pyright(
            _PREAMBLE
            + f"""
    class A:
        @mo.{cache_func}
        async def method(self, x: int) -> int:
            return x

    async def main():
        val = await A().method(1)
        assert_type(val, int)
"""
        )

    def test_cache_exposes_cache_info(self) -> None:
        _check_pyright(
            _PREAMBLE
            + """
    @mo.cache
    def compute(x: int) -> int:
        return x * 2

    info = compute.cache_info()
    compute.cache_clear()
"""
        )


class TestLruCacheTyping:
    def test_lru_cache_parameterized_preserves_return_type(self) -> None:
        _check_pyright(
            _PREAMBLE
            + """
    @mo.lru_cache(maxsize=128)
    def compute(x: int) -> int:
        return x * 2

    assert_type(compute(1), int)
"""
        )

    def test_lru_cache_exposes_cache_info(self) -> None:
        _check_pyright(
            _PREAMBLE
            + """
    @mo.lru_cache
    def compute(x: int) -> int:
        return x * 2

    info = compute.cache_info()
    compute.cache_clear()
"""
        )


class TestPersistentCacheTyping:
    def test_persistent_cache_parameterized_preserves_return_type(
        self,
    ) -> None:
        _check_pyright(
            _PREAMBLE
            + """
    @mo.persistent_cache(save_path="cache")
    def compute(x: int) -> int:
        return x * 2

    assert_type(compute(1), int)
"""
        )


class TestCacheContext:
    def test_cache_context_return_type(self, cache_func: str) -> None:
        _check_pyright(
            _PREAMBLE
            + f"""
    from marimo._save.save import _cache_context
    assert_type(mo.{cache_func}("cache"), _cache_context)
"""
        )
