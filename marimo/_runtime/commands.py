# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import re
import time
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
    TypeVar,
    Union,
)
from uuid import uuid4

import msgspec

from marimo import _loggers
from marimo._ast.app_config import _AppConfig
from marimo._config.config import MarimoConfig
from marimo._data.models import DataTableSource
from marimo._types.ids import CellId_t, RequestId, UIElementId, WidgetModelId

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from collections.abc import Iterator

    from starlette.datastructures import URL
    from starlette.requests import HTTPConnection


def kebab_case(name: str) -> str:
    """Convert PascalCase to kebab-case.

    Removes 'Command' suffix and converts to kebab-case for discriminated union tags.
    Handles acronyms by keeping consecutive uppercase letters together.
    """
    if name.endswith("Command"):
        name = name[:-7]  # Remove 'Command' (7 characters)
    if not name:
        return name
    # Insert hyphens before uppercase letters that follow lowercase letters
    # or before an uppercase letter followed by a lowercase letter (handling acronyms)
    # This groups consecutive uppercase letters together (e.g., "SQL" -> "sql")
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1-\2", name)
    s2 = re.sub("([a-z0-9])([A-Z])", r"\1-\2", s1)
    return s2.lower()


class Command(
    msgspec.Struct, rename="camel", tag_field="type", tag=kebab_case
):
    """Base class for runtime commands.

    Discriminated union base using msgspec for serialization. Command subclasses
    are automatically tagged with their kebab-case name and serialized with
    camelCase field names. The "type" tag discriminates between commands during
    deserialization for type-safe routing.
    """

    pass


T = TypeVar("T")
ListOrValue = Union[T, list[T]]
SerializedQueryParams = dict[str, ListOrValue[str]]
Primitive = Union[str, bool, int, float]
SerializedCLIArgs = dict[str, ListOrValue[Primitive]]


@dataclass
class HTTPRequest(Mapping[str, Any]):
    """Serializable HTTP request representation.

    Mimics Starlette/FastAPI Request but is pickle-able and contains only a safe
    subset of data. Excludes session and auth to prevent exposing sensitive data.

    Attributes:
        url: Serialized URL with path, port, scheme, netloc, query, hostname.
        base_url: Serialized base URL.
        headers: Request headers (marimo-specific headers excluded).
        query_params: Query parameters mapped to lists of values.
        path_params: Path parameters from the URL route.
        cookies: Request cookies.
        meta: User-defined storage for custom data.
        user: User info from authentication middleware (e.g., is_authenticated, username).
    """

    url: dict[str, Any]  # Serialized URL
    base_url: dict[str, Any]  # Serialized URL
    headers: dict[str, str]  # Raw headers
    query_params: dict[str, list[str]]  # Raw query params
    path_params: dict[str, Any]
    cookies: dict[str, str]
    meta: dict[str, Any]  # User-defined storage
    user: Any

    # We don't include session or auth because they may contain
    # information that the app author does not want to expose.

    # session: dict[str, Any]
    # auth: Any

    def __getitem__(self, key: str) -> Any:
        return self.__dict__[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.__dict__)

    def __len__(self) -> int:
        return len(self.__dict__)

    def _display_(self) -> Any:
        try:
            import dataclasses

            return dataclasses.asdict(self)
        except TypeError:
            return self.__dict__

    def __repr__(self) -> str:
        return f"HTTPRequest(path={self.url['path']}, params={len(self.query_params)})"

    @staticmethod
    def from_request(request: HTTPConnection) -> HTTPRequest:
        def _url_to_dict(url: URL) -> dict[str, Any]:
            return {
                "path": url.path,
                "port": url.port,
                "scheme": url.scheme,
                "netloc": url.netloc,
                "query": url.query,
                "hostname": url.hostname,
            }

        # Convert URL to dict
        url_dict = _url_to_dict(request.url)

        # Convert base_url to dict
        base_url_dict = _url_to_dict(request.base_url)

        # Convert query params to dict[str, list[str]]
        query_params: dict[str, list[str]] = defaultdict(list)
        for k, v in request.query_params.multi_items():
            query_params[k].append(str(v))

        # Convert headers to dict, remove all marimo-specific headers
        headers: dict[str, str] = {}
        for k, v in request.headers.items():
            if not k.startswith(("marimo", "x-marimo")):
                headers[k] = v

        return HTTPRequest(
            url=url_dict,
            base_url=base_url_dict,
            headers=headers,
            query_params=query_params,
            path_params=request.path_params,
            cookies=request.cookies,
            user=request["user"] if "user" in request else {},
            meta=request["meta"] if "meta" in request else {},
            # Left out for now. This may contain information that the app author
            # does not want to expose.
            # session=request.session if "session" in request else {},
            # auth=request.auth if "auth" in request else {},
        )


