# Copyright 2026 Marimo. All rights reserved.
"""Notification message types for kernel-to-frontend communication."""

from __future__ import annotations

import time
from typing import (
    Any,
    ClassVar,
    Literal,
    Optional,
    Union,
)

import msgspec

from marimo import _loggers as loggers
from marimo._ast.app_config import _AppConfig
from marimo._ast.cell import CellConfig, RuntimeStateType
from marimo._data.models import (
    ColumnStats,
    DataSourceConnection,
    DataTable,
    DataTableSource,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.cell_output import CellOutput
from marimo._messaging.completion_option import CompletionOption
from marimo._messaging.context import RUN_ID_CTX, RunId_t
from marimo._plugins.core.web_component import JSONType
from marimo._runtime.layout.layout import LayoutConfig
from marimo._runtime.packages.utils import PackageDescription
from marimo._secrets.models import SecretKeysWithProvider
from marimo._sql.parse import SqlCatalogCheckResult, SqlParseResult
from marimo._types.ids import CellId_t, RequestId, WidgetModelId
from marimo._utils.msgspec_basestruct import BaseStruct
from marimo._utils.platform import is_pyodide, is_windows
from marimo._utils.uv_tree import DependencyTreeNode

LOGGER = loggers.marimo_logger()


class Notification(msgspec.Struct, tag_field="op"):
    """Base class for all kernel-to-frontend notifications.

    Uses msgspec's tagged union with "op" field as discriminator.
    Subclasses must define both tag="..." and name: ClassVar[str].
    """

    name: ClassVar[str]


class CellNotification(Notification, tag="cell-op"):
    """Updates a cell's state in the frontend.

    Only fields that are set (not None) will update the cell state.
    Omitting a field leaves that aspect unchanged.

    Attributes:
        cell_id: Unique identifier of the cell being updated.
        output: Cell's output. Use CellOutput.empty() to clear.
        console: Console messages. Single/list appends, [] clears, None unchanged.
        status: Execution status (idle/running/stale/queued/disabled-transitively).
        stale_inputs: Whether cell has stale inputs from changed dependencies.
        run_id: Execution run ID for tracing. Auto-set from context.
        serialization: Serialization status (TopLevelHints).
        timestamp: Creation timestamp, auto-set.
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


class HumanReadableStatus(msgspec.Struct):
    """Human-readable status for operation results.

    Attributes:
        code: Status code ("ok" or "error").
        title: Optional short title.
        message: Optional detailed description.
    """

    code: Literal["ok", "error"]
    title: Union[str, None] = None
    message: Union[str, None] = None


class FunctionCallResultNotification(Notification, tag="function-call-result"):
    """Result of a frontend-initiated function call.

    Attributes:
        function_call_id: ID matching the original request.
        return_value: Function return value as JSON.
        status: Human-readable success/failure status.
    """

    name: ClassVar[str] = "function-call-result"

    function_call_id: RequestId
    return_value: JSONType
    status: HumanReadableStatus


class RemoveUIElementsNotification(Notification, tag="remove-ui-elements"):
    """Removes UI elements associated with a cell.

    Sent when cell is re-executed or deleted.

    Attributes:
        cell_id: Cell whose UI elements should be removed.
    """

    name: ClassVar[str] = "remove-ui-elements"
    cell_id: CellId_t


class UIElementMessageNotification(
    Notification, tag="send-ui-element-message"
):
    """Sends a message to a UI element/widget.

    Attributes:
        ui_element: UI element identifier (legacy).
        model_id: Widget model ID (newer architecture).
        message: Message payload as dictionary.
        buffers: Optional binary buffers for large data.
    """

    name: ClassVar[str] = "send-ui-element-message"
    ui_element: Optional[str]
    model_id: Optional[WidgetModelId]
    message: dict[str, Any]
    buffers: Optional[list[bytes]] = None


class InterruptedNotification(Notification, tag="interrupted"):
    """Kernel was interrupted by user (SIGINT/Ctrl+C)."""

    name: ClassVar[str] = "interrupted"


class CompletedRunNotification(Notification, tag="completed-run"):
    """Run of submitted cells and descendants completed."""

    name: ClassVar[str] = "completed-run"


class KernelCapabilitiesNotification(msgspec.Struct):
    """Kernel capabilities detected at startup.

    All fields auto-detected in __post_init__.

    Attributes:
        terminal: Terminal access (unavailable on Windows/Pyodide).
        pylsp: Python Language Server Protocol installed.
        ty: ty type checker installed.
        basedpyright: basedpyright type checker installed.
    """

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


class KernelReadyNotification(Notification, tag="kernel-ready"):
    """Kernel ready for execution. First notification sent at startup.

    Attributes:
        cell_ids: Cell IDs in order.
        codes: Source code for each cell.
        names: Cell names/titles.
        layout: Notebook layout config.
        configs: Per-cell configuration.
        resumed: Whether resumed from previous session.
        ui_values: Previous UI element values if resumed.
        last_executed_code: Last executed code per cell if resumed.
        last_execution_time: Last execution time per cell if resumed.
        app_config: Application configuration.
        kiosk: Whether running in kiosk mode.
        capabilities: Available kernel capabilities.
        auto_instantiated: Whether cells already executed (run mode).
    """

    name: ClassVar[str] = "kernel-ready"
    cell_ids: tuple[CellId_t, ...]
    codes: tuple[str, ...]
    names: tuple[str, ...]
    layout: Optional[LayoutConfig]
    configs: tuple[CellConfig, ...]
    resumed: bool
    ui_values: Optional[dict[str, JSONType]]
    last_executed_code: Optional[dict[CellId_t, str]]
    last_execution_time: Optional[dict[CellId_t, float]]
    app_config: _AppConfig
    kiosk: bool
    capabilities: KernelCapabilitiesNotification
    auto_instantiated: bool = False


class CompletionResultNotification(Notification, tag="completion-result"):
    """Code completion result from language server.

    Attributes:
        completion_id: Request ID this responds to.
        prefix_length: Length of prefix to replace.
        options: Completion options to display.
    """

    name: ClassVar[str] = "completion-result"
    completion_id: str
    prefix_length: int
    options: list[CompletionOption]


class AlertNotification(Notification, tag="alert"):
    """User-facing alert message.

    Attributes:
        title: Alert title.
        description: Alert body (may contain HTML).
        variant: Visual variant (e.g., "danger").
    """

    name: ClassVar[str] = "alert"
    title: str
    description: str
    variant: Optional[Literal["danger"]] = None


class MissingPackageAlertNotification(
    Notification, tag="missing-package-alert"
):
    """Alert for missing packages with install option.

    Attributes:
        packages: Missing package names.
        isolated: Whether in isolated environment.
    """

    name: ClassVar[str] = "missing-package-alert"
    packages: list[str]
    isolated: bool


# package name => installation status
PackageStatusType = dict[
    str, Literal["queued", "installing", "installed", "failed"]
]


class InstallingPackageAlertNotification(
    Notification, tag="installing-package-alert"
):
    """Package installation progress with streaming logs.

    Attributes:
        packages: Package name to status (queued/installing/installed/failed).
        logs: Optional streaming logs per package.
        log_status: Log stream status (append/start/done).
    """

    name: ClassVar[str] = "installing-package-alert"
    packages: PackageStatusType
    logs: Optional[dict[str, str]] = None  # package name -> log content
    log_status: Optional[Literal["append", "start", "done"]] = None


class ReconnectedNotification(Notification, tag="reconnected"):
    """WebSocket reconnection confirmed."""

    name: ClassVar[str] = "reconnected"


class StartupLogsNotification(Notification, tag="startup-logs"):
    """Streaming kernel startup logs.

    Attributes:
        content: Log content to display.
        status: Stream status (start/append/done).
    """

    name: ClassVar[str] = "startup-logs"
    content: str
    status: Literal["append", "start", "done"]


class BannerNotification(Notification, tag="banner"):
    """Persistent banner message at top of notebook.

    Attributes:
        title: Banner title.
        description: Banner body (may contain HTML).
        variant: Visual variant (e.g., "danger").
        action: Optional user action (e.g., "restart").
    """

    name: ClassVar[str] = "banner"
    title: str
    description: str
    variant: Optional[Literal["danger"]] = None
    action: Optional[Literal["restart"]] = None


class KernelStartupErrorNotification(Notification, tag="kernel-startup-error"):
    """Kernel failed to start.

    Attributes:
        error: Error message describing failure.
    """

    name: ClassVar[str] = "kernel-startup-error"
    error: str


class ReloadNotification(Notification, tag="reload"):
    """Instructs frontend to reload the page."""

    name: ClassVar[str] = "reload"


class VariableDeclarationNotification(msgspec.Struct):
    """Variable declaration and usage for dataflow graph.

    Attributes:
        name: Variable name.
        declared_by: Cell IDs that define this variable.
        used_by: Cell IDs that use this variable.
    """

    name: str
    declared_by: list[CellId_t]
    used_by: list[CellId_t]


class VariableValue(BaseStruct):
    """Variable value and type for variables panel.

    Attributes:
        name: Variable name.
        value: String representation of value.
        datatype: Data type as string.
    """

    name: str
    value: Optional[str]
    datatype: Optional[str]


class VariablesNotification(Notification, tag="variables"):
    """Variable dataflow graph.

    Attributes:
        variables: Variable declarations and usage.
    """

    name: ClassVar[str] = "variables"
    variables: list[VariableDeclarationNotification]


class VariableValuesNotification(Notification, tag="variable-values"):
    """Current variable values.

    Attributes:
        variables: Variables with current values and types.
    """

    name: ClassVar[str] = "variable-values"
    variables: list[VariableValue]


class DatasetsNotification(Notification, tag="datasets"):
    """Available datasets for data explorer.

    Attributes:
        tables: Available data tables/datasets.
        clear_channel: If set, clears tables from this channel first.
    """

    name: ClassVar[str] = "datasets"
    tables: list[DataTable]
    clear_channel: Optional[DataTableSource] = None


class SQLMetadata(msgspec.Struct, tag="sql-metadata"):
    """SQL database and schema metadata.

    Attributes:
        connection: Connection identifier.
        database: Database name.
        schema: Schema name.
    """

    connection: str
    database: str
    schema: str


class SQLTablePreviewNotification(Notification, tag="sql-table-preview"):
    """SQL table preview.

    Attributes:
        request_id: Request ID this responds to.
        metadata: Database and schema metadata.
        table: Table data (None if error).
        error: Error message if failed.
    """

    name: ClassVar[str] = "sql-table-preview"
    request_id: RequestId
    metadata: SQLMetadata
    table: Optional[DataTable]
    error: Optional[str] = None


class SQLTableListPreviewNotification(
    Notification, tag="sql-table-list-preview"
):
    """List of SQL tables in a schema.

    Attributes:
        request_id: Request ID this responds to.
        metadata: Database and schema metadata.
        tables: Tables in schema.
        error: Error message if failed.
    """

    name: ClassVar[str] = "sql-table-list-preview"
    request_id: RequestId
    metadata: SQLMetadata
    tables: list[DataTable] = msgspec.field(default_factory=list)
    error: Optional[str] = None


class ColumnPreview(msgspec.Struct):
    """Column preview with stats and visualization.

    Attributes:
        chart_spec: Vega-Lite chart spec.
        chart_code: Python code to generate chart.
        error: Error message if failed.
        missing_packages: Required but not installed packages.
        stats: Statistical summary.
    """

    chart_spec: Optional[str] = None
    chart_code: Optional[str] = None
    error: Optional[str] = None
    missing_packages: Optional[list[str]] = None
    stats: Optional[ColumnStats] = None


class DataColumnPreviewNotification(
    Notification, ColumnPreview, kw_only=True, tag="data-column-preview"
):
    """Data column preview with stats and visualization.

    Inherits all ColumnPreview attributes.

    Attributes:
        table_name: Table containing the column.
        column_name: Column being previewed.
    """

    name: ClassVar[str] = "data-column-preview"
    table_name: str
    column_name: str


class DataSourceConnectionsNotification(
    Notification, tag="data-source-connections"
):
    """Available data source connections for SQL cells.

    Attributes:
        connections: Available data source connections.
    """

    name: ClassVar[str] = "data-source-connections"
    connections: list[DataSourceConnection]


class ValidateSQLResultNotification(Notification, tag="validate-sql-result"):
    """SQL query validation result.

    Attributes:
        request_id: Request ID this responds to.
        parse_result: SQL parsing result.
        validate_result: Catalog validation result.
        error: Error message if failed.
    """

    name: ClassVar[str] = "validate-sql-result"
    request_id: RequestId
    parse_result: Optional[SqlParseResult] = None
    validate_result: Optional[SqlCatalogCheckResult] = None
    error: Optional[str] = None


class QueryParamsSetNotification(Notification, tag="query-params-set"):
    """Sets URL query parameter, replacing existing values.

    Attributes:
        key: Query parameter key.
        value: Value(s) to set.
    """

    name: ClassVar[str] = "query-params-set"
    key: str
    value: Union[str, list[str]]


class QueryParamsAppendNotification(Notification, tag="query-params-append"):
    """Appends value to URL query parameter.

    Attributes:
        key: Query parameter key.
        value: Value to append.
    """

    name: ClassVar[str] = "query-params-append"
    key: str
    value: str


class QueryParamsDeleteNotification(Notification, tag="query-params-delete"):
    """Deletes URL query parameter values.

    Attributes:
        key: Query parameter key.
        value: Specific value to delete. If None, deletes all values for key.
    """

    name: ClassVar[str] = "query-params-delete"
    key: str
    value: Optional[str]


class QueryParamsClearNotification(Notification, tag="query-params-clear"):
    """Clears all URL query parameters."""

    name: ClassVar[str] = "query-params-clear"


class FocusCellNotification(Notification, tag="focus-cell"):
    """Focuses a cell (kiosk mode).

    Attributes:
        cell_id: Cell to focus.
    """

    name: ClassVar[str] = "focus-cell"
    cell_id: CellId_t


class UpdateCellCodesNotification(Notification, tag="update-cell-codes"):
    """Updates cell code contents (kiosk mode).

    Attributes:
        cell_ids: Cells to update.
        codes: New code for each cell.
        code_is_stale: If True, code was not executed on backend (output may not match).
    """

    name: ClassVar[str] = "update-cell-codes"
    cell_ids: list[CellId_t]
    codes: list[str]
    code_is_stale: bool


class SecretKeysResultNotification(Notification, tag="secret-keys-result"):
    """Available secret keys from secret providers.

    Attributes:
        request_id: Request ID this responds to.
        secrets: Secret keys with provider info.
    """

    request_id: RequestId
    name: ClassVar[str] = "secret-keys-result"
    secrets: list[SecretKeysWithProvider]


class CacheClearedNotification(Notification, tag="cache-cleared"):
    """Execution cache cleared result.

    Attributes:
        bytes_freed: Bytes freed by clearing cache.
    """

    name: ClassVar[str] = "cache-cleared"
    bytes_freed: int


class CacheInfoNotification(Notification, tag="cache-info"):
    """Execution cache statistics.

    Attributes:
        hits: Cache hits.
        misses: Cache misses.
        time: Time spent on cache operations (seconds).
        disk_to_free: Disk space that could be freed (bytes).
        disk_total: Total disk space used (bytes).
    """

    name: ClassVar[str] = "cache-info"
    hits: int
    misses: int
    time: float
    disk_to_free: int
    disk_total: int


class UpdateCellIdsNotification(Notification, tag="update-cell-ids"):
    """Updates cell ordering in notebook.

    Attributes:
        cell_ids: Complete ordered list of cell IDs.
    """

    name: ClassVar[str] = "update-cell-ids"
    cell_ids: list[CellId_t]


class ListPackagesResultNotification(Notification, tag="list-packages-result"):
    """Result of a list packages request.

    Attributes:
        request_id: Request ID this responds to.
        packages: List of installed packages.
    """

    name: ClassVar[str] = "list-packages-result"
    request_id: RequestId
    packages: list[PackageDescription]


class PackagesDependencyTreeResultNotification(
    Notification, tag="packages-dependency-tree-result"
):
    """Result of a dependency tree request.

    Attributes:
        request_id: Request ID this responds to.
        tree: Dependency tree (None if error or not available).
    """

    name: ClassVar[str] = "packages-dependency-tree-result"
    request_id: RequestId
    tree: Optional[DependencyTreeNode]


NotificationMessage = Union[
    # Cell operations
    CellNotification,
    FunctionCallResultNotification,
    UIElementMessageNotification,
    RemoveUIElementsNotification,
    # Notebook lifecycle
    ReloadNotification,
    ReconnectedNotification,
    InterruptedNotification,
    CompletedRunNotification,
    KernelReadyNotification,
    # Editor
    CompletionResultNotification,
    # Alerts
    AlertNotification,
    BannerNotification,
    MissingPackageAlertNotification,
    InstallingPackageAlertNotification,
    StartupLogsNotification,
    KernelStartupErrorNotification,
    # Variables
    VariablesNotification,
    VariableValuesNotification,
    # Query params
    QueryParamsSetNotification,
    QueryParamsAppendNotification,
    QueryParamsDeleteNotification,
    QueryParamsClearNotification,
    # Data/SQL
    DatasetsNotification,
    DataColumnPreviewNotification,
    SQLTablePreviewNotification,
    SQLTableListPreviewNotification,
    DataSourceConnectionsNotification,
    ValidateSQLResultNotification,
    # Secrets
    SecretKeysResultNotification,
    # Cache
    CacheClearedNotification,
    CacheInfoNotification,
    # Kiosk
    FocusCellNotification,
    UpdateCellCodesNotification,
    UpdateCellIdsNotification,
    # Packages
    ListPackagesResultNotification,
    PackagesDependencyTreeResultNotification,
]
