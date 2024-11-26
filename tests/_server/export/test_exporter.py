from __future__ import annotations

import asyncio

import pytest

from marimo._ast.app import App, InternalApp
from marimo._dependencies.dependencies import DependencyManager
from marimo._server.export import run_app_until_completion
from marimo._server.export.exporter import Exporter
from marimo._server.file_manager import AppFileManager
from tests.mocks import snapshotter

snapshot = snapshotter(__file__)

HAS_NBFORMAT = DependencyManager.nbformat.has()


@pytest.mark.skipif(not HAS_NBFORMAT, reason="nbformat is not installed")
def test_export_ipynb_empty():
    app = App()
    file_manager = AppFileManager.from_app(InternalApp(app))
    exporter = Exporter()

    content, filename = exporter.export_as_ipynb(
        file_manager, sort_mode="top-down"
    )
    assert filename == "notebook.ipynb"
    snapshot("empty_notebook.ipynb.txt", content)


@pytest.mark.skipif(not HAS_NBFORMAT, reason="nbformat is not installed")
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


@pytest.mark.skipif(not HAS_NBFORMAT, reason="nbformat is not installed")
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


@pytest.mark.skipif(not HAS_NBFORMAT, reason="nbformat is not installed")
def test_export_ipynb_with_outputs():
    app = App()

    @app.cell()
    def cell_1():
        print("hello")
        return ()

    @app.cell()
    def cell_2():
        import sys

        sys.stdout.write("world\n")
        return ()

    # This includes the filepath in the error message, which is not
    # good for snapshots
    # @app.cell()
    # def cell_3():
    #     raise Exception("error")
    #     return ()

    @app.cell()
    def cell_4():
        x = 10
        return (x,)

    @app.cell()
    def cell_5(x):
        y = x + 1
        y * 2
        return (y,)

    @app.cell()
    def cell_6():
        import marimo as mo

        return (mo,)

    @app.cell()
    def cell_7(mo):
        mo.md("hello")
        return ()

    @app.cell()
    def cell_8(mo, x):
        mo.md(f"hello {x}")
        return ()

    file_manager = AppFileManager.from_app(InternalApp(app))
    exporter = Exporter()

    content, filename = exporter.export_as_ipynb(
        file_manager, sort_mode="top-down", session_view=None
    )
    assert filename == "notebook.ipynb"

    # Create a session view with outputs
    session_view = asyncio.run(
        run_app_until_completion(file_manager, cli_args={})
    )
    content, filename = exporter.export_as_ipynb(
        file_manager, sort_mode="top-down", session_view=session_view
    )
    assert filename == "notebook.ipynb"
    snapshot("notebook_with_outputs.ipynb.txt", content)
