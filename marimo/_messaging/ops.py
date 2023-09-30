# Copyright 2023 Marimo. All rights reserved.
"""Message Types

Messages that the kernel sends to the frontend.
"""

from __future__ import annotations

import sys
import time
from dataclasses import asdict, dataclass, field
from types import ModuleType
from typing import (
    Any,
    ClassVar,
    Dict,
    Literal,
    Optional,
    Sequence,
    Union,
    cast,
)

from marimo._ast.cell import CellConfig, CellId_t, CellStatusType
from marimo._messaging.cell_output import CellOutput
from marimo._messaging.completion_option import CompletionOption
from marimo._messaging.errors import Error
from marimo._messaging.streams import OUTPUT_MAX_BYTES, Stream
from marimo._output.hypertext import Html
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._runtime.context import get_context
from marimo._server.layout import LayoutConfig


def serialize(datacls: Any) -> dict[str, JSONType]:
    return cast(Dict[str, JSONType], asdict(datacls))


@dataclass
class Op:
    name: ClassVar[str]

    # TODO(akshayka): fix typing once mypy has stricter typing for asdict
    def broadcast(self, stream: Optional[Stream] = None) -> None:
        stream = stream if stream is not None else get_context().stream
        stream.write(op=self.name, data=serialize(self))


@dataclass
class CellOp(Op):
    """Op to transition a cell.

    A CellOp's data has three optional fields:

    output  - a CellOutput
    console - a CellOutput (console msg to append), or a list of CellOutputs
    status  - execution status

    Omitting a field means that its value should be unchanged!

    And one required field:

    cell_id - the cell id
    """

    name: ClassVar[str] = "cell-op"
    cell_id: CellId_t
    output: Optional[CellOutput] = None
    console: Optional[Union[CellOutput, list[CellOutput]]] = None
    status: Optional[CellStatusType] = None
    timestamp: float = field(default_factory=lambda: time.time())

    @staticmethod
    def maybe_truncate_output(mimetype: str, data: str) -> tuple[str, str]:
        if (size := sys.getsizeof(data)) > OUTPUT_MAX_BYTES:
            from marimo._output.md import md
            from marimo._plugins.stateless.callout_output import callout

            text = f"""
                <span class="text-error">**Your output is too large**</span>

                Your output is too large for marimo to show. It has a size
                of {size} bytes. Did you output this object by accident?

                If this limitation is a problem for you, please reach out
                to us on [Discord](https://discord.gg/JE7nhX6mD8) or
                [Github](https://github.com/marimo-team/marimo/issues).
                """

            warning = callout(
                md(text),
                kind="warn",
            )
            mimetype, data = warning._mime_()
        return mimetype, data

    @staticmethod
    def broadcast_output(
        channel: str,
        mimetype: str,
        data: str,
        cell_id: Optional[CellId_t],
        status: Optional[CellStatusType],
    ) -> None:
        mimetype, data = CellOp.maybe_truncate_output(mimetype, data)
        cell_id = (
            cell_id if cell_id is not None else get_context().stream.cell_id
        )
        assert cell_id is not None
        CellOp(
            cell_id=cell_id,
            output=CellOutput(
                channel=channel,
                mimetype=mimetype,
                data=data,
            ),
            status=status,
        ).broadcast()

    @staticmethod
    def broadcast_empty_output(
        cell_id: Optional[CellId_t],
        status: Optional[CellStatusType],
    ) -> None:
        cell_id = (
            cell_id if cell_id is not None else get_context().stream.cell_id
        )
        assert cell_id is not None
        CellOp(
            cell_id=cell_id,
            output=CellOutput(
                channel="output",
                mimetype="text/plain",
                data="",
            ),
            status=status,
        ).broadcast()

    @staticmethod
    def broadcast_console_output(
        channel: str,
        mimetype: str,
        data: str,
        cell_id: Optional[CellId_t],
        status: Optional[CellStatusType],
    ) -> None:
        mimetype, data = CellOp.maybe_truncate_output(mimetype, data)
        cell_id = (
            cell_id if cell_id is not None else get_context().stream.cell_id
        )
        assert cell_id is not None
        CellOp(
            cell_id=cell_id,
            console=CellOutput(
                channel=channel,
                mimetype=mimetype,
                data=data,
            ),
            status=status,
        ).broadcast()

    @staticmethod
    def broadcast_status(cell_id: CellId_t, status: CellStatusType) -> None:
        if status != "running":
            CellOp(cell_id=cell_id, status=status).broadcast()
        else:
            # Console gets cleared on "running"
            CellOp(cell_id=cell_id, console=[], status=status).broadcast()

    @staticmethod
    def broadcast_error(
        data: Sequence[Error],
        clear_console: bool,
        cell_id: CellId_t,
        status: Optional[CellStatusType],
    ) -> None:
        console: Optional[list[CellOutput]] = [] if clear_console else None
        CellOp(
            cell_id=cell_id,
            output=CellOutput(
                channel="marimo-error",
                mimetype="application/vnd.marimo+error",
                data=data,
            ),
            console=console,
            status=status,
        ).broadcast()


@dataclass
class RemoveUIElements(Op):
    """Invalidate UI elements for a given cell."""

    name: ClassVar[str] = "remove-ui-elements"
    cell_id: CellId_t


@dataclass
class Interrupted(Op):
    """Written when the kernel is interrupted by the user."""

    name: ClassVar[str] = "interrupted"


@dataclass
class CompletedRun(Op):
    """Written on run completion (of submitted cells and their descendants."""

    name: ClassVar[str] = "completed-run"


@dataclass
class KernelReady(Op):
    """Kernel is ready for execution."""

    name: ClassVar[str] = "kernel-ready"
    codes: tuple[str, ...]
    names: tuple[str, ...]
    layout: Optional[LayoutConfig]
    configs: tuple[CellConfig, ...]


@dataclass
class CompletionResult(Op):
    """Code completion result."""

    name: ClassVar[str] = "completion-result"
    completion_id: str
    prefix_length: int
    options: list[CompletionOption]


@dataclass
class Alert(Op):
    name: ClassVar[str] = "alert"
    title: str
    # description may be HTML
    description: str
    variant: Optional[Literal["danger"]] = None


@dataclass
class VariableDeclaration:
    name: str
    declared_by: list[CellId_t]
    used_by: list[CellId_t]


@dataclass
class VariableValue:
    name: str
    datatype: Optional[str]
    value: Optional[str]

    def __init__(self, name: str, value: object):
        self.name = name

        # Defensively try-catch attribute accesses, which could raise
        # exceptions
        try:
            self.datatype = type(value).__name__ if value is not None else None
        except Exception:
            self.datatype = None

        try:
            self.value = self._format_value(value)
        except Exception:
            self.value = None

    def _stringify(self, value: object) -> str:
        return str(value)[:50]

    def _format_value(self, value: object) -> str:
        resolved = value
        if isinstance(value, UIElement):
            resolved = value.value
        elif isinstance(value, Html):
            resolved = value.text
        elif isinstance(value, ModuleType):
            resolved = value.__name__
        return self._stringify(resolved)


@dataclass
class Variables(Op):
    """List of variable declarations."""

    name: ClassVar[str] = "variables"
    variables: list[VariableDeclaration]


@dataclass
class VariableValues(Op):
    """List of variables and their types/values."""

    name: ClassVar[str] = "variable-values"
    variables: list[VariableValue]
