# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._ast.parse import parse_notebook
from marimo._lint.rules.runtime.reusable_definition_order import (
    ReusableDefinitionOrderRule,
)
from tests._lint.utils import lint_notebook


def test_reusable_definition_order_unsafe_fix_reorders_provider_cells():
    code = """import marimo

__generated_with = "0.18.0"
app = marimo.App()


@app.function
def uses_offset(x: int = offset()) -> int:
    return x + 1


@app.function
def offset() -> int:
    return 1


if __name__ == "__main__":
    app.run()
"""
    notebook = parse_notebook(code, filepath="test.py")
    diagnostics = lint_notebook(notebook)

    assert [diagnostic.code for diagnostic in diagnostics] == ["MR003"]

    fixed = ReusableDefinitionOrderRule().apply_unsafe_fix(
        notebook, diagnostics
    )

    assert fixed.cells[0].name == "offset"
    assert fixed.cells[1].name == "uses_offset"
    assert not [
        diagnostic
        for diagnostic in lint_notebook(fixed)
        if diagnostic.code == "MR003"
    ]


def test_reusable_definition_order_unsafe_fix_preserves_provider_order():
    code = """import marimo

__generated_with = "0.18.0"
app = marimo.App()


@app.function
def uses_both(
    one: int = first(),
    two: int = second(),
) -> tuple[int, int]:
    return one, two


@app.function
def first() -> int:
    return 1


@app.function
def second() -> int:
    return 2


if __name__ == "__main__":
    app.run()
"""
    notebook = parse_notebook(code, filepath="test.py")
    diagnostics = lint_notebook(notebook)

    assert [diagnostic.code for diagnostic in diagnostics] == ["MR003"]

    fixed = ReusableDefinitionOrderRule().apply_unsafe_fix(
        notebook, diagnostics
    )

    assert [cell.name for cell in fixed.cells[:3]] == [
        "first",
        "second",
        "uses_both",
    ]
    assert not [
        diagnostic
        for diagnostic in lint_notebook(fixed)
        if diagnostic.code == "MR003"
    ]


def test_reusable_definition_order_unsafe_fix_chained_dependencies():
    code = """import marimo

__generated_with = "0.18.0"
app = marimo.App()


@app.function
def a(x: int = b()) -> int:
    return x


@app.function
def b(x: int = c()) -> int:
    return x


@app.function
def c() -> int:
    return 1


if __name__ == "__main__":
    app.run()
"""
    notebook = parse_notebook(code, filepath="test.py")
    diagnostics = lint_notebook(notebook)

    assert {d.code for d in diagnostics} == {"MR003"}

    fixed = ReusableDefinitionOrderRule().apply_unsafe_fix(
        notebook, diagnostics
    )

    assert [cell.name for cell in fixed.cells[:3]] == ["c", "b", "a"]
    assert not [
        diagnostic
        for diagnostic in lint_notebook(fixed)
        if diagnostic.code == "MR003"
    ]


def test_reusable_definition_order_unsafe_fix_does_not_move_for_setup():
    code = """import marimo

__generated_with = "0.18.0"
app = marimo.App()


with app.setup:
    def uses_offset(x: int = offset()) -> int:
        return x + 1


@app.function
def offset() -> int:
    return 1


if __name__ == "__main__":
    app.run()
"""
    notebook = parse_notebook(code, filepath="test.py")
    original_order = [cell.name for cell in notebook.cells]
    diagnostics = lint_notebook(notebook)

    assert not [d for d in diagnostics if d.code == "MR003"]

    fixed = ReusableDefinitionOrderRule().apply_unsafe_fix(
        notebook, diagnostics
    )

    assert [cell.name for cell in fixed.cells] == original_order
