# Copyright 2026 Marimo. All rights reserved.
"""Message Types

Messages that the kernel sends to the frontend.
"""

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
from marimo._secrets.models import SecretKeysWithProvider
from marimo._sql.parse import SqlCatalogCheckResult, SqlParseResult
from marimo._types.ids import CellId_t, RequestId, WidgetModelId
from marimo._utils.msgspec_basestruct import BaseStruct
from marimo._utils.platform import is_pyodide, is_windows

LOGGER = loggers.marimo_logger()


class Notification(msgspec.Struct, tag_field="op"):
    name: ClassVar[str]


class CellNotification(Notification, tag="cell-op"):
    """Op to transition a cell.

    A CellNotification's data has some optional fields:

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


class HumanReadableStatus(msgspec.Struct):
    """Human-readable status."""

    code: Literal["ok", "error"]
    title: Union[str, None] = None
    message: Union[str, None] = None


class FunctionCallResultNotification(Notification, tag="function-call-result"):
    """Result of calling a function."""

    name: ClassVar[str] = "function-call-result"

    function_call_id: RequestId
    return_value: JSONType
    status: HumanReadableStatus


class RemoveUIElementsNotification(Notification, tag="remove-ui-elements"):
    """Invalidate UI elements for a given cell."""

    name: ClassVar[str] = "remove-ui-elements"
    cell_id: CellId_t


class UIElementMessageNotification(
    Notification, tag="send-ui-element-message"
):
    """Send a message to a UI element."""

    name: ClassVar[str] = "send-ui-element-message"
    ui_element: Optional[str]
    model_id: Optional[WidgetModelId]
    message: dict[str, Any]
    buffers: Optional[list[bytes]] = None


class InterruptedNotification(Notification, tag="interrupted"):
    """Written when the kernel is interrupted by the user."""

    name: ClassVar[str] = "interrupted"


class CompletedRunNotification(Notification, tag="completed-run"):
    """Written on run completion (of submitted cells and their descendants."""

    name: ClassVar[str] = "completed-run"


class KernelCapabilitiesNotification(msgspec.Struct):
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
    capabilities: KernelCapabilitiesNotification
    # Whether the kernel has already been instantiated server-side (e.g. run mode)
    # If True, the frontend does not need to instantiate the app.
    auto_instantiated: bool = False


class CompletionResultNotification(Notification, tag="completion-result"):
    """Code completion result."""

    name: ClassVar[str] = "completion-result"
    completion_id: str
    prefix_length: int
    options: list[CompletionOption]


class AlertNotification(Notification, tag="alert"):
    name: ClassVar[str] = "alert"
    title: str
    # description may be HTML
    description: str
    variant: Optional[Literal["danger"]] = None


class MissingPackageAlertNotification(
    Notification, tag="missing-package-alert"
):
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
    name: ClassVar[str] = "installing-package-alert"
    packages: PackageStatusType
    # Optional fields for streaming logs per package
    logs: Optional[dict[str, str]] = None  # package name -> log content
    log_status: Optional[Literal["append", "start", "done"]] = None


class ReconnectedNotification(Notification, tag="reconnected"):
    name: ClassVar[str] = "reconnected"


class StartupLogsNotification(Notification, tag="startup-logs"):
    name: ClassVar[str] = "startup-logs"
    content: str
    status: Literal["append", "start", "done"]


class BannerNotification(Notification, tag="banner"):
    name: ClassVar[str] = "banner"
    title: str
    # description may be HTML
    description: str
    variant: Optional[Literal["danger"]] = None
    action: Optional[Literal["restart"]] = None


class ReloadNotification(Notification, tag="reload"):
    name: ClassVar[str] = "reload"


class VariableDeclarationNotification(msgspec.Struct):
    name: str
    declared_by: list[CellId_t]
    used_by: list[CellId_t]


class VariableValue(BaseStruct):
    name: str
    value: Optional[str]
    datatype: Optional[str]


class VariablesNotification(Notification, tag="variables"):
    """List of variable declarations."""

    name: ClassVar[str] = "variables"
    variables: list[VariableDeclarationNotification]


class VariableValuesNotification(Notification, tag="variable-values"):
    """List of variables and their types/values."""

    name: ClassVar[str] = "variable-values"
    variables: list[VariableValue]


class DatasetsNotification(Notification, tag="datasets"):
    """List of datasets."""

    name: ClassVar[str] = "datasets"
    tables: list[DataTable]
    clear_channel: Optional[DataTableSource] = None


class SQLMetadata(msgspec.Struct, tag="sql-metadata"):
    """Metadata for a SQL database."""

    connection: str
    database: str
    schema: str


class SQLTablePreviewNotification(Notification, tag="sql-table-preview"):
    """Preview of a table in a SQL database."""

    name: ClassVar[str] = "sql-table-preview"
    request_id: RequestId
    metadata: SQLMetadata
    table: Optional[DataTable]
    error: Optional[str] = None


class SQLTableListPreviewNotification(
    Notification, tag="sql-table-list-preview"
):
    """Preview of a list of tables in a schema."""

    name: ClassVar[str] = "sql-table-list-preview"
    request_id: RequestId
    metadata: SQLMetadata
    tables: list[DataTable] = msgspec.field(default_factory=list)
    error: Optional[str] = None


class ColumnPreview(msgspec.Struct):
    chart_spec: Optional[str] = None
    chart_code: Optional[str] = None
    error: Optional[str] = None
    missing_packages: Optional[list[str]] = None
    stats: Optional[ColumnStats] = None


class DataColumnPreviewNotification(
    Notification, ColumnPreview, kw_only=True, tag="data-column-preview"
):
    """Preview of a column in a dataset."""

    name: ClassVar[str] = "data-column-preview"
    table_name: str
    column_name: str


class DataSourceConnectionsNotification(
    Notification, tag="data-source-connections"
):
    name: ClassVar[str] = "data-source-connections"
    connections: list[DataSourceConnection]


class ValidateSQLResultNotification(Notification, tag="validate-sql-result"):
    name: ClassVar[str] = "validate-sql-result"
    request_id: RequestId
    parse_result: Optional[SqlParseResult] = None
    validate_result: Optional[SqlCatalogCheckResult] = None
    error: Optional[str] = None


class QueryParamsSetNotification(Notification, tag="query-params-set"):
    """Set query parameters."""

    name: ClassVar[str] = "query-params-set"
    key: str
    value: Union[str, list[str]]


class QueryParamsAppendNotification(Notification, tag="query-params-append"):
    name: ClassVar[str] = "query-params-append"
    key: str
    value: str


class QueryParamsDeleteNotification(Notification, tag="query-params-delete"):
    name: ClassVar[str] = "query-params-delete"
    key: str
    # If value is None, delete all values for the key
    # If a value is provided, only that value is deleted
    value: Optional[str]


class QueryParamsClearNotification(Notification, tag="query-params-clear"):
    # Clear all query parameters
    name: ClassVar[str] = "query-params-clear"


class FocusCellNotification(Notification, tag="focus-cell"):
    name: ClassVar[str] = "focus-cell"
    cell_id: CellId_t


class UpdateCellCodesNotification(Notification, tag="update-cell-codes"):
    name: ClassVar[str] = "update-cell-codes"
    cell_ids: list[CellId_t]
    codes: list[str]
    # If true, this means the code was not run on the backend when updating
    # the cell codes.
    code_is_stale: bool


class SecretKeysResultNotification(Notification, tag="secret-keys-result"):
    """Result of listing secret keys."""

    request_id: RequestId
    name: ClassVar[str] = "secret-keys-result"
    secrets: list[SecretKeysWithProvider]


class CacheClearedNotification(Notification, tag="cache-cleared"):
    """Result of clearing cache."""

    name: ClassVar[str] = "cache-cleared"
    bytes_freed: int


class CacheInfoNotification(Notification, tag="cache-info"):
    """Cache statistics information."""

    name: ClassVar[str] = "cache-info"
    hits: int
    misses: int
    time: float
    disk_to_free: int
    disk_total: int


class UpdateCellIdsNotification(Notification, tag="update-cell-ids"):
    """
    Update the cell ID ordering of the cells in the notebook.

    Right now we send the entire list of cell IDs,
    but in the future we might want to send change-deltas.
    """

    name: ClassVar[str] = "update-cell-ids"
    cell_ids: list[CellId_t]


NotificationMessage = Union[
    # Cell notifications
    CellNotification,
    FunctionCallResultNotification,
    UIElementMessageNotification,
    RemoveUIElementsNotification,
    # Notebook operations
    ReloadNotification,
    ReconnectedNotification,
    InterruptedNotification,
    CompletedRunNotification,
    KernelReadyNotification,
    # Editor operations
    CompletionResultNotification,
    # Alerts
    AlertNotification,
    BannerNotification,
    MissingPackageAlertNotification,
    InstallingPackageAlertNotification,
    StartupLogsNotification,
    # Variables
    VariablesNotification,
    VariableValuesNotification,
    # Query params
    QueryParamsSetNotification,
    QueryParamsAppendNotification,
    QueryParamsDeleteNotification,
    QueryParamsClearNotification,
    # Datasets
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
    # Kiosk specific
    FocusCellNotification,
    UpdateCellCodesNotification,
    UpdateCellIdsNotification,
]
