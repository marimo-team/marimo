# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import inspect

from marimo._ast.app import App
from marimo._ast.cell import CellFunction, CellFuncType

# Arg capture
cell_function: CellFunction[CellFuncType] = None  # type: ignore[assignment]


def mock_register_cell(cf: CellFunction[CellFuncType]) -> None:
    global cell_function
    cell_function = cf


app = App()
app._cell_manager._register_cell_function = mock_register_cell  # type: ignore[method-assign, assignment] # noqa: E501


def test_decorator_called() -> None:
    # Decorator called
    @app.cell()
    def mock_func1() -> tuple[int]:
        x = 2 + 2
        return (x,)

    assert cell_function.cell.code == "x = 2 + 2"
    assert cell_function.cell.config.disabled is False
    assert len(cell_function.args) == 0
    assert cell_function.__name__ == "mock_func1"
    assert cell_function.__call__ is not None
    assert cell_function.__call__() == (4,)


def test_decorator_uncalled() -> None:
    # Decorator uncalled
    @app.cell
    def __() -> tuple[int]:
        z = 3 + 3
        return (z,)

    assert cell_function.cell.code == "z = 3 + 3"
    assert cell_function.cell.config.disabled is False
    assert len(cell_function.args) == 0
    assert cell_function.__name__ == "__"
    assert cell_function.__call__ is not None
    assert cell_function.__call__() == (6,)


def test_decorator_with_args() -> None:
    # Decorator with args
    @app.cell(disabled=True)
    def mock_func3(x: int) -> tuple[int]:
        y = x + 2
        return (y,)

    assert cell_function.cell.code == "y = x + 2"
    assert cell_function.cell.config.disabled is True
    assert cell_function.args == {"x"}
    assert cell_function.__name__ == "mock_func3"
    assert cell_function.__call__ is not None
    assert cell_function.__call__(2) == (4,)


def test_decorator_with_unknown_args() -> None:
    # Decorator with unknown args
    @app.cell(foo=True)
    def __() -> tuple[int]:
        x = 2 + 2
        return (x,)

    assert cell_function.cell.code == "x = 2 + 2"
    assert cell_function.cell.config.disabled is False
    assert len(cell_function.args) == 0
    assert cell_function.__name__ == "__"
    assert cell_function.__call__ is not None
    assert cell_function.__call__() == (4,)


async def test_decorator_async() -> None:
    # Decorator uncalled
    @app.cell
    async def __(asyncio) -> tuple[int]:
        await asyncio.sleep(0.1)
        z = 3 + 3
        return (z,)

    assert inspect.iscoroutinefunction(cell_function)
    assert cell_function.cell.config.disabled is False
    assert len(cell_function.args) == 1
    assert cell_function.__name__ == "__"
    assert cell_function.__call__ is not None

    import asyncio

    assert (await cell_function(asyncio)) == (6,)
