# Copyright 2024 Marimo. All rights reserved.
"""Message Types

Messages that the kernel sends to the frontend.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Sequence  # noqa: TC003
from types import ModuleType
from typing import (
    Any,
    ClassVar,
    Literal,
    Optional,
    Union,
)
from uuid import uuid4

import msgspec

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
from marimo._messaging.msgspec_encoder import encode_json_bytes
from marimo._messaging.streams import output_max_bytes
from marimo._messaging.types import KernelMessage, Stream
from marimo._messaging.variables import get_variable_preview
from marimo._output.hypertext import Html
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


def serialize_kernel_message(message: Op) -> KernelMessage:
    """
    Serialize a MessageOperation to a KernelMessage.
    """
    return KernelMessage(encode_json_bytes(message))


def deserialize_kernel_message(message: KernelMessage) -> MessageOperation:
    """
    Deserialize a KernelMessage to a MessageOperation.
    """
    return msgspec.json.decode(message, strict=True, type=MessageOperation)  # type: ignore[no-any-return]


class _OpName(msgspec.Struct):
    op: str


def deserialize_kernel_operation_name(message: KernelMessage) -> str:
    """
    Deserialize a KernelMessage to a MessageOperation name.
    """
    # We use the Op type to deserialize the message because it is slimmer than MessageOperation
    return msgspec.json.decode(message, strict=True, type=_OpName).op


class Op(msgspec.Struct, tag_field="op"):
    name: ClassVar[str]

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
            stream.write(serialize_kernel_message(self))
        except Exception as e:
            LOGGER.exception(
                "Error serializing op %s: %s",
                self.__class__.__name__,
                e,
            )
            return


class CellOp(Op, tag="cell-op"):
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
    timestamp: float = msgspec.field(default_factory=lambda: time.time())

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


class HumanReadableStatus(msgspec.Struct):
    """Human-readable status."""

    code: Literal["ok", "error"]
    title: Union[str, None] = None
    message: Union[str, None] = None


class FunctionCallResult(Op, tag="function-call-result"):
    """Result of calling a function."""

    name: ClassVar[str] = "function-call-result"

    function_call_id: RequestId
    return_value: JSONType
    status: HumanReadableStatus

    def serialize(self) -> KernelMessage:
        try:
            return serialize_kernel_message(self)
        except Exception as e:
            LOGGER.exception(
                "Error serializing function call result %s: %s",
                self.__class__.__name__,
                e,
            )
            return serialize_kernel_message(
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


class RemoveUIElements(Op, tag="remove-ui-elements"):
    """Invalidate UI elements for a given cell."""

    name: ClassVar[str] = "remove-ui-elements"
    cell_id: CellId_t


class SendUIElementMessage(Op, tag="send-ui-element-message"):
    """Send a message to a UI element."""

    name: ClassVar[str] = "send-ui-element-message"
    ui_element: Optional[str]
    model_id: Optional[WidgetModelId]
    message: dict[str, Any]
    buffers: Optional[list[str]] = None


class Interrupted(Op, tag="interrupted"):
    """Written when the kernel is interrupted by the user."""

    name: ClassVar[str] = "interrupted"


class CompletedRun(Op, tag="completed-run"):
    """Written on run completion (of submitted cells and their descendants."""

    name: ClassVar[str] = "completed-run"


class KernelCapabilities(msgspec.Struct):
    terminal: bool = False
    pylsp: bool = False
    ty: bool = False
    basedpyright: bool = False

    def __post_init__(self) -> None:
        # Only available in mac/linux
        self.terminal = not is_windows() and not is_pyodide()
        self.pylsp = DependencyManager.pylsp.has()
        self.basedpyright = DependencyManager.basedpyright.has()
        self.ty = DependencyManager.ty.has()


class KernelReady(Op, tag="kernel-ready"):
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


class CompletionResult(Op, tag="completion-result"):
    """Code completion result."""

    name: ClassVar[str] = "completion-result"
    completion_id: str
    prefix_length: int
    options: list[CompletionOption]


class Alert(Op, tag="alert"):
    name: ClassVar[str] = "alert"
    title: str
    # description may be HTML
    description: str
    variant: Optional[Literal["danger"]] = None


class MissingPackageAlert(Op, tag="missing-package-alert"):
    name: ClassVar[str] = "missing-package-alert"
    packages: list[str]
    isolated: bool


# package name => installation status
PackageStatusType = dict[
    str, Literal["queued", "installing", "installed", "failed"]
]


class InstallingPackageAlert(Op, tag="installing-package-alert"):
    name: ClassVar[str] = "installing-package-alert"
    packages: PackageStatusType
    # Optional fields for streaming logs per package
    logs: Optional[dict[str, str]] = None  # package name -> log content
    log_status: Optional[Literal["append", "start", "done"]] = None


class Reconnected(Op, tag="reconnected"):
    name: ClassVar[str] = "reconnected"


class StartupLogs(Op, tag="startup-logs"):
    name: ClassVar[str] = "startup-logs"
    content: str
    status: Literal["append", "start", "done"]


class Banner(Op, tag="banner"):
    name: ClassVar[str] = "banner"
    title: str
    # description may be HTML
    description: str
    variant: Optional[Literal["danger"]] = None
    action: Optional[Literal["restart"]] = None


class Reload(Op, tag="reload"):
    name: ClassVar[str] = "reload"


class VariableDeclaration(msgspec.Struct):
    name: str
    declared_by: list[CellId_t]
    used_by: list[CellId_t]


class VariableValue(msgspec.Struct):
    name: str
    value: Optional[str]
    datatype: Optional[str]

    @staticmethod
    def create(
        name: str, value: object, datatype: Optional[str] = None
    ) -> VariableValue:
        """Factory method to create a VariableValue from an object."""
        # Defensively try-catch attribute accesses, which could raise
        # exceptions
        # If datatype is already defined, don't try to infer it
        if datatype is None:
            try:
                computed_datatype = (
                    type(value).__name__ if value is not None else None
                )
            except Exception:
                computed_datatype = datatype
        else:
            computed_datatype = datatype

        try:
            formatted_value = VariableValue._format_value_static(value)
        except Exception:
            formatted_value = None

        return VariableValue(
            name=name, value=formatted_value, datatype=computed_datatype
        )

    @staticmethod
    def _stringify_static(value: object) -> str:
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

    @staticmethod
    def _format_value_static(value: object) -> str:
        resolved = value
        if isinstance(value, UIElement):
            resolved = value.value
        elif isinstance(value, Html):
            resolved = value.text
        elif isinstance(value, ModuleType):
            resolved = value.__name__
        return VariableValue._stringify_static(resolved)


class Variables(Op, tag="variables"):
    """List of variable declarations."""

    name: ClassVar[str] = "variables"
    variables: list[VariableDeclaration]


class VariableValues(Op, tag="variable-values"):
    """List of variables and their types/values."""

    name: ClassVar[str] = "variable-values"
    variables: list[VariableValue]


class Datasets(Op, tag="datasets"):
    """List of datasets."""

    name: ClassVar[str] = "datasets"
    tables: list[DataTable]
    clear_channel: Optional[DataTableSource] = None


class SQLTablePreview(Op, tag="sql-table-preview"):
    """Preview of a table in a SQL database."""

    name: ClassVar[str] = "sql-table-preview"
    request_id: RequestId
    table: Optional[DataTable]
    error: Optional[str] = None


class SQLTableListPreview(Op, tag="sql-table-list-preview"):
    """Preview of a list of tables in a schema."""

    name: ClassVar[str] = "sql-table-list-preview"
    request_id: RequestId
    tables: list[DataTable] = msgspec.field(default_factory=list)
    error: Optional[str] = None


class ColumnPreview(msgspec.Struct):
    chart_spec: Optional[str] = None
    chart_code: Optional[str] = None
    error: Optional[str] = None
    missing_packages: Optional[list[str]] = None
    stats: Optional[ColumnStats] = None


# We shouldn't need to make table_name and column_name have default values.
# We can use kw_only=True once we drop support for Python 3.9.
class DataColumnPreview(Op, ColumnPreview, tag="data-column-preview"):
    """Preview of a column in a dataset."""

    name: ClassVar[str] = "data-column-preview"
    table_name: str = ""
    column_name: str = ""


class DataSourceConnections(Op, tag="data-source-connections"):
    name: ClassVar[str] = "data-source-connections"
    connections: list[DataSourceConnection]


class QueryParamsSet(Op, tag="query-params-set"):
    """Set query parameters."""

    name: ClassVar[str] = "query-params-set"
    key: str
    value: Union[str, list[str]]


class QueryParamsAppend(Op, tag="query-params-append"):
    name: ClassVar[str] = "query-params-append"
    key: str
    value: str


class QueryParamsDelete(Op, tag="query-params-delete"):
    name: ClassVar[str] = "query-params-delete"
    key: str
    # If value is None, delete all values for the key
    # If a value is provided, only that value is deleted
    value: Optional[str]


class QueryParamsClear(Op, tag="query-params-clear"):
    # Clear all query parameters
    name: ClassVar[str] = "query-params-clear"


class FocusCell(Op, tag="focus-cell"):
    name: ClassVar[str] = "focus-cell"
    cell_id: CellId_t


class UpdateCellCodes(Op, tag="update-cell-codes"):
    name: ClassVar[str] = "update-cell-codes"
    cell_ids: list[CellId_t]
    codes: list[str]
    # If true, this means the code was not run on the backend when updating
    # the cell codes.
    code_is_stale: bool


class SecretKeysResult(Op, tag="secret-keys-result"):
    """Result of listing secret keys."""

    request_id: RequestId
    name: ClassVar[str] = "secret-keys-result"
    secrets: list[SecretKeysWithProvider]


class UpdateCellIdsRequest(Op, tag="update-cell-ids"):
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
    StartupLogs,
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
