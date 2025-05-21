# Copyright 2024 Marimo. All rights reserved.
"""Message Types

Messages that the kernel sends to the frontend.
"""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Sequence  # noqa: TC003
from dataclasses import asdict, dataclass, field
from types import ModuleType
from typing import (
    Any,
    ClassVar,
    Literal,
    Optional,
    Union,
    cast,
)
from uuid import uuid4

from marimo import _loggers as loggers
from marimo._ast.app_config import _AppConfig
from marimo._ast.cell import CellConfig, RuntimeStateType
from marimo._ast.toplevel import TopLevelHints, TopLevelStatus
from marimo._data.models import (
    ColumnStats,
    DataSourceConnection,
    DataTable,
    DataTableSource,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.completion_option import CompletionOption
from marimo._messaging.context import RUN_ID_CTX, RunId_t
from marimo._messaging.errors import (
    Error,
    MarimoInternalError,
    is_sensitive_error,
)
from marimo._messaging.mimetypes import KnownMimeType
from marimo._messaging.streams import output_max_bytes
from marimo._messaging.types import Stream
from marimo._messaging.variables import get_variable_preview
from marimo._output.hypertext import Html
from marimo._plugins.core.json_encoder import WebComponentEncoder
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._runtime.context import get_context
from marimo._runtime.context.types import ContextNotInitializedError
from marimo._runtime.context.utils import get_mode
from marimo._runtime.layout.layout import LayoutConfig
from marimo._secrets.models import SecretKeysWithProvider
from marimo._types.ids import CellId_t, RequestId, WidgetModelId
from marimo._utils.platform import is_pyodide, is_windows

LOGGER = loggers.marimo_logger()


def serialize(datacls: Any) -> dict[str, JSONType]:
    # TODO(akshayka): maybe serialize as bytes (JSON), not objects ...,
    # then `send_bytes` over connection ... to try to avoid pickling
    # issues
    try:
        # Try to serialize as a dataclass
        return cast(
            dict[str, JSONType],
            asdict(datacls),
        )
    except Exception:
        # If that fails, try to serialize using the WebComponentEncoder
        return cast(
            dict[str, JSONType],
            json.loads(WebComponentEncoder.json_dumps(datacls)),
        )


@dataclass
class Op:
    name: ClassVar[str]

    # TODO(akshayka): fix typing once mypy has stricter typing for asdict
    def broadcast(self, stream: Optional[Stream] = None) -> None:
        if stream is None:
            try:
                ctx = get_context()
            except ContextNotInitializedError:
                LOGGER.debug("No context initialized.")
                return
            else:
                stream = ctx.stream

        try:
            stream.write(op=self.name, data=self.serialize())
        except Exception as e:
            LOGGER.exception(
                "Error serializing op %s: %s",
                self.__class__.__name__,
                e,
            )
            return

    def serialize(self) -> dict[str, Any]:
        return serialize(self)


@dataclass
class CellOp(Op):
    """Op to transition a cell.

    A CellOp's data has some optional fields:

    output        - a CellOutput
    console       - a CellOutput (console msg to append), or a list of
                    CellOutputs
    status        - execution status
    stale_inputs  - whether the cell has stale inputs (variables, modules, ...)
    run_id        - the run associated with this cell.
    serialization - the serialization status of the cell

    Omitting a field means that its value should be unchanged!

    And one required field:

    cell_id - the cell id
    """

    name: ClassVar[str] = "cell-op"
    cell_id: CellId_t
    output: Optional[CellOutput] = None
    console: Optional[Union[CellOutput, list[CellOutput]]] = None
    status: Optional[RuntimeStateType] = None
    stale_inputs: Optional[bool] = None
    run_id: Optional[RunId_t] = None
    serialization: Optional[str] = None
    timestamp: float = field(default_factory=lambda: time.time())

    def __post_init__(self) -> None:
        if self.run_id is not None:
            return

        # We currently don't support tracing for replayed cell ops (previous session runs)
        if self.status == "idle":
            self.run_id = None
            return

        try:
            self.run_id = RUN_ID_CTX.get()
        except LookupError:
            # Be specific about the exception we're catching
            # The context variable hasn't been set yet
            self.run_id = None
        except Exception as e:
            LOGGER.error("Error getting run id: %s", str(e))
            self.run_id = None

    @staticmethod
    def maybe_truncate_output(
        mimetype: KnownMimeType, data: str
    ) -> tuple[KnownMimeType, str]:
        if (size := sys.getsizeof(data)) > output_max_bytes():
            from marimo._output.md import md
            from marimo._plugins.stateless.callout import callout

            text = f"""
                <span class="text-error">**Your output is too large**</span>

                Your output is too large for marimo to show. It has a size
                of {size} bytes. Did you output this object by accident?

                If this limitation is a problem for you, you can configure
                the max output size by adding (eg)

                ```
                [tool.marimo.runtime]
                output_max_bytes = 10_000_000
                ```

                to your pyproject.toml, or with the environment variable
                `MARIMO_OUTPUT_MAX_BYTES`:

                ```
                export MARIMO_OUTPUT_MAX_BYTES=10_000_000
                ```

                Increasing the max output size may cause performance issues.
                If you run into problems, please reach out
                to us on [Discord](https://marimo.io/discord?ref=app) or
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
        status: Optional[RuntimeStateType],
        stream: Stream | None = None,
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
        ).broadcast(stream=stream)

    @staticmethod
    def broadcast_empty_output(
        cell_id: Optional[CellId_t],
        status: Optional[RuntimeStateType],
        stream: Stream | None = None,
    ) -> None:
        cell_id = (
            cell_id if cell_id is not None else get_context().stream.cell_id
        )
        assert cell_id is not None
        CellOp(
            cell_id=cell_id,
            output=CellOutput.empty(),
            status=status,
        ).broadcast(stream=stream)

    @staticmethod
    def broadcast_console_output(
        channel: CellChannel,
        mimetype: KnownMimeType,
        data: str,
        cell_id: Optional[CellId_t],
        status: Optional[RuntimeStateType],
        stream: Stream | None = None,
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
        ).broadcast(stream=stream)

    @staticmethod
    def broadcast_status(
        cell_id: CellId_t,
        status: RuntimeStateType,
        stream: Stream | None = None,
    ) -> None:
        if status != "running":
            CellOp(cell_id=cell_id, status=status).broadcast()
        else:
            # Console gets cleared on "running"
            CellOp(cell_id=cell_id, console=[], status=status).broadcast(
                stream=stream
            )

    @staticmethod
    def broadcast_error(
        data: Sequence[Error],
        clear_console: bool,
        cell_id: CellId_t,
    ) -> None:
        console: Optional[list[CellOutput]] = [] if clear_console else None

        # In run mode, we don't want to broadcast the error. Instead we want to print the error to the console
        # and then broadcast a new error such that the data is hidden.
        safe_errors: list[Error] = []
        if get_mode() == "run":
            for error in data:
                # Skip non-sensitive errors
                if not is_sensitive_error(error):
                    safe_errors.append(error)
                    continue

                error_id = uuid4()
                LOGGER.error(
                    f"(error_id={error_id}) {error.describe()}",
                    extra={"error_id": error_id},
                )
                safe_errors.append(MarimoInternalError(error_id=str(error_id)))
        else:
            safe_errors = list(data)

        CellOp(
            cell_id=cell_id,
            output=CellOutput.errors(safe_errors),
            console=console,
            status=None,
        ).broadcast()

    @staticmethod
    def broadcast_stale(
        cell_id: CellId_t, stale: bool, stream: Stream | None = None
    ) -> None:
        CellOp(cell_id=cell_id, stale_inputs=stale).broadcast(stream)

    @staticmethod
    def broadcast_serialization(
        cell_id: CellId_t,
        serialization: TopLevelStatus,
        stream: Stream | None = None,
    ) -> None:
        status: Optional[TopLevelHints] = serialization.hint
        CellOp(cell_id=cell_id, serialization=str(status)).broadcast(stream)


@dataclass
class HumanReadableStatus:
    """Human-readable status."""

    code: Literal["ok", "error"]
    title: Union[str, None] = None
    message: Union[str, None] = None


@dataclass
class FunctionCallResult(Op):
    """Result of calling a function."""

    name: ClassVar[str] = "function-call-result"

    function_call_id: RequestId
    return_value: JSONType
    status: HumanReadableStatus

    def __post_init__(self) -> None:
        # We want to serialize the return_value using our custom JSON encoder
        try:
            self.return_value = json.loads(
                WebComponentEncoder.json_dumps(self.return_value)
            )
        except Exception as e:
            LOGGER.exception(
                "Error serializing function call result %s: %s",
                self.__class__.__name__,
                e,
            )

    def serialize(self) -> dict[str, Any]:
        try:
            return serialize(self)
        except Exception as e:
            LOGGER.exception(
                "Error serializing function call result %s: %s",
                self.__class__.__name__,
                e,
            )
            return serialize(
                FunctionCallResult(
                    function_call_id=self.function_call_id,
                    return_value=None,
                    status=HumanReadableStatus(
                        code="error",
                        title="Error calling function",
                        message="Failed to serialize function call result",
                    ),
                )
            )


@dataclass
class RemoveUIElements(Op):
    """Invalidate UI elements for a given cell."""

    name: ClassVar[str] = "remove-ui-elements"
    cell_id: CellId_t


@dataclass
class SendUIElementMessage(Op):
    """Send a message to a UI element."""

    name: ClassVar[str] = "send-ui-element-message"
    ui_element: Optional[str]
    model_id: Optional[WidgetModelId]
    message: dict[str, Any]
    buffers: Optional[list[str]] = None


@dataclass
class Interrupted(Op):
    """Written when the kernel is interrupted by the user."""

    name: ClassVar[str] = "interrupted"


@dataclass
class CompletedRun(Op):
    """Written on run completion (of submitted cells and their descendants."""

    name: ClassVar[str] = "completed-run"


@dataclass
class KernelCapabilities:
    terminal: bool = False
    pylsp: bool = False

    def __post_init__(self) -> None:
        # Only available in mac/linux
        self.terminal = not is_windows() and not is_pyodide()
        self.pylsp = DependencyManager.pylsp.has()


@dataclass
class KernelReady(Op):
    """Kernel is ready for execution."""

    name: ClassVar[str] = "kernel-ready"
    cell_ids: tuple[CellId_t, ...]
    codes: tuple[str, ...]
    names: tuple[str, ...]
    layout: Optional[LayoutConfig]
    configs: tuple[CellConfig, ...]
    # Whether the kernel was resumed from a previous session
    resumed: bool
    # If the kernel was resumed, the values of the UI elements
    ui_values: Optional[dict[str, JSONType]]
    # If the kernel was resumed, the last executed code for each cell
    last_executed_code: Optional[dict[CellId_t, str]]
    # If the kernel was resumed, the last execution time for each cell
    last_execution_time: Optional[dict[CellId_t, float]]
    # App config
    app_config: _AppConfig
    # Whether the kernel is kiosk mode
    kiosk: bool
    # Kernel capabilities
    capabilities: KernelCapabilities


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
class MissingPackageAlert(Op):
    name: ClassVar[str] = "missing-package-alert"
    packages: list[str]
    isolated: bool


# package name => installation status
PackageStatusType = dict[
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
    declared_by: list[CellId_t]
    used_by: list[CellId_t]


@dataclass
class VariableValue:
    name: str
    value: Optional[str]
    datatype: Optional[str]

    def __init__(
        self, name: str, value: object, datatype: Optional[str] = None
    ) -> None:
        self.name = name

        # Defensively try-catch attribute accesses, which could raise
        # exceptions
        # If datatype is already defined, don't try to infer it
        if datatype is None:
            try:
                self.datatype = (
                    type(value).__name__ if value is not None else None
                )
            except Exception:
                self.datatype = datatype
        else:
            self.datatype = datatype

        try:
            self.value = self._format_value(value)
        except Exception:
            self.value = None

    def _stringify(self, value: object) -> str:
        MAX_STR_LEN = 50

        if isinstance(value, str):
            if len(value) > MAX_STR_LEN:
                return value[:MAX_STR_LEN]
            return value

        try:
            # str(value) can be slow for large objects
            # or lead to large memory spikes
            return get_variable_preview(value, max_str_len=MAX_STR_LEN)
        except BaseException:
            # Catch-all: some libraries like Polars have bugs and raise
            # BaseExceptions, which shouldn't crash the kernel
            return "<UNKNOWN>"

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


@dataclass
class Datasets(Op):
    """List of datasets."""

    name: ClassVar[str] = "datasets"
    tables: list[DataTable]
    clear_channel: Optional[DataTableSource] = None


@dataclass
class SQLTablePreview(Op):
    """Preview of a table in a SQL database."""

    name: ClassVar[str] = "sql-table-preview"
    request_id: RequestId
    table: Optional[DataTable]
    error: Optional[str] = None


@dataclass
class SQLTableListPreview(Op):
    """Preview of a list of tables in a schema."""

    name: ClassVar[str] = "sql-table-list-preview"
    request_id: RequestId
    tables: list[DataTable] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class DataColumnPreview(Op):
    """Preview of a column in a dataset."""

    name: ClassVar[str] = "data-column-preview"
    table_name: str
    column_name: str
    chart_spec: Optional[str] = None
    chart_max_rows_errors: bool = False
    chart_code: Optional[str] = None
    error: Optional[str] = None
    missing_packages: Optional[list[str]] = None
    stats: Optional[ColumnStats] = None


@dataclass
class DataSourceConnections(Op):
    name: ClassVar[str] = "data-source-connections"
    connections: list[DataSourceConnection]


@dataclass
class QueryParamsSet(Op):
    """Set query parameters."""

    name: ClassVar[str] = "query-params-set"
    key: str
    value: Union[str, list[str]]


@dataclass
class QueryParamsAppend(Op):
    name: ClassVar[str] = "query-params-append"
    key: str
    value: str


@dataclass
class QueryParamsDelete(Op):
    name: ClassVar[str] = "query-params-delete"
    key: str
    # If value is None, delete all values for the key
    # If a value is provided, only that value is deleted
    value: Optional[str]


@dataclass
class QueryParamsClear(Op):
    # Clear all query parameters
    name: ClassVar[str] = "query-params-clear"


@dataclass
class FocusCell(Op):
    name: ClassVar[str] = "focus-cell"
    cell_id: CellId_t


@dataclass
class UpdateCellCodes(Op):
    name: ClassVar[str] = "update-cell-codes"
    cell_ids: list[CellId_t]
    codes: list[str]
    # If true, this means the code was not run on the backend when updating
    # the cell codes.
    code_is_stale: bool


@dataclass
class SecretKeysResult(Op):
    """Result of listing secret keys."""

    request_id: RequestId
    name: ClassVar[str] = "secret-keys-result"
    secrets: list[SecretKeysWithProvider]


@dataclass
class UpdateCellIdsRequest(Op):
    """
    Update the cell ID ordering of the cells in the notebook.

    Right now we send the entire list of cell IDs,
    but in the future we might want to send change-deltas.
    """

    name: ClassVar[str] = "update-cell-ids"
    cell_ids: list[CellId_t]


MessageOperation = Union[
    # Cell operations
    CellOp,
    FunctionCallResult,
    SendUIElementMessage,
    RemoveUIElements,
    # Notebook operations
    Reload,
    Reconnected,
    Interrupted,
    CompletedRun,
    KernelReady,
    # Editor operations
    CompletionResult,
    # Alerts
    Alert,
    Banner,
    MissingPackageAlert,
    InstallingPackageAlert,
    # Variables
    Variables,
    VariableValues,
    # Query params
    QueryParamsSet,
    QueryParamsAppend,
    QueryParamsDelete,
    QueryParamsClear,
    # Datasets
    Datasets,
    DataColumnPreview,
    SQLTablePreview,
    SQLTableListPreview,
    DataSourceConnections,
    # Secrets
    SecretKeysResult,
    # Kiosk specific
    FocusCell,
    UpdateCellCodes,
    UpdateCellIdsRequest,
]
