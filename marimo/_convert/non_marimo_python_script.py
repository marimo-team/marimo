# Copyright 2026 Marimo. All rights reserved.
"""Convert non-marimo Python scripts to marimo notebooks."""

from __future__ import annotations

import ast
import json

from marimo._convert.ipynb.to_ir import convert_from_ipynb_to_notebook_ir
from marimo._schemas.serialization import (
    AppInstantiation,
    Header,
    NotebookSerialization,
    UnparsableCell,
)


def convert_pypercent_script_to_notebook_ir(
    source: str,
) -> NotebookSerialization:
    """Convert a pypercent Python script into marimo notebook IR.

    Converts pypercent to jupyter to marimo notebook IR using jupytext.
    """
    try:
        import jupytext  # type: ignore[import-untyped]
    except ImportError as e:
        raise ImportError(
            "Converting py:percent format requires jupytext"
        ) from e
    notebook = jupytext.reads(source, fmt="py:percent")
    notebook_str = json.dumps(notebook)

    ir = convert_from_ipynb_to_notebook_ir(notebook_str)
    _transform_main_blocks(ir)
    return ir


def convert_python_block_to_notebook_ir(
    source: str,
) -> NotebookSerialization:
    """Convert a Python script block to marimo notebook IR.

    This is used when the script is not in the notebook format.
    """
    notebook = {"cells": [{"source": source, "cell_type": "code"}]}
    notebook_str = json.dumps(notebook)

    ir = convert_from_ipynb_to_notebook_ir(notebook_str)
    _transform_main_blocks(ir)
    return ir


def convert_script_block_to_notebook_ir(
    source: str,
) -> NotebookSerialization:
    """Converts unknown script block to marimo notebook IR.

    Puts all content into a single cell. Generally used for unparsable scripts.
    """
    return NotebookSerialization(
        app=AppInstantiation(),
        header=Header(value=""),
        cells=[
            UnparsableCell(
                code=source,
            )
        ],
    )


def convert_non_marimo_python_script_to_notebook_ir(
    source: str,
) -> NotebookSerialization:
    """Convert a Python script that isn't in the notebook format into marimo notebook IR.

    This should only be called after verifying the file is not already
    a valid marimo notebook. It converts by:
    1. If pypercent format is detected (# %%), use jupytext for conversion
    2. Otherwise, puts all content into a single cell
    3. Preserves PEP 723 inline script metadata if present
    """

    if "# %%" in source:
        return convert_pypercent_script_to_notebook_ir(source)
    return convert_python_block_to_notebook_ir(source)


def convert_non_marimo_script_to_notebook_ir(
    source: str,
) -> NotebookSerialization:
    """Convert a non-marimo script to marimo notebook IR.

    This is a convenience function that turns any string into a
    marimo notebook.
    """
    try:
        return convert_non_marimo_python_script_to_notebook_ir(source)
    except ImportError:
        pass
    try:
        import ast

        ast.parse(source)  # Validate if it's valid Python code
        return convert_python_block_to_notebook_ir(source)
    except SyntaxError:
        return convert_script_block_to_notebook_ir(source)


def _is_main_guard(test: ast.expr) -> bool:
    """Whether `test` is `__name__ == "__main__"` (in either order)."""
    if not (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Eq)
        and len(test.comparators) == 1
    ):
        return False

    def is_name(expr: ast.expr) -> bool:
        return isinstance(expr, ast.Name) and expr.id == "__name__"

    def is_main(expr: ast.expr) -> bool:
        return isinstance(expr, ast.Constant) and expr.value == "__main__"

    left, right = test.left, test.comparators[0]
    return (is_name(left) and is_main(right)) or (
        is_main(left) and is_name(right)
    )


def _transform_main_blocks(ir: NotebookSerialization) -> None:
    """Transform if __name__ == "__main__": blocks in cells to marimo-compatible functions."""
    for cell in ir.cells:
        # Locate a real, top-level `if __name__ == "__main__":` statement via
        # the AST -- a naive string search would also match occurrences inside
        # string literals or comments and corrupt the cell. Cells that don't
        # parse are left untouched; they are emitted as unparsable cells
        # downstream anyway.
        try:
            tree = ast.parse(cell.code)
        except SyntaxError:
            continue

        guard = None
        for node in tree.body:
            if (
                isinstance(node, ast.If)
                and not node.orelse
                and _is_main_guard(node.test)
            ):
                guard = node
                break
        if guard is None:
            continue

        # Absolute offset of each line start (ast linenos are 1-based and
        # count physical "\n"-separated lines).
        line_starts = [0]
        for line in cell.code.split("\n"):
            line_starts.append(line_starts[-1] + len(line) + 1)

        start = line_starts[guard.lineno - 1] + guard.col_offset
        test_end_lineno = guard.test.end_lineno or guard.lineno
        test_end_col = guard.test.end_col_offset or 0
        test_end = line_starts[test_end_lineno - 1] + test_end_col
        # The colon that closes the `if` header is the first ":" after the
        # end of the test expression (comments cannot appear before it).
        colon = cell.code.index(":", test_end)

        before_main = cell.code[:start].strip()

        # replace the if __name__ == "__main__": with def _main_():
        main_block = "def _main_():" + cell.code[colon + 1 :] + "\n\n_main_()"

        if before_main:
            cell.code = before_main + "\n\n" + main_block
        else:
            cell.code = main_block
