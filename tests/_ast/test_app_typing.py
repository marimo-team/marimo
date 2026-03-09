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
            ["basedpyright", "--pythonpath", sys.executable, str(p)],
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


class TestCacheTyping:
    def test_cache_preserves_return_type(self) -> None:
        _check_pyright(
            _PREAMBLE
            + """
    @mo.cache
    def compute(x: int) -> int:
        return x * 2

    assert_type(compute(1), int)
"""
        )

    def test_cache_typeis_narrowing(self) -> None:
        _check_pyright(
            _PREAMBLE
            + """
    @mo.cache
    def is_int(x: object) -> TypeIs[int]:
        return isinstance(x, int)

    val = _int_or_str()
    if is_int(val):
        assert_type(val, int)
"""
        )

    def test_cache_typeguard_narrowing(self) -> None:
        _check_pyright(
            _PREAMBLE
            + """
    @mo.cache
    def guard_int(x: object) -> TypeGuard[int]:
        return isinstance(x, int)

    val = _int_or_str()
    if guard_int(val):
        assert_type(val, int)
"""
        )


class TestLruCacheTyping:
    def test_lru_cache_preserves_return_type(self) -> None:
        _check_pyright(
            _PREAMBLE
            + """
    @mo.lru_cache
    def compute(x: int) -> int:
        return x * 2

    assert_type(compute(1), int)
"""
        )

    def test_lru_cache_typeis_narrowing(self) -> None:
        _check_pyright(
            _PREAMBLE
            + """
    @mo.lru_cache
    def is_int(x: object) -> TypeIs[int]:
        return isinstance(x, int)

    val = _int_or_str()
    if is_int(val):
        assert_type(val, int)
"""
        )

    def test_lru_cache_typeguard_narrowing(self) -> None:
        _check_pyright(
            _PREAMBLE
            + """
    @mo.lru_cache
    def guard_int(x: object) -> TypeGuard[int]:
        return isinstance(x, int)

    val = _int_or_str()
    if guard_int(val):
        assert_type(val, int)
"""
        )
