# Copyright 2023 Marimo. All rights reserved.
import sys

from marimo._messaging.ops import CellOp
from marimo._output import formatting
from marimo._output.rich_help import mddoc
from marimo._runtime.context import get_context


@mddoc
def write(value: object) -> None:
    """Make `object` the output of the currently executing cell.

    Call `mo.output.write()` to write to a cell's output area. Subsequent calls
    to this function replace previously written outputs.

    **Args:**

    - `value`: object to output
    """
    ctx = get_context()
    if ctx.kernel.execution_context is None:
        return
    ctx.kernel.execution_context.output = value

    cell_id = ctx.kernel.execution_context.cell_id
    output = formatting.try_format(value)
    if output.traceback is not None:
        sys.stderr.write(output.traceback)
    CellOp.broadcast_output(
        channel="output",
        mimetype=output.mimetype,
        data=output.data,
        cell_id=cell_id,
        status=None,
    )


@mddoc
def append(value: object) -> None:
    """Append a new object to the currently executing cell's output.

    Call this function to incrementally build a cell's output. Appended
    outputs are stacked vertically.

    **Args:**

    - `value`: object to output
    """
    raise NotImplementedError


@mddoc
def clear() -> None:
    """Clear the cell's current output."""
    ctx = get_context()
    if ctx.kernel.execution_context is None:
        return
    CellOp.broadcast_empty_output(
        cell_id=ctx.kernel.execution_context.cell_id, status=None
    )
