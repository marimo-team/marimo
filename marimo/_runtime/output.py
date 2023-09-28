from marimo._messaging.ops import CellOp
from marimo._output.rich_help import mddoc
from marimo._runtime.context import get_context


@mddoc
def write(object: Any) -> None:
    """Make `object` the output of the currently executing cell.

    Call `mo.output.write()` to write to a cell's output area. Subsequent calls
    to this function replace previously written outputs.

    **Args:**

    - `object`: object to output
    """
    raise NotImplementedError


@mddoc
def append(object: Any) -> None:
    """Append a new object to the currently executing cell's output.

    Call this function to incrementally build a cell's output. Appended
    outputs are stacked vertically.

    **Args:**

    - `object`: object to output
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
