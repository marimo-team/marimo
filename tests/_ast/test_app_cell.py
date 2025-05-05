# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import textwrap
import types
from collections.abc import Awaitable

from marimo._ast.app import App
from marimo._ast.cell import Cell


def test_decorator_called() -> None:
    def mock_func1() -> tuple[int]:
        x = 2 + 2
        return (x,)

    app = App()
    cell = app.cell()(mock_func1)
    assert cell is not None
    assert cell._cell.code == "x = 2 + 2"
    assert cell._cell.config.disabled is False
    assert cell.name == "mock_func1"
    assert cell.run() == (None, {"x": 4})


def test_decorator_uncalled() -> None:
    def __() -> tuple[int]:
        z = 3 + 3
        return (z,)

    app = App()
    cell = app.cell(__)
    assert cell is not None
    assert cell._cell.code == "z = 3 + 3"
    assert cell._cell.config.disabled is False
    assert cell.name == "__"
    assert cell.run() == (None, {"z": 6})


def test_decorator_with_args() -> None:
    def mock_func3(x: int) -> tuple[int]:
        y = x + 2
        return (y,)

    app = App()
    cell = app.cell(disabled=True)(mock_func3)
    assert cell is not None

    assert cell._cell.code == "y = x + 2"
    assert cell._cell.config.disabled is True
    assert cell.name == "mock_func3"
    assert cell.run(x=1) == (None, {"y": 3})


def test_decorator_with_unknown_args() -> None:
    # Decorator with unknown args
    def __() -> tuple[int]:
        x = 2 + 2
        return (x,)

    app = App()
    cell = app.cell(foo=True)(__)
    assert cell is not None

    assert cell._cell.code == "x = 2 + 2"
    assert cell._cell.config.disabled is False
    assert cell.name == "__"
    assert cell.run() == (None, {"x": 4})


async def test_decorator_async() -> None:
    # Decorator uncalled
    async def __(asyncio) -> tuple[int]:
        await asyncio.sleep(0.1)
        z = 3 + 3
        return (z,)

    app = App()
    cell = app.cell(__)
    assert cell is not None

    assert cell._cell.is_coroutine()
    assert cell._cell.config.disabled is False
    assert cell.name == "__"

    import asyncio

    result = cell.run(asyncio=asyncio)
    assert isinstance(result, Awaitable)
    assert await result == (None, {"z": 6})


def test_function_decorator_called() -> None:
    app = App()

    @app.function()
    def mock_func(x) -> tuple[int]:
        return x + x

    assert isinstance(mock_func, types.FunctionType)

    (cell,) = app._cell_manager.cells()
    assert not isinstance(cell, types.FunctionType)
    assert isinstance(cell, Cell)

    assert cell.name == "*mock_func"
    assert (
        cell.run()[1]["mock_func"].__code__.co_code
        == mock_func.__code__.co_code
    )


def test_function_decorator_uncalled() -> None:
    app = App()

    @app.function
    def mock_func(x) -> tuple[int]:
        return x + x

    assert isinstance(mock_func, types.FunctionType)

    (cell,) = app._cell_manager.cells()
    assert not isinstance(cell, types.FunctionType)
    assert isinstance(cell, Cell)

    assert cell.name == "*mock_func"
    assert (
        cell.run()[1]["mock_func"].__code__.co_code
        == mock_func.__code__.co_code
    )


def test_function_decorator_with_args() -> None:
    app = App()

    @app.function(disabled=True)
    def mock_func(x: int) -> int:
        y = x + 2
        return y

    assert isinstance(mock_func, types.FunctionType)

    (cell,) = app._cell_manager.cells()
    assert cell is not None
    assert isinstance(cell, Cell)

    assert (
        cell._cell.code
        == textwrap.dedent("""
    def mock_func(x: int) -> int:
        y = x + 2
        return y
    """).strip()
    )
    assert cell._cell.config.disabled is True
    assert cell.name == "*mock_func"
    assert (
        cell.run()[1]["mock_func"].__code__.co_code
        == mock_func.__code__.co_code
    )


# TODO(akshayka): test cell.run() with multiple cells in graph, outputs, ...
