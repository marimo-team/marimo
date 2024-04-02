# Copyright 2024 Marimo. All rights reserved.
import sys

from marimo._ast.cell import CellId_t
from marimo._messaging.cell_output import CellChannel
from marimo._messaging.ops import CellOp
from marimo._output import formatting
from marimo._output.rich_help import mddoc
from marimo._plugins.stateless.flex import vstack
from marimo._runtime.context import get_context


def write_internal(cell_id: CellId_t, value: object) -> None:
    output = formatting.try_format(value)
    if output.traceback is not None:
        sys.stderr.write(output.traceback)
    CellOp.broadcast_output(
        channel=CellChannel.OUTPUT,
        mimetype=output.mimetype,
        data=output.data,
        cell_id=cell_id,
        status=None,
    )


@mddoc
def replace(value: object) -> None:
    """Replace a cell's output with a new one.

    Call `mo.output.replace()` to write to a cell's output area, replacing
    the existing output, if any.

    **Args:**

    - `value`: object to output
    """
    ctx = get_context()
    if ctx.kernel.execution_context is None:
        return
    elif value is None:
        ctx.kernel.execution_context.output = None
    else:
        ctx.kernel.execution_context.output = [formatting.as_html(value)]
    write_internal(cell_id=ctx.kernel.execution_context.cell_id, value=value)


@mddoc
def append(value: object) -> None:
    """Append a new object to a cell's output.

    Call this function to incrementally build a cell's output. Appended
    outputs are stacked vertically.

    **Args:**

    - `value`: object to output
    """
    ctx = get_context()
    if ctx.kernel.execution_context is None:
        return

    if ctx.kernel.execution_context.output is None:
        ctx.kernel.execution_context.output = [formatting.as_html(value)]
    else:
        ctx.kernel.execution_context.output.append(formatting.as_html(value))
    write_internal(
        cell_id=ctx.kernel.execution_context.cell_id,
        value=vstack(ctx.kernel.execution_context.output),
    )


@mddoc
def clear() -> None:
    """Clear a cell's output."""
    return replace(None)


def flush() -> None:
    """Internal function to re-render the cell's output."""
    ctx = get_context()
    if ctx.kernel.execution_context is None:
        return

    if ctx.kernel.execution_context.output is not None:
        value = vstack(ctx.kernel.execution_context.output)
    else:
        value = None
    write_internal(cell_id=ctx.kernel.execution_context.cell_id, value=value)


def remove(value: object) -> None:
    """Internal function to remove an object from a cell's output."""
    ctx = get_context()
    if (
        ctx.kernel.execution_context is None
        or ctx.kernel.execution_context.output is None
    ):
        return
    output = [
        item
        for item in ctx.kernel.execution_context.output
        if item is not value
    ]
    ctx.kernel.execution_context.output = output if output else None
    flush()