class DebugCellCommand(Command):
    """Enter debugger mode for a cell.

    Starts the Python debugger (pdb) for the specified cell.

    Attributes:
        cell_id: Cell to debug.
        request: HTTP request context if available.
    """

    cell_id: CellId_t
    # incoming request, e.g. from Starlette or FastAPI
    request: Optional[HTTPRequest] = None

    def __repr__(self) -> str:
        return f"DebugCellCommand(cell={self.cell_id})"


class ExecuteCellCommand(Command):
    """Execute a single cell.

    Executes a cell with the provided code. Dependent cells may be
    re-executed based on the reactive execution mode.

    Attributes:
        cell_id: Cell to execute.
        code: Python code to execute.
        request: HTTP request context if available.
        timestamp: Unix timestamp when command was created.
    """

    cell_id: CellId_t
    code: str
    # incoming request, e.g. from Starlette or FastAPI
    request: Optional[HTTPRequest] = None
    timestamp: float = msgspec.field(default_factory=time.time)

    def __repr__(self) -> str:
        preview = self.code[:10].replace("\n", " ")
        return (
            f"ExecuteCellCommand(cell={self.cell_id}, code_preview={preview})"
        )


class ExecuteStaleCellsCommand(Command):
    """Execute all stale cells.

    Cells become stale when their dependencies change but haven't been
    re-executed yet. Brings the notebook to a consistent state.

    Attributes:
        request: HTTP request context if available.
    """

    request: Optional[HTTPRequest] = None


class ExecuteCellsCommand(Command):
    """Execute multiple cells in a batch.

    Executes multiple cells with their corresponding code. The kernel manages
    dependency tracking and reactive execution.

    Attributes:
        cell_ids: Cells to execute.
        codes: Python code for each cell. Must match length of cell_ids.
        request: HTTP request context if available.
        timestamp: Unix timestamp when command was created.
    """

    # ids of cells to run
    cell_ids: list[CellId_t]
    # code to register/run for each cell
    codes: list[str]
    # incoming request, e.g. from Starlette or FastAPI
    request: Optional[HTTPRequest] = None
    # time at which the request was received
    timestamp: float = msgspec.field(default_factory=time.time)

    def __repr__(self) -> str:
        return f"ExecuteCellsCommand(cells={len(self.cell_ids)})"

    @property
    def execution_requests(self) -> list[ExecuteCellCommand]:
        """Convert to individual cell execution commands.

        Returns:
            List of ExecuteCellCommand instances, one per cell.
        """
        return [
            ExecuteCellCommand(
                cell_id=cell_id,
                code=code,
                request=self.request,
                timestamp=self.timestamp,
            )
            for cell_id, code in zip(self.cell_ids, self.codes)
        ]

    def __post_init__(self) -> None:
        assert len(self.cell_ids) == len(self.codes), (
            "Mismatched cell_ids and codes"
        )


class SyncGraphCommand(Command):
    """Synchronize the kernel graph with file manager state.

    Used when the notebook file changes externally (e.g., file reload or version control).
    Updates changed cells, deletes removed cells, and optionally executes modified cells.

    Attributes:
        cells: All cells known to file manager, mapping cell_id to code.
        run_ids: Cells to execute or update.
        delete_ids: Cells to delete from the graph.
        timestamp: Unix timestamp when command was created.
    """

    # ids of cells known to filemanager
    cells: dict[CellId_t, str]
    # From the list of ALL cells that filemanager knows about,
    # denote what should be run/ updated or deleted.
    run_ids: list[CellId_t]
    delete_ids: list[CellId_t]
    # time at which the request was received
    timestamp: float = msgspec.field(default_factory=time.time)

    @property
    def execution_requests(self) -> list[ExecuteCellCommand]:
        """Convert run_ids to individual cell execution commands.

        Returns:
            List of ExecuteCellCommand instances for cells to execute.
        """
        return [
            ExecuteCellCommand(
                cell_id=cell_id,
                code=self.cells[cell_id],
                request=None,
                timestamp=self.timestamp,
            )
            for cell_id in self.run_ids
        ]


