# Copyright 2024 Marimo. All rights reserved.
"""Convert unknown Python scripts to marimo notebooks."""

from __future__ import annotations

from marimo._ast.parse import Parser
from marimo._schemas.serialization import (
    AppInstantiation,
    CellDef,
    NotebookSerialization,
)


def convert_unknown_py_to_notebook_ir(source: str) -> NotebookSerialization:
    """Convert an unknown Python script to marimo notebook IR.

    This should only be called after verifying the file is not already
    a valid marimo notebook. It converts by:
    1. Preserving the header (docstrings/comments)
    2. Splitting on 'if __name__ == "__main__":' if present:
       - Everything before goes into the first cell
       - The main block is transformed into a second cell with:
         - 'if __name__ == "__main__":' replaced with 'def _main_():'
         - '_main_()' called at the end
    3. If no main block exists, all content goes into a single cell
    """
    parser = Parser(source)
    body = parser.node_stack()
    cells: list[CellDef] = []
    header_result = parser.parse_header(body)

    header = header_result.unwrap()
    remaining = parser.extractor.contents[len(header.value) :].strip()

    if remaining:
        # Split on if __name__ == "__main__":
        main_pattern = 'if __name__ == "__main__":'
        if main_pattern in remaining:
            parts = remaining.split(main_pattern, 1)
            before_main = parts[0].strip()

            # Replace the if __name__ == "__main__": with def _main_():
            main_block = "def _main_():" + parts[1] + "\n\n_main_()"

            # Create cells
            if before_main:
                cells.append(
                    CellDef(
                        lineno=1,
                        col_offset=0,
                        end_lineno=1,
                        end_col_offset=0,
                        code=before_main,
                        name="_",
                        options={},
                    )
                )

            cells.append(
                CellDef(
                    lineno=2,
                    col_offset=0,
                    end_lineno=2,
                    end_col_offset=0,
                    code=main_block,
                    name="_",
                    options={},
                )
            )
        else:
            # No main block, put everything in one cell
            cells.append(
                CellDef(
                    lineno=1,
                    col_offset=0,
                    end_lineno=1,
                    end_col_offset=0,
                    code=remaining,
                    name="_",
                    options={},
                )
            )

    return NotebookSerialization(
        header=header,
        version=None,
        app=AppInstantiation(),
        cells=cells,
        violations=header_result.violations,
        valid=False,
    )
