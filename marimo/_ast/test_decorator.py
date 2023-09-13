# Copyright 2023 Marimo. All rights reserved.
from marimo._ast.app import App
from marimo._ast.cell import CellFunction

# Arg capture
cell_function: CellFunction = None


def mock_register_cell(cf: CellFunction):
    global cell_function
    cell_function = cf


app = App()
app._register_cell = mock_register_cell


def test_decorator():
    # Decorator called
    @app.cell()
    def mock_func1():
        x = 2 + 2
        return (x,)

    assert cell_function.cell.code == "x = 2 + 2"
    assert cell_function.cell.config.disabled is False
    assert len(cell_function.args) == 0
    assert cell_function.__name__ == "mock_func1"
    assert cell_function.__call__ is not None
    assert cell_function.__call__() == (4,)

    # Decorator uncalled
    @app.cell
    def __():
        z = 3 + 3
        return (z,)

    assert cell_function.cell.code == "z = 3 + 3"
    assert cell_function.cell.config.disabled is False
    assert len(cell_function.args) == 0
    assert cell_function.__name__ == "__"
    assert cell_function.__call__ is not None
    assert cell_function.__call__() == (6,)

    # Decorator with args
    @app.cell(disabled=True)
    def mock_func3(x):
        y = x + 2
        return (y,)

    assert cell_function.cell.code == "y = x + 2"
    assert cell_function.cell.config.disabled is True
    assert cell_function.args == {"x"}
    assert cell_function.__name__ == "mock_func3"
    assert cell_function.__call__ is not None
    assert cell_function.__call__(2) == (4,)

    # Decorator with unknown args
    @app.cell(foo=True)
    def __():
        x = 2 + 2
        return (x,)

    assert cell_function.cell.code == "x = 2 + 2"
    assert cell_function.cell.config.disabled is False
    assert len(cell_function.args) == 0
    assert cell_function.__name__ == "__"
    assert cell_function.__call__ is not None
    assert cell_function.__call__() == (4,)