class ExecuteScratchpadCommand(Command):
    """Execute code in the scratchpad.

    The scratchpad is a temporary execution environment that doesn't affect
    the notebook's cells or dependencies. Runs in an isolated cell with a copy
    of the global namespace, useful for experimentation.

    Attributes:
        code: Python code to execute.
        request: HTTP request context if available.
    """

    code: str
    # incoming request, e.g. from Starlette or FastAPI
    request: Optional[HTTPRequest] = None


class RenameNotebookCommand(Command):
    """Rename or move the notebook file.

    Updates the notebook's filename in the kernel metadata.

    Attributes:
        filename: New filename or path for the notebook.
    """

    filename: str


class UpdateUIElementCommand(Command):
    """Update UI element values.

    Triggered when users interact with UI elements (sliders, inputs, dropdowns, etc.).
    Updates element values and re-executes dependent cells.

    Attributes:
        object_ids: UI elements to update.
        values: New values for the elements. Must match length of object_ids.
        request: HTTP request context if available.
        token: Unique request identifier for deduplication.
    """

    object_ids: list[UIElementId]
    values: list[Any]
    # Incoming request, e.g. from Starlette or FastAPI
    request: Optional[HTTPRequest] = None
    # uniquely identifies the request
    token: str = msgspec.field(default_factory=lambda: str(uuid4()))

    def __repr__(self) -> str:
        return f"UpdateUIElementCommand(n_elements={len(self.object_ids)}, token={self.token})"

    def __post_init__(self) -> None:
        assert len(self.object_ids) == len(self.values), (
            "Mismatched object_ids and values"
        )
        # Empty token is not valid (but let's not fail)
        if not self.token:
            LOGGER.warning(
                "UpdateUIElementRequest with empty token is invalid"
            )

    @staticmethod
    def from_ids_and_values(
        ids_and_values: list[tuple[UIElementId, Any]],
        request: Optional[HTTPRequest] = None,
    ) -> UpdateUIElementCommand:
        """Create command from list of (id, value) tuples.

        Args:
            ids_and_values: UI element IDs and their new values.
            request: HTTP request context if available.

        Returns:
            UpdateUIElementCommand instance.
        """
        if not ids_and_values:
            return UpdateUIElementCommand(
                object_ids=[], values=[], request=request
            )
        object_ids, values = zip(*ids_and_values)
        return UpdateUIElementCommand(
            object_ids=list(object_ids),
            values=list(values),
            request=request,
        )

    @property
    def ids_and_values(self) -> list[tuple[UIElementId, Any]]:
        """UI element IDs and values as tuples.

        Returns:
            List of (id, value) tuples.
        """
        return list(zip(self.object_ids, self.values))


class InvokeFunctionCommand(Command):
    """Invoke a function from a UI element.

    Called when a UI element needs to invoke a Python function.

    Attributes:
        function_call_id: Unique identifier for this call.
        namespace: Namespace where the function is registered.
        function_name: Function to invoke.
        args: Keyword arguments for the function.
    """

    function_call_id: RequestId
    namespace: str
    function_name: str
    args: dict[str, Any]

    def __repr__(self) -> str:
        return f"InvokeFunctionCommand(id={self.function_call_id}, fn={self.namespace}.{self.function_name})"


class AppMetadata(msgspec.Struct, rename="camel"):
    """Application runtime metadata.

    Attributes:
        query_params: Query parameters from the URL when running as a web app.
        cli_args: Command-line arguments passed when starting the app.
        app_config: Application-level configuration.
        argv: Full argument vector if available.
        filename: Path to the notebook file.
    """

    query_params: SerializedQueryParams
    cli_args: SerializedCLIArgs
    app_config: _AppConfig
    argv: Union[list[str], None] = None

    filename: Optional[str] = None


