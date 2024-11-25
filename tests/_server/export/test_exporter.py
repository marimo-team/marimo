from __future__ import annotations

from marimo._ast.app import App, InternalApp
from marimo._server.export.exporter import Exporter
from marimo._server.file_manager import AppFileManager
from tests.mocks import snapshotter

snapshot = snapshotter(__file__)


def test_export_ipynb_empty():
    app = App()
    file_manager = AppFileManager.from_app(InternalApp(app))
    exporter = Exporter()

    content, filename = exporter.export_as_ipynb(
        file_manager, sort_mode="top-down"
    )
    assert filename == "notebook.ipynb"
    snapshot("empty_notebook.ipynb.txt", content)


def test_export_ipynb_with_cells():
    app = App()

    @app.cell()
    def cell_1():
        print("hello")

    file_manager = AppFileManager.from_app(InternalApp(app))
    exporter = Exporter()

    content, filename = exporter.export_as_ipynb(
        file_manager, sort_mode="top-down"
    )
    assert filename == "notebook.ipynb"
    snapshot("notebook_with_cells.ipynb.txt", content)


def test_export_ipynb_sort_modes():
    app = App()

    @app.cell()
    def result(x, y):
        z = x + y
        return (z,)

    @app.cell()
    def __():
        x = 1
        return (x,)

    @app.cell()
    def __():
        y = 1
        return (y,)

    file_manager = AppFileManager.from_app(InternalApp(app))
    exporter = Exporter()

    # Test top-down mode preserves document order
    content, _ = exporter.export_as_ipynb(file_manager, sort_mode="top-down")
    snapshot("notebook_top_down.ipynb.txt", content)

    # Test topological mode respects dependencies
    content, _ = exporter.export_as_ipynb(
        file_manager, sort_mode="topological"
    )
    snapshot("notebook_topological.ipynb.txt", content)
