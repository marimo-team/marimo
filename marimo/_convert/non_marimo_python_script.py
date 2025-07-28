# Copyright 2024 Marimo. All rights reserved.
"""Convert non-marimo Python scripts to marimo notebooks."""

from __future__ import annotations

import json

from marimo._convert.ipynb import convert_from_ipynb_to_notebook_ir
from marimo._schemas.serialization import NotebookSerialization


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
        try:
            import jupytext  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError(
                "Converting py:percent format requires jupytext"
            ) from e
        notebook = jupytext.reads(source, fmt="py:percent")
    else:
        notebook = {"cells": [{"source": source, "cell_type": "code"}]}

    notebook_str = json.dumps(notebook)

    ir = convert_from_ipynb_to_notebook_ir(notebook_str)
    _transform_main_blocks(ir)
    return ir


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
