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
    from typing_extensions import assert_type
    import marimo as mo
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

    async def _main():  # pyright: ignore[reportUnusedFunction]
        assert_type(await compute(1), int)
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

    async def _main():  # pyright: ignore[reportUnusedFunction]
        assert_type(await A().method(1), int)
"""
        )

    def test_cache_exposes_cache_info(self) -> None:
        _check_pyright("""
            import marimo as mo

            @mo.cache
            def compute(x: int) -> int:
                return x * 2

            _info = compute.cache_info()
            compute.cache_clear()
        """)


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
        _check_pyright("""
            import marimo as mo

            @mo.lru_cache
            def compute(x: int) -> int:
                return x * 2

            _info = compute.cache_info()
            compute.cache_clear()
        """)


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
    from marimo._save.save import (
        _cache_context,  # pyright: ignore[reportPrivateUsage]
    )
    assert_type(mo.{cache_func}("cache"), _cache_context)
"""
        )


class TestBatchTyping:
    def test_batch_accepts_slider_and_number(self) -> None:
        _check_pyright(
            _PREAMBLE
            + """
    parameters = mo.md(
        "slider: {a} number: {b}"
    ).batch(
        a=mo.ui.slider(start=1, stop=50, step=1, value=10),
        b=mo.ui.number(value=0.2),
    )
    assert_type(parameters.value, dict[str, object])
"""
        )


class TestDictionaryTyping:
    def test_dictionary_accepts_covariant_dict(self) -> None:
        # dict is invariant, so a dict[str, checkbox] was rejected for the old
        # dict[str, UIElement] param; widening it to a covariant Mapping accepts
        # a dict of UIElement subclasses. Regression guard for #10653.
        _check_pyright(
            _PREAMBLE
            + """
    checks: dict[str, mo.ui.checkbox] = {"a": mo.ui.checkbox()}
    d = mo.ui.dictionary(checks)
    assert_type(d.value, dict[str, object])
"""
        )

    def test_validate_and_clone_accepts_covariant_dict(self) -> None:
        _check_pyright(
            """
            import marimo as mo
            from marimo._plugins.ui._impl.batch import validate_and_clone

            checks: dict[str, mo.ui.checkbox] = {"a": mo.ui.checkbox()}
            _cloned = validate_and_clone(checks)
            """
        )


class TestContainerTyping:
    # dict is invariant, so a dict[str, Html] was rejected for the old
    # dict[str, object] params; widening them to a covariant Mapping accepts
    # a dict of any value type. Regression guard for #10631.
    def test_tabs_accepts_covariant_dict(self) -> None:
        _check_pyright(
            _PREAMBLE
            + """
    panes: dict[str, mo.Html] = {"a": mo.md("x")}
    t = mo.ui.tabs(panes)
    assert_type(t.value, str)
"""
        )

    def test_accordion_accepts_covariant_dict(self) -> None:
        _check_pyright(
            _PREAMBLE
            + """
    panes: dict[str, mo.Html] = {"a": mo.md("x")}
    _acc = mo.accordion(panes)
"""
        )

    def test_deprecated_tabs_accepts_covariant_dict(self) -> None:
        _check_pyright(
            _PREAMBLE
            + """
    panes: dict[str, mo.Html] = {"a": mo.md("x")}
    _t = mo.tabs(panes)
"""
        )

    def test_routes_accepts_covariant_dict(self) -> None:
        _check_pyright(
            _PREAMBLE
            + """
    from collections.abc import Callable

    pages: dict[str, Callable[[], mo.Html]] = {"#/": lambda: mo.md("x")}
    _r = mo.routes(pages)
"""
        )
