# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from textwrap import dedent

from marimo import __version__
from marimo._convert.converters import MarimoConvert
from marimo._convert.script import _header_for_script
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
        filename="Test Notebook.py"
    )
    snapshot("basic_marimo_example_to_md.txt", converted_to_md)

    # Test conversion back from markdown to marimo
    converted_back = MarimoConvert.from_md(converted_to_md).to_py()
    snapshot("basic_marimo_example_roundtrip.py.txt", converted_back)


def test_unparsable_cell_with_escaped_quotes():
    """Test an unparsable cell with escaped quotes."""
    marimo_script = dedent(rf'''
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
            # Single quote string
            x = "hello \"world\"
            x.
            """,
            name="_"
        )


        app._unparsable_cell(
            r"""
            # Triple quote string
            x = "hello \"\"\"world\"\"\""
            x.
            """,
            name="_"
        )


        app._unparsable_cell(
            r"""
            # Triple quote string with other slashes
            x = "hello \"\"\"world\"\"\"
            path = "C:\\Users\\test"
            x.
            """,
            name="_"
        )


        if __name__ == "__main__":
            app.run()
    ''')[1:]

    def identity(x: str) -> str:
        return MarimoConvert.from_py(x).to_py()

    assert identity(marimo_script) == marimo_script
    assert identity(identity(marimo_script)) == marimo_script
    assert identity(identity(identity(marimo_script))) == marimo_script
    snapshot(
        "unparsable_cell_with_escaped_quotes.py.txt", identity(marimo_script)
    )


def test_inline_deps_preserved_in_script_export() -> None:
    """PEP 723 inline deps in Python notebooks are preserved when exporting to script."""
    marimo_py = dedent("""\
        # /// script
        # requires-python = ">=3.11"
        # dependencies = [
        #     "pandas",
        # ]
        # ///

        import marimo

        __generated_with = "0.0.0"
        app = marimo.App()


        @app.cell
        def _():
            import pandas as pd
            return (pd,)


        if __name__ == "__main__":
            app.run()
    """)

    ir = MarimoConvert.from_py(marimo_py).ir
    header = _header_for_script(ir)
    assert "# /// script" in header
    assert "pandas" in header


def test_inline_deps_preserved_via_markdown_roundtrip() -> None:
    """PEP 723 inline deps survive Python → markdown → script conversion."""
    marimo_py = dedent("""\
        # /// script
        # requires-python = ">=3.11"
        # dependencies = [
        #     "pandas",
        # ]
        # ///

        import marimo

        __generated_with = "0.0.0"
        app = marimo.App()


        @app.cell
        def _():
            import pandas as pd
            return (pd,)


        if __name__ == "__main__":
            app.run()
    """)

    # Python → markdown
    md = MarimoConvert.from_py(marimo_py).to_markdown()

    # markdown → script IR
    ir = MarimoConvert.from_md(md).ir
    header = _header_for_script(ir)
    assert "# /// script" in header
    assert "pandas" in header
