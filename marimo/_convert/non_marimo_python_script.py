# Copyright 2026 Marimo. All rights reserved.
"""Convert non-marimo Python scripts to marimo notebooks."""

from __future__ import annotations

import json

from marimo._convert.ipynb import convert_from_ipynb_to_notebook_ir
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


def _transform_main_blocks(ir: NotebookSerialization) -> None:
    """Transform if __name__ == "__main__": blocks in cells to marimo-compatible functions."""
    main_pattern = 'if __name__ == "__main__":'

    for cell in ir.cells:
        if main_pattern in cell.code:
            parts = cell.code.split(main_pattern, 1)
            before_main = parts[0].strip()

            # replace the if __name__ == "__main__": with def _main_():
            main_block = "def _main_():" + parts[1] + "\n\n_main_()"

            if before_main:
                cell.code = before_main + "\n\n" + main_block
            else:
                cell.code = main_block
