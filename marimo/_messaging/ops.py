# Copyright 2024 Marimo. All rights reserved.
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
    List,
    Literal,
    Optional,
    Sequence,
    Tuple,
    Union,
    cast,
)

from marimo import _loggers as loggers
from marimo._ast.cell import CellConfig, CellId_t, CellStatusType
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.completion_option import CompletionOption
from marimo._messaging.errors import Error
from marimo._messaging.mimetypes import KnownMimeType
from marimo._messaging.streams import OUTPUT_MAX_BYTES
from marimo._messaging.types import Stream
from marimo._output.hypertext import Html
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._runtime.context import get_context
from marimo._runtime.layout.layout import LayoutConfig

LOGGER = loggers.marimo_logger()


def serialize(datacls: Any) -> dict[str, JSONType]:
    return cast(Dict[str, JSONType], asdict(datacls))


@dataclass
class Op:
    name: ClassVar[str]

    # TODO(akshayka): fix typing once mypy has stricter typing for asdict
    def broadcast(self, stream: Optional[Stream] = None) -> None:
        stream = stream if stream is not None else get_context().stream
        LOGGER.debug("Broadcasting op: %s", self)
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
    console: Optional[Union[CellOutput, List[CellOutput]]] = None
    status: Optional[CellStatusType] = None
    timestamp: float = field(default_factory=lambda: time.time())

    @staticmethod
    def maybe_truncate_output(
        mimetype: KnownMimeType, data: str
    ) -> tuple[KnownMimeType, str]:
        if (size := sys.getsizeof(data)) > OUTPUT_MAX_BYTES:
            from marimo._output.md import md
            from marimo._plugins.stateless.callout import callout

            text = f"""
                <span class="text-error">**Your output is too large**</span>

                Your output is too large for marimo to show. It has a size
                of {size} bytes. Did you output this object by accident?

                If this limitation is a problem for you, you can configure
                the max output size with the environment variable
                `MARIMO_OUTPUT_MAX_BYTES`. For example, to increase
                the max output to 10 MB, use:

                ```
                export MARIMO_OUTPUT_MAX_BYTES=10_000_000
                ```

                Increasing the max output size may cause performance issues.
                If you run into problems, please reach out
                to us on [Discord](https://discord.gg/JE7nhX6mD8) or
                [GitHub](https://github.com/marimo-team/marimo/issues).
                """

            warning = callout(
                md(text),
                kind="warn",
            )
            mimetype, data = warning._mime_()
        return mimetype, data

    @staticmethod
    def broadcast_output(
        channel: CellChannel,
        mimetype: KnownMimeType,
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
                channel=CellChannel.OUTPUT,
                mimetype="text/plain",
                data="",
            ),
            status=status,
        ).broadcast()

    @staticmethod
    def broadcast_console_output(
        channel: CellChannel,
        mimetype: KnownMimeType,
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
                channel=CellChannel.MARIMO_ERROR,
                mimetype="application/vnd.marimo+error",
                data=data,
            ),
            console=console,
            status=status,
        ).broadcast()


@dataclass
class HumanReadableStatus(Op):
    """Human-readable status."""

    code: Literal["ok", "error"]
    title: Union[str, None] = None
    message: Union[str, None] = None


@dataclass
class FunctionCallResult(Op):
    """Result of calling a function."""

    name: ClassVar[str] = "function-call-result"

    function_call_id: str
    return_value: JSONType
    status: HumanReadableStatus


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
    cell_ids: Tuple[CellId_t, ...]
    codes: Tuple[str, ...]
    names: Tuple[str, ...]
    layout: Optional[LayoutConfig]
    configs: Tuple[CellConfig, ...]
    # Whether the kernel was resumed from a previous session
    resumed: bool
    # If the kernel was resumed, the values of the UI elements
    ui_values: Optional[Dict[str, JSONType]]
    # If the kernel was resumed, the last executed code for each cell
    last_executed_code: Optional[Dict[CellId_t, str]]


@dataclass
class CompletionResult(Op):
    """Code completion result."""

    name: ClassVar[str] = "completion-result"
    completion_id: str
    prefix_length: int
    options: List[CompletionOption]


@dataclass
class Alert(Op):
    name: ClassVar[str] = "alert"
    title: str
    # description may be HTML
    description: str
    variant: Optional[Literal["danger"]] = None


@dataclass
class MissingPackageAlert(Op):
    name: ClassVar[str] = "missing-package-alert"
    packages: List[str]
    isolated: bool


# package name => installation status
PackageStatusType = Dict[
    str, Literal["queued", "installing", "installed", "failed"]
]


@dataclass
class InstallingPackageAlert(Op):
    name: ClassVar[str] = "installing-package-alert"
    packages: PackageStatusType


@dataclass
class Reconnected(Op):
    name: ClassVar[str] = "reconnected"


@dataclass
class Banner(Op):
    name: ClassVar[str] = "banner"
    title: str
    # description may be HTML
    description: str
    variant: Optional[Literal["danger"]] = None
    action: Optional[Literal["restart"]] = None


@dataclass
class Reload(Op):
    name: ClassVar[str] = "reload"


@dataclass
class VariableDeclaration:
    name: str
    declared_by: List[CellId_t]
    used_by: List[CellId_t]


@dataclass
class VariableValue:
    name: str
    datatype: Optional[str]
    value: Optional[str]

    def __init__(
        self, name: str, value: object, datatype: Optional[str] = None
    ) -> None:
        self.name = name

        # Defensively try-catch attribute accesses, which could raise
        # exceptions
        try:
            self.datatype = type(value).__name__ if value is not None else None
        except Exception:
            self.datatype = datatype

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
    variables: List[VariableDeclaration]


@dataclass
class VariableValues(Op):
    """List of variables and their types/values."""

    name: ClassVar[str] = "variable-values"
    variables: List[VariableValue]


MessageOperation = Union[
    CellOp,
    HumanReadableStatus,
    Reload,
    Reconnected,
    FunctionCallResult,
    RemoveUIElements,
    Interrupted,
    CompletedRun,
    KernelReady,
    CompletionResult,
    Alert,
    Banner,
    MissingPackageAlert,
    InstallingPackageAlert,
    Variables,
    VariableValues,
]
