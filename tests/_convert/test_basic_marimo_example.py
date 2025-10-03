# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from textwrap import dedent

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