class UpdateCellConfigCommand(Command):
    """Update cell configuration.

    Updates cell-level settings like disabled state, hide code, etc.

    Attributes:
        configs: Cell IDs mapped to their config updates. Each config dict
                 can contain partial updates.
    """

    # Map from Cell ID to (possibly partial) CellConfig
    configs: dict[CellId_t, dict[str, Any]]


class UpdateUserConfigCommand(Command):
    """Update user configuration.

    Updates global marimo configuration (runtime settings, display options, editor preferences).

    Attributes:
        config: Complete user configuration.
    """

    # MarimoConfig TypedDict
    config: MarimoConfig

    def __repr__(self) -> str:
        return "UpdateUserConfigCommand(config=...)"


class CreateNotebookCommand(Command):
    """Instantiate and initialize a notebook.

    Sent when a notebook is first loaded. Contains all cells and initial UI element values.

    Attributes:
        execution_requests: ExecuteCellCommand for each notebook cell.
        set_ui_element_value_request: Initial UI element values.
        auto_run: Whether to automatically execute cells on instantiation.
        request: HTTP request context if available.
    """

    execution_requests: tuple[ExecuteCellCommand, ...]
    set_ui_element_value_request: UpdateUIElementCommand
    auto_run: bool
    request: Optional[HTTPRequest] = None


class DeleteCellCommand(Command):
    """Delete a cell from the notebook.

    Removes cell from the dependency graph and cleans up its variables.
    Dependent cells may become stale.

    Attributes:
        cell_id: Cell to delete.
    """

    cell_id: CellId_t


class StopKernelCommand(Command):
    """Stop kernel execution.

    Signals the kernel to stop processing and shut down gracefully.
    Used when closing a notebook or terminating a session.
    """

    pass


class CodeCompletionCommand(Command):
    """Request code completion suggestions.

    Sent when the user requests autocomplete. Provides code context up to
    the cursor position for the language server.

    Attributes:
        id: Unique identifier for this request.
        document: Source code up to the cursor position.
        cell_id: Cell where completion is requested.
    """

    id: RequestId
    document: str
    """Source code found in the cell up to the cursor position."""
    cell_id: CellId_t

    def __repr__(self) -> str:
        return f"CodeCompletionCommand(id={self.id}, cell={self.cell_id})"


class InstallPackagesCommand(Command):
    """Install Python packages.

    Installs missing packages using the specified package manager. Triggered
    automatically on import errors or manually by the user.

    Attributes:
        manager: Package manager to use ('pip', 'conda', 'uv', etc.).
        versions: Package names mapped to version specifiers. Empty version
                  means install latest.
    """

    # TODO: index URL (index/channel/...)
    manager: str

    # Map from package name to desired version
    # If the package name is not in the map, the latest version
    # will be installed
    versions: dict[str, str]


class PreviewDatasetColumnCommand(Command):
    """Preview a dataset column.

    Retrieves and displays data from a single column (dataframe or SQL table).
    Used by the data explorer UI.

    Attributes:
        source_type: Data source type ('dataframe', 'sql', etc.).
        source: Source identifier (connection string or variable name).
        table_name: Table or dataframe variable name.
        column_name: Column to preview.
        fully_qualified_table_name: Full database.schema.table name for SQL.
    """

    # The source type of the dataset
    source_type: DataTableSource
    # The source of the dataset
    source: str
    # The name of the dataset
    # If this is a Python dataframe, this is the variable name
    # If this is an SQL table, this is the table name
    table_name: str
    # The name of the column
    column_name: str
    # The fully qualified name of the table
    # This is the database.schema.table name
    fully_qualified_table_name: Optional[str] = None


class PreviewSQLTableCommand(Command):
    """Preview SQL table details.

    Retrieves metadata and sample data for a table. Used by the SQL editor
    and data explorer.

    Attributes:
        request_id: Unique identifier for this request.
        engine: SQL engine ('postgresql', 'mysql', 'duckdb', etc.).
        database: Database containing the table.
        schema: Schema containing the table.
        table_name: Table to preview.
    """

    request_id: RequestId
    engine: str
    database: str
    schema: str
    table_name: str


