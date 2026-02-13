# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from textwrap import dedent

from marimo._ast.cell_id import CellIdGenerator
from marimo._ast.names import SETUP_CELL_NAME
from marimo._convert.converters import MarimoConvert


def _kernel_cell_ids(source: str) -> list[str]:
    """Simulate the cell IDs the kernel would generate for a notebook."""
    from marimo._ast.parse import parse_notebook
    from marimo._schemas.serialization import SetupCell

    ir = parse_notebook(source)
    assert ir is not None
    gen = CellIdGenerator()
    ids = []
    for i, cell_def in enumerate(ir.cells):
        if isinstance(cell_def, SetupCell) or (
            i == 0 and cell_def.name == SETUP_CELL_NAME
        ):
            ids.append(SETUP_CELL_NAME)
        else:
            ids.append(gen.create_cell_id())
    return ids


def test_snapshot_ids_match_kernel_ids():
    source = dedent('''
        import marimo

        __generated_with = "0.1.0"
        app = marimo.App()

        @app.cell
        def hello():
            x = 1
            return (x,)

        @app.cell
        def world(x):
            y = x + 1
            return (y,)

        if __name__ == "__main__":
            app.run()
    ''').strip()

    notebook = MarimoConvert.from_py(source).to_notebook_v1()
    snapshot_ids = [c["id"] for c in notebook["cells"]]
    kernel_ids = _kernel_cell_ids(source)

    assert snapshot_ids == kernel_ids
    assert all(id is not None for id in snapshot_ids)


def test_snapshot_ids_match_kernel_ids_with_setup_cell():
    source = dedent('''
        import marimo

        __generated_with = "0.1.0"
        app = marimo.App()

        with app.setup:
            import numpy as np

        @app.cell
        def hello():
            x = 1
            return (x,)

        @app.cell
        def world(x):
            y = x + 1
            return (y,)

        if __name__ == "__main__":
            app.run()
    ''').strip()

    notebook = MarimoConvert.from_py(source).to_notebook_v1()
    snapshot_ids = [c["id"] for c in notebook["cells"]]
    kernel_ids = _kernel_cell_ids(source)

    assert snapshot_ids == kernel_ids
    assert snapshot_ids[0] == SETUP_CELL_NAME


def test_snapshot_ids_are_deterministic():
    source = dedent('''
        import marimo

        __generated_with = "0.1.0"
        app = marimo.App()

        @app.cell
        def _():
            x = 1
            return (x,)

        @app.cell
        def _():
            y = 2
            return (y,)

        @app.cell
        def _():
            z = 3
            return (z,)

        if __name__ == "__main__":
            app.run()
    ''').strip()

    ids_1 = [
        c["id"] for c in MarimoConvert.from_py(source).to_notebook_v1()["cells"]
    ]
    ids_2 = [
        c["id"] for c in MarimoConvert.from_py(source).to_notebook_v1()["cells"]
    ]

    assert ids_1 == ids_2
    assert len(set(ids_1)) == 3  # all unique
