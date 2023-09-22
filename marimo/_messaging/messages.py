# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import sys
from typing import Any, Optional, Sequence

from marimo._ast.cell import CellId_t, CellStatusType
from marimo._messaging.cell_output import CellOutput
from marimo._messaging.errors import Error
from marimo._messaging.message_types import (
    CellOp,
    CompletedRun,
    Interrupted,
    MessageType,
    RemoveUIElements,
    VariableDeclaration,
    Variables,
    VariableValue,
    VariableValues,
    serialize,
)
from marimo._messaging.streams import OUTPUT_MAX_BYTES
from marimo._output.formatting import get_formatter
from marimo._runtime.context import get_context


def write_output(
    channel: str,
    mimetype: str,
    data: str,
    cell_id: CellId_t,
    status: Optional[CellStatusType],
) -> None:
    if (size := sys.getsizeof(data)) > OUTPUT_MAX_BYTES:
        from marimo._output.md import md
        from marimo._plugins.stateless.callout_output import callout

        warning = callout(
            md(
                f"""
                <span class="text-error">**Your output is too large**</span>

                Your output is too large for marimo to show. It has a size
                of {size} bytes. Did you output this object by accident?

                If this limitation is a problem for you, please reach out
                to us on [Discord](https://discord.gg/JE7nhX6mD8) or
                [Github](https://github.com/marimo-team/marimo/issues).
                """
            ),
            kind="warn",
        )
        mimetype, data = warning._mime_()

    get_context().stream.write(
        op=CellOp.name,
        data=serialize(
            CellOp(
                cell_id=cell_id,
                output=CellOutput(
                    channel=channel,
                    mimetype=mimetype,
                    data=data,
                ),
                status=status,
            )
        ),
    )


def write_stale(cell_id: CellId_t) -> None:
    get_context().stream.write(
        op=CellOp.name,
        data=serialize(CellOp(cell_id=cell_id, status="stale")),
    )


def write_idle(cell_id: CellId_t) -> None:
    get_context().stream.write(
        op=CellOp.name,
        data=serialize(CellOp(cell_id=cell_id, status="idle")),
    )


def write_disabled_transitively(cell_id: CellId_t) -> None:
    get_context().stream.write(
        op=CellOp.name,
        data=serialize(
            CellOp(cell_id=cell_id, status="disabled-transitively")
        ),
    )


def write_queued(cell_id: CellId_t) -> None:
    get_context().stream.write(
        op=CellOp.name,
        data=serialize(CellOp(cell_id=cell_id, status="queued")),
    )


def write_new_run(cell_id: CellId_t) -> None:
    get_context().stream.write(
        op=CellOp.name,
        data=serialize(CellOp(cell_id=cell_id, console=[], status="running")),
    )


def write_marimo_error(
    data: Sequence[Error],
    clear_console: bool,
    cell_id: CellId_t,
    status: Optional[CellStatusType],
) -> None:
    console: Optional[list[CellOutput]] = [] if clear_console else None
    get_context().stream.write(
        op=CellOp.name,
        data=serialize(
            CellOp(
                cell_id=cell_id,
                output=CellOutput(
                    channel="marimo-error",
                    mimetype="application/vnd.marimo+error",
                    data=data,
                ),
                console=console,
                status=status,
            )
        ),
    )


def write_variables(data: list[VariableDeclaration]) -> None:
    get_context().stream.write(
        op=Variables.name,
        data=serialize(Variables(variables=data)),
    )


def write_variable_values(data: list[VariableValue]) -> None:
    get_context().stream.write(
        op=VariableValues.name,
        data=serialize(VariableValues(variables=data)),
    )


def write_interrupted() -> None:
    get_context().stream.write(op=Interrupted.name, data={})


def write_completed_run() -> None:
    get_context().stream.write(op=CompletedRun.name, data={})


def write_remove_ui_elements(cell_id: CellId_t) -> None:
    get_context().stream.write(
        op=RemoveUIElements.name,
        data=serialize(RemoveUIElements(cell_id=cell_id)),
    )


# TODO: refactor messaging code to use this function instead of
# write_* for specific ops ...
def write_message(op: MessageType) -> None:
    get_context().stream.write(op=op.name, data=serialize(op))


def write_output_to_global_stream(
    channel: str, mimetype: str, data: str
) -> None:
    stream = get_context().stream
    assert stream.cell_id is not None
    write_output(channel, mimetype, data, stream.cell_id, status=None)


def write_to_global_console_stream(
    channel: str, mimetype: str, data: str
) -> None:
    stream = get_context().stream
    assert stream.cell_id is not None
    stream.write(
        op=CellOp.name,
        data=serialize(
            CellOp(
                cell_id=stream.cell_id,
                console=CellOutput(
                    channel=channel,
                    mimetype=mimetype,
                    data=data,
                ),
            )
        ),
    )


def _show(value: Any, mimetype: Optional[str] = None) -> None:
    """Shows a value in the current cell's console area

    Uses the media protocol to instantiate a displayable element
    for `value`.
    """
    if (formatter := get_formatter(value)) is not None:
        mimetype, data = formatter(value)
    else:
        mimetype, data = ("text/plain", value)

    write_to_global_console_stream(
        channel="output", mimetype=mimetype, data=data
    )
