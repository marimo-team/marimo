# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._ast.parse import parse_notebook
from tests._lint.utils import lint_notebook


def _mr004_diagnostics(code: str):
    notebook = parse_notebook(code, filepath="test.py")
    return [d for d in lint_notebook(notebook) if d.code == "MR004"]


def test_flags_import_repeated_across_cells():
    code = """import marimo

__generated_with = "0.18.0"
app = marimo.App()


@app.cell
def _():
    import os as _os
    return


@app.cell
def _():
    import os as _os
    return


if __name__ == "__main__":
    app.run()
"""
    diagnostics = _mr004_diagnostics(code)
    assert len(diagnostics) == 1
    assert "_os" in diagnostics[0].message
    # Points to both occurrences, like MultipleDefinitionsRule.
    assert len(diagnostics[0].line) == 2


def test_flags_import_from_repeated_across_cells():
    code = """import marimo

__generated_with = "0.18.0"
app = marimo.App()


@app.cell
def _():
    from collections import OrderedDict as _OrderedDict
    return


@app.cell
def _():
    from collections import OrderedDict as _OrderedDict
    return


if __name__ == "__main__":
    app.run()
"""
    diagnostics = _mr004_diagnostics(code)
    assert len(diagnostics) == 1
    assert "_OrderedDict" in diagnostics[0].message
    assert len(diagnostics[0].line) == 2


def test_no_false_positive_for_single_occurrence():
    code = """import marimo

__generated_with = "0.18.0"
app = marimo.App()


@app.cell
def _():
    import os as _os
    return


if __name__ == "__main__":
    app.run()
"""
    assert _mr004_diagnostics(code) == []


def test_no_false_positive_for_plain_import():
    code = """import marimo

__generated_with = "0.18.0"
app = marimo.App()


@app.cell
def _():
    import os
    return


@app.cell
def _():
    import os
    return


if __name__ == "__main__":
    app.run()
"""
    assert _mr004_diagnostics(code) == []


def test_no_false_positive_for_module_named_with_underscore():
    code = """import marimo

__generated_with = "0.18.0"
app = marimo.App()


@app.cell
def _():
    import _thread
    return


@app.cell
def _():
    import _thread
    return


if __name__ == "__main__":
    app.run()
"""
    assert _mr004_diagnostics(code) == []


def test_no_false_positive_for_public_alias():
    code = """import marimo

__generated_with = "0.18.0"
app = marimo.App()


@app.cell
def _():
    import numpy as np
    return


@app.cell
def _():
    import numpy as np
    return


if __name__ == "__main__":
    app.run()
"""
    assert _mr004_diagnostics(code) == []


def test_flags_repeat_across_setup_and_regular_cell():
    """The setup cell isn't special-cased; a repeat there still counts."""
    code = """import marimo

__generated_with = "0.18.0"
app = marimo.App()

with app.setup:
    import os as _os


@app.cell
def _():
    import os as _os
    return


if __name__ == "__main__":
    app.run()
"""
    diagnostics = _mr004_diagnostics(code)
    assert len(diagnostics) == 1
    assert len(diagnostics[0].line) == 2