class ListSQLTablesCommand(Command):
    """List tables in an SQL schema.

    Retrieves names of all tables and views in a schema. Used by the SQL
    editor for table selection.

    Attributes:
        request_id: Unique identifier for this request.
        engine: SQL engine ('postgresql', 'mysql', 'duckdb', etc.).
        database: Database to query.
        schema: Schema to list tables from.
    """

    request_id: RequestId
    engine: str
    database: str
    schema: str


class ListDataSourceConnectionCommand(Command):
    """List data source schemas.

    Retrieves available schemas for a data source engine.

    Attributes:
        engine: Data source engine identifier.
    """

    engine: str


class ValidateSQLCommand(Command):
    """Validate an SQL query.

    Checks if an SQL query is valid by parsing against a dialect (no DB connection)
    or validating against an actual database.

    Attributes:
        request_id: Unique identifier for this request.
        query: SQL query to validate.
        only_parse: If True, only parse using dialect. If False, validate against DB.
        engine: SQL engine (required if only_parse is False).
        dialect: SQL dialect for parsing (required if only_parse is True).
    """

    request_id: RequestId
    query: str
    # Whether to only parse the query or validate against the database
    # Parsing is done without a DB connection and uses dialect, whereas validation requires a connection
    only_parse: bool
    engine: Optional[str] = None
    dialect: Optional[str] = None


class ListSecretKeysCommand(Command):
    """List available secret keys.

    Retrieves secret names without exposing values.

    Attributes:
        request_id: Unique identifier for this request.
    """

    request_id: RequestId


class ModelMessage(msgspec.Struct, rename="camel"):
    """Widget model state update message.

    State changes for anywidget models, including state dict and binary buffer paths.

    Attributes:
        state: Model state updates.
        buffer_paths: Paths within state dict pointing to binary buffers.
    """

    state: dict[str, Any]
    buffer_paths: list[list[Union[str, int]]]


class UpdateWidgetModelCommand(Command):
    """Update anywidget model state.

    Updates widget model state for bidirectional Python-JavaScript communication.

    Attributes:
        model_id: Widget model identifier.
        message: Model message with state updates and buffer paths.
        buffers: Base64-encoded binary buffers referenced by buffer_paths.
    """

    model_id: WidgetModelId
    message: ModelMessage
    buffers: Optional[list[str]] = None


class RefreshSecretsCommand(Command):
    """Refresh secrets from the secrets store.

    Reloads secrets from the provider without restarting the kernel.
    """

    pass


class ClearCacheCommand(Command):
    """Clear all cached data.

    Clears all cache contexts, freeing memory and disk space.
    Affects all cells using the @cache decorator.
    """

    pass


class GetCacheInfoCommand(Command):
    """Retrieve cache statistics.

    Collects cache usage info across all contexts (hit/miss rates, time saved, disk usage).
    """

    pass


CommandMessage = Union[
    # Notebook operations
    CreateNotebookCommand,
    RenameNotebookCommand,
    CodeCompletionCommand,
    # Cell execution and management
    ExecuteCellsCommand,
    ExecuteScratchpadCommand,
    ExecuteStaleCellsCommand,
    DebugCellCommand,
    DeleteCellCommand,
    SyncGraphCommand,
    UpdateCellConfigCommand,
    # Package management
    InstallPackagesCommand,
    # UI element and widget model operations
    UpdateUIElementCommand,
    UpdateWidgetModelCommand,
    InvokeFunctionCommand,
    # User/configuration operations
    UpdateUserConfigCommand,
    # Data SQL operations
    PreviewDatasetColumnCommand,
    PreviewSQLTableCommand,
    ListSQLTablesCommand,
    ValidateSQLCommand,
    ListDataSourceConnectionCommand,
    # Secrets management
    ListSecretKeysCommand,
    RefreshSecretsCommand,
    # Cache management
    ClearCacheCommand,
    GetCacheInfoCommand,
    # Kernel operations
    StopKernelCommand,
]
"""Union of all command messages.

All commands that can be sent to the kernel.

"""
