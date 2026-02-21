# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._messaging.cell_output import CellChannel
from marimo._messaging.notification_utils import CellNotificationUtils
from marimo._messaging.tracebacks import write_traceback
from marimo._output import formatting
from marimo._output.rich_help import mddoc
from marimo._runtime.context import get_context
from marimo._runtime.context.types import ContextNotInitializedError
from marimo._types.ids import CellId_t


def write_internal(cell_id: CellId_t, value: object) -> None:
    output = formatting.try_format(value)
    if output.traceback is not None:
        write_traceback(output.traceback)
    CellNotificationUtils.broadcast_output(
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

    Args:
        value: object to output
    """
    try:
        ctx = get_context()
    except ContextNotInitializedError:
        return

    if ctx.execution_context is None:
        return

    output = ctx.execution_context.output
    with output.lock:
        output.clear()
        if value is not None:
            output.append(formatting.as_html(value))
        write_internal(cell_id=ctx.execution_context.cell_id, value=value)


@mddoc
def replace_at_index(value: object, idx: int) -> None:
    """Replace a cell's output at the given index with value.

    Call this function to replace an existing object in a cell's output. If idx
    is equal to the length of the output, this is equivalent to an append.

    Args:
        value: new object to replace an existing object
        idx: index of output to replace
    """

    try:
        ctx = get_context()
    except ContextNotInitializedError:
        return

    if ctx.execution_context is None or not ctx.execution_context.output:
        return

    output = ctx.execution_context.output
    with output.lock:
        output.replace_at_index(formatting.as_html(value), idx)
        write_internal(
            cell_id=ctx.execution_context.cell_id,
            value=output.stack(),
        )


@mddoc
def append(value: object) -> None:
    """Append a new object to a cell's output.

    Call this function to incrementally build a cell's output. Appended
    outputs are stacked vertically.

    Args:
        value: object to output
    """
    try:
        ctx = get_context()
    except ContextNotInitializedError:
        return

    if ctx.execution_context is None:
        return

    output = ctx.execution_context.output
    with output.lock:
        output.append(formatting.as_html(value))
        write_internal(
            cell_id=ctx.execution_context.cell_id,
            value=output.stack(),
        )


@mddoc
def clear() -> None:
    """Clear a cell's output."""
    return replace(None)


def flush() -> None:
    """Internal function to re-render the cell's output."""
    try:
        ctx = get_context()
    except ContextNotInitializedError:
        return

    if ctx.execution_context is None:
        return

    output = ctx.execution_context.output
    with output.lock:
        write_internal(
            cell_id=ctx.execution_context.cell_id, value=output.stack()
        )


def remove(value: object) -> None:
    """Internal function to remove an object from a cell's output."""
    try:
        ctx = get_context()
    except ContextNotInitializedError:
        return

    if ctx.execution_context is None or not ctx.execution_context.output:
        return
    output = ctx.execution_context.output
    with output.lock:
        output.remove(value)
        flush()
