# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import sys
import logging
from collections.abc import Awaitable

import pytest

from marimo import _loggers
from marimo._ast.app import App
from marimo._ast.cell import CellConfig


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
        assert not cell._is_coroutine
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
        assert cell._is_coroutine

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

        assert g._is_coroutine
        # h is a coroutine because it depends on the execution of an async
        # function
        assert h._is_coroutine

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

        assert f._is_coroutine
        assert g._is_coroutine
        assert h._is_coroutine

    @staticmethod
    def test_empty_cell() -> None:
        app = App()

        @app.cell
        def f() -> None:
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

    @staticmethod
    def test_unhashable_import() -> None:
        from cell_data.named_cells import (
            unhashable_defined,
            unhashable_override_required,
        )

        assert unhashable_defined.name == "unhashable_defined"
        assert (
            unhashable_override_required.name == "unhashable_override_required"
        )

        assert unhashable_override_required.run(unhashable={0, 1}) == (
            {0, 1},
            {},
        )
        assert unhashable_defined.run() == (
            {0, 1, 2},
            {"unhashable": {0, 1, 2}},
        )

    @staticmethod
    def test_direct_call() -> None:
        from cell_data.named_cells import h, multiple, unhashable_defined

        assert h(1) == 2
        assert multiple() == (0, 1)
        assert unhashable_defined() == {0, 1, 2}

    @staticmethod
    def test_direct_call_with_global() -> None:
        old = os.environ.pop("PYTEST_CURRENT_TEST")
        old_version = os.environ.pop("PYTEST_VERSION")
        try:
            if "cell_data.named_cells" in sys.modules:
                del sys.modules["cell_data.named_cells"]
            from cell_data.named_cells import called_with_global

            # NB. depends on a variable `a` defined on module level.
            assert called_with_global(1) == 2
            assert called_with_global(x=1) == 2

            # Raise errors
            with pytest.raises(TypeError) as e:
                called_with_global(1, 1)

            with pytest.raises(TypeError) as e:
                called_with_global(x=1, a=1)
            assert "unexpected argument" in str(e.value)

            with pytest.raises(TypeError) as e:
                called_with_global(a=1)
            assert "unexpected argument" in str(e.value)

        finally:
            os.environ["PYTEST_CURRENT_TEST"] = old
            os.environ["PYTEST_VERSION"] = old_version

    @staticmethod
    def test_mismatch_args(app, caplog) -> none:
        # poor practice, but possible cell.
        @app.cell
        def basic(lots, of_, incorrect, args):
            1
            return

        assert basic.run() == (1, {})
        assert len(caplog.records) == 0
        with caplog.at_level(logging.WARNING):
            _loggers.marimo_logger().propagate = True
            assert basic() == 1
        assert len(caplog.records) == 1
        assert "signature" in caplog.text

    @staticmethod
    def test_direct_cyclic_call(app) -> none:
        # poor practice, but possible cell.
        @app.cell
        def cyclic():
            a = 1
            if False:
                a = b  # noqa: f821
            else:
                b = a
            b  # noqa: b018
            return

        assert cyclic.run() == (1, {"a": 1, "b": 1})
        assert cyclic() == 1


def help_smoke() -> None:
    app = App()

    @app.cell
    async def f(x) -> None:
        await x
        return

    @app.cell
    def g() -> None:
        return

    assert "Async" in f._help().text
    assert "Async" not in g._help().text


def test_cell_config_asdict_without_defaults():
    config = CellConfig()
    assert config.asdict_without_defaults() == {}

    config = CellConfig(hide_code=True)
    assert config.asdict_without_defaults() == {"hide_code": True}

    config = CellConfig(hide_code=False)
    assert config.asdict_without_defaults() == {}


def test_is_different_from_default():
    config = CellConfig(hide_code=True)
    assert config.is_different_from_default()

    config = CellConfig(hide_code=False)
    assert not config.is_different_from_default()
