# Copyright 2024 Marimo. All rights reserved.
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
    pass


T = TypeVar("T")
ListOrValue = Union[T, list[T]]
SerializedQueryParams = dict[str, ListOrValue[str]]
Primitive = Union[str, bool, int, float]
SerializedCLIArgs = dict[str, ListOrValue[Primitive]]


@dataclass
class HTTPRequest(Mapping[str, Any]):
    """
    A class that mimics the Request object from Starlette or FastAPI.

    It is a subset and pickle-able version of the Request object.
    """

    url: dict[str, Any]  # Serialized URL
    base_url: dict[str, Any]  # Serialized URL
    headers: dict[str, str]  # Raw headers
    query_params: dict[str, list[str]]  # Raw query params
    path_params: dict[str, Any]
    cookies: dict[str, str]
    meta: dict[str, Any]
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
    cell_id: CellId_t
    # incoming request, e.g. from Starlette or FastAPI
    request: Optional[HTTPRequest] = None

    def __repr__(self) -> str:
        return f"DebugCellCommand(cell={self.cell_id})"


class ExecuteCellCommand(Command):
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
    request: Optional[HTTPRequest] = None


class ExecuteCellsCommand(Command):
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
    code: str
    # incoming request, e.g. from Starlette or FastAPI
    request: Optional[HTTPRequest] = None


class RenameNotebookCommand(Command):
    filename: str


class UpdateUIElementCommand(Command):
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
        return list(zip(self.object_ids, self.values))


class InvokeFunctionCommand(Command):
    function_call_id: RequestId
    namespace: str
    function_name: str
    args: dict[str, Any]

    def __repr__(self) -> str:
        return f"InvokeFunctionCommand(id={self.function_call_id}, fn={self.namespace}.{self.function_name})"


class AppMetadata(Command):
    """Hold metadata about the app, like its filename."""

    query_params: SerializedQueryParams
    cli_args: SerializedCLIArgs
    app_config: _AppConfig
    argv: Union[list[str], None] = None

    filename: Optional[str] = None


class UpdateCellConfigCommand(Command):
    # Map from Cell ID to (possibly partial) CellConfig
    configs: dict[CellId_t, dict[str, Any]]


class UpdateUserConfigCommand(Command):
    # MarimoConfig TypedDict
    config: MarimoConfig

    def __repr__(self) -> str:
        return "UpdateUserConfigCommand(config=...)"


class CreateNotebookCommand(Command):
    execution_requests: tuple[ExecuteCellCommand, ...]
    set_ui_element_value_request: UpdateUIElementCommand
    auto_run: bool
    request: Optional[HTTPRequest] = None


class DeleteCellCommand(Command):
    cell_id: CellId_t


class StopKernelCommand(Command):
    pass


class CodeCompletionCommand(Command):
    id: RequestId
    document: str
    """Source code found in the cell up to the cursor position."""
    cell_id: CellId_t

    def __repr__(self) -> str:
        return f"CodeCompletionCommand(id={self.id}, cell={self.cell_id})"


class InstallPackagesCommand(Command):
    # TODO: index URL (index/channel/...)
    manager: str

    # Map from package name to desired version
    # If the package name is not in the map, the latest version
    # will be installed
    versions: dict[str, str]


class PreviewDatasetColumnCommand(Command):
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
    """Preview table details in an SQL database"""

    request_id: RequestId
    engine: str
    database: str
    schema: str
    table_name: str


class ListSQLTablesCommand(Command):
    """Preview list of tables in an SQL schema"""

    request_id: RequestId
    engine: str
    database: str
    schema: str


class ListDataSourceConnectionCommand(Command):
    """Fetch a datasource connection"""

    engine: str


class ValidateSQLCommand(Command):
    """Validate an SQL query against the engine"""

    request_id: RequestId
    query: str
    # Whether to only parse the query or validate against the database
    # Parsing is done without a DB connection and uses dialect, whereas validation requires a connection
    only_parse: bool
    engine: Optional[str] = None
    dialect: Optional[str] = None


class ListSecretKeysCommand(Command):
    request_id: RequestId


class ModelMessage(msgspec.Struct, rename="camel"):
    state: dict[str, Any]
    buffer_paths: list[list[Union[str, int]]]


class UpdateWidgetModelCommand(Command):
    model_id: WidgetModelId
    message: ModelMessage
    buffers: Optional[list[str]] = None


class RefreshSecretsCommand(Command):
    pass


class ClearCacheCommand(Command):
    pass


class GetCacheInfoCommand(Command):
    pass


CommandMessage = Union[
    # Notebook operations
    CreateNotebookCommand,
    RenameNotebookCommand,
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
