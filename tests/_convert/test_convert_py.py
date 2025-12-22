# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from textwrap import dedent

from marimo import __version__
from marimo._convert.converters import MarimoConvert
from tests.mocks import snapshotter

snapshot = snapshotter(__file__)


def test_basic_marimo_example_jupytext_compatibility():
    """Test a basic marimo example that matches what jupytext would generate."""
    # This is the exact content from the jupytext PR test file
    marimo_script = dedent('''
        import marimo

        __generated_with = "0.15.2"
        app = marimo.App(width="medium")


        @app.cell(hide_code=True)
        def _(mo):
            mo.md(r"""This is a simple marimo notebook""")
            return


        @app.cell
        def _():
            x = 1
            return (x,)


        @app.cell
        def _(x):
            y = x+1
            y
            return


        @app.cell
        def _():
            import marimo as mo
            return (mo,)


        if __name__ == "__main__":
            app.run()
    ''').strip()

    # Snapshot the original marimo script
    snapshot("basic_marimo_example.py.txt", marimo_script)

    # Test conversion to markdown (now works without file existing)
    converted_to_md = MarimoConvert.from_py(marimo_script).to_markdown(
        "Test Notebook.py"
    )
    snapshot("basic_marimo_example_to_md.txt", converted_to_md)

    # Test conversion back from markdown to marimo
    converted_back = MarimoConvert.from_md(converted_to_md).to_py()
    snapshot("basic_marimo_example_roundtrip.py.txt", converted_back)


def test_unparsable_cell_with_escaped_quotes():
    """Test an unparsable cell with escaped quotes."""
    marimo_script = dedent(f'''
        import marimo

        __generated_with = "{__version__}"
        app = marimo.App()

        app._unparsable_cell(
            r"""
            return
            """,
            name="_"
        )

        app._unparsable_cell(
            r"""
            x = "hello \\"world\\""
            x.
            """,
            name="_"
        )

        if __name__ == "__main__":
            app.run()
    ''').strip()

    def identity(x: str) -> str:
        return MarimoConvert.from_py(x).to_py()

    # This is not equal since `_unparsable_cell` got written in a different way than our codegen
    assert identity(marimo_script) != marimo_script
    # But after being written once, it's idempotent
    assert identity(identity(marimo_script)) == identity(marimo_script)
    snapshot(
        "unparsable_cell_with_escaped_quotes.py.txt", identity(marimo_script)
    )
