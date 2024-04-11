# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from collections.abc import Awaitable

import pytest

from marimo._ast.app import App


class TestCellRun:
    @staticmethod
    def test_cell_basic() -> None:
        def f() -> tuple[int]:
            x = 2 + 2
            "output"
            return (x,)

        app = App()
        cell = app.cell(f)
        assert cell.name == "f"
        assert not cell.refs
        assert cell.defs == set(["x"])
        assert not cell._is_coroutine()
        assert cell.run() == ("output", {"x": 4})

    @staticmethod
    async def test_async_cell_basic() -> None:
        async def f(asyncio) -> tuple[int]:
            await asyncio.sleep(0)

            x = 2 + 2
            "output"
            return (x,)

        app = App()
        cell = app.cell(f)
        assert cell.name == "f"
        assert cell.refs == {"asyncio"}
        assert cell.defs == {"x"}
        assert cell._is_coroutine()

        import asyncio

        ret = cell.run(asyncio=asyncio)
        assert isinstance(ret, Awaitable)
        assert await ret == ("output", {"x": 4})

    @staticmethod
    def test_unknown_ref_raises() -> None:
        def f() -> None: ...

        app = App()
        cell = app.cell(f)
        with pytest.raises(ValueError) as einfo:
            cell.run(foo=1)
        assert "unexpected argument" in str(einfo.value)

    @staticmethod
    def test_substituted_ref_basic() -> None:
        app = App()

        @app.cell
        def g():
            x = 0
            y = 1
            return (x, y)

        @app.cell
        def h(x, y):
            z = x + y
            return (z,)

        assert h.run() == (None, {"z": 1})
        assert h.run(x=1) == (None, {"z": 2})
        assert h.run(y=0) == (None, {"z": 0})
        assert h.run(x=1, y=2) == (None, {"z": 3})

    @staticmethod
    def test_substituted_ref_chain() -> None:
        app = App()

        @app.cell
        def f():
            x = 0
            return (x,)

        @app.cell
        def g(x):
            y = x + 1
            return (y,)

        @app.cell
        def h(y):
            z = 2 * y
            return (z,)

        assert h.run() == (None, {"z": 2})
        assert h.run(y=0) == (None, {"z": 0})

        with pytest.raises(ValueError) as e:
            h.run(x=1)
        assert "unexpected argument" in str(e.value)

    @staticmethod
    def test_async_parent() -> None:
        app = App()

        @app.cell
        async def g(arg):
            await arg
            x = 0
            return (x,)

        @app.cell
        def h(x):
            y = x
            return (y,)

        assert g._is_coroutine()
        # h is a coroutine because it depends on the execution of an async
        # function
        assert h._is_coroutine()

    @staticmethod
    def test_async_chain() -> None:
        app = App()

        @app.cell
        async def f(arg):
            await arg
            x = 0
            return (x,)

        @app.cell
        def g(x):
            y = x
            return (y,)

        @app.cell
        def h(y):
            z = y
            return (z,)

        assert f._is_coroutine()
        assert g._is_coroutine()
        assert h._is_coroutine()

    @staticmethod
    def test_empty_cell() -> None:
        app = App()

        @app.cell
        def f():
            return

        assert f.run() == (None, {})

    @staticmethod
    def test_conditional_def() -> None:
        app = App()

        @app.cell
        def f():
            if False:
                x = 0
            return (x,)

        # "x" was statically declared
        assert f.defs == {"x"}
        # "x" should not be in returns because it wasn't defined at runtime
        assert f.run() == (None, {})

    @staticmethod
    def test_import() -> None:
        from cell_data.named_cells import f, g, h

        assert f.name == "f"
        assert g.name == "g"
        assert h.name == "h"

        assert f.run() == (None, {"x": 0})
        assert g.run() == (None, {"y": 1})
        assert h.run() == (2, {"z": 2})

        assert g.run(x=1) == (None, {"y": 2})
        assert h.run(y=2) == (3, {"z": 3})


def help_smoke() -> None:
    app = App()

    @app.cell
    async def f(x):
        await x
        return

    @app.cell
    def g():
        return

    assert "Async" in f._help().text
    assert "Async" not in g._help().text
