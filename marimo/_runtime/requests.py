# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Iterator, Mapping
from dataclasses import asdict, dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
    TypeVar,
    Union,
)
from uuid import uuid4

from marimo._ast.app_config import _AppConfig
from marimo._config.config import MarimoConfig
from marimo._data.models import DataTableSource
from marimo._types.ids import CellId_t, RequestId, UIElementId, WidgetModelId

if TYPE_CHECKING:
    from starlette.datastructures import URL
    from starlette.requests import HTTPConnection


CompletionRequestId = str

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
            return asdict(self)
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


@dataclass
class PdbRequest:
    cell_id: CellId_t
    # incoming request, e.g. from Starlette or FastAPI
    request: Optional[HTTPRequest] = None

    def __repr__(self) -> str:
        return f"PdbRequest(cell={self.cell_id})"


@dataclass
class ExecutionRequest:
    cell_id: CellId_t
    code: str
    # incoming request, e.g. from Starlette or FastAPI
    request: Optional[HTTPRequest] = None
    timestamp: float = field(default_factory=time.time)

    def __repr__(self) -> str:
        preview = self.code[:10].replace("\n", " ")
        return f"ExecutionRequest(cell={self.cell_id}, code_preview={preview})"


@dataclass
class ExecuteStaleRequest:
    request: Optional[HTTPRequest] = None


@dataclass
class ExecuteMultipleRequest:
    # ids of cells to run
    cell_ids: list[CellId_t]
    # code to register/run for each cell
    codes: list[str]
    # incoming request, e.g. from Starlette or FastAPI
    request: Optional[HTTPRequest] = None
    # time at which the request was received
    timestamp: float = field(default_factory=time.time)

    def __repr__(self) -> str:
        return f"ExecuteMultipleRequest(cells={len(self.cell_ids)})"

    @property
    def execution_requests(self) -> list[ExecutionRequest]:
        return [
            ExecutionRequest(
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


@dataclass
class ExecuteScratchpadRequest:
    code: str
    # incoming request, e.g. from Starlette or FastAPI
    request: Optional[HTTPRequest] = None


@dataclass
class RenameRequest:
    filename: str


@dataclass
class SetUIElementValueRequest:
    object_ids: list[UIElementId]
    values: list[Any]
    # Incoming request, e.g. from Starlette or FastAPI
    request: Optional[HTTPRequest] = None
    # uniquely identifies the request
    token: str = field(default_factory=lambda: str(uuid4()))

    def __repr__(self) -> str:
        return f"SetUIElementValueRequest(n_elements={len(self.object_ids)}, token={self.token})"

    def __post_init__(self) -> None:
        assert len(self.object_ids) == len(self.values), (
            "Mismatched object_ids and values"
        )

    @staticmethod
    def from_ids_and_values(
        ids_and_values: list[tuple[UIElementId, Any]],
        request: Optional[HTTPRequest] = None,
    ) -> SetUIElementValueRequest:
        if not ids_and_values:
            return SetUIElementValueRequest(
                object_ids=[], values=[], request=request
            )
        object_ids, values = zip(*ids_and_values)
        return SetUIElementValueRequest(
            object_ids=list(object_ids),
            values=list(values),
            request=request,
        )

    @property
    def ids_and_values(self) -> list[tuple[UIElementId, Any]]:
        return list(zip(self.object_ids, self.values))


@dataclass
class FunctionCallRequest:
    function_call_id: RequestId
    namespace: str
    function_name: str
    args: dict[str, Any]

    def __repr__(self) -> str:
        return f"FunctionCallRequest(id={self.function_call_id}, fn={self.namespace}.{self.function_name})"


@dataclass
class AppMetadata:
    """Hold metadata about the app, like its filename."""

    query_params: SerializedQueryParams
    cli_args: SerializedCLIArgs
    app_config: _AppConfig
    argv: Union[list[str], None] = None

    filename: Optional[str] = None


@dataclass
class SetCellConfigRequest:
    # Map from Cell ID to (possibly partial) CellConfig
    configs: dict[CellId_t, dict[str, Any]]


@dataclass
class SetUserConfigRequest:
    # MarimoConfig TypedDict
    config: MarimoConfig


@dataclass
class CreationRequest:
    execution_requests: tuple[ExecutionRequest, ...]
    set_ui_element_value_request: SetUIElementValueRequest
    auto_run: bool
    request: Optional[HTTPRequest] = None


@dataclass
class DeleteCellRequest:
    cell_id: CellId_t


@dataclass
class StopRequest:
    pass


@dataclass
class CodeCompletionRequest:
    id: CompletionRequestId
    document: str
    cell_id: CellId_t

    def __repr__(self) -> str:
        return f"CodeCompletionRequest(id={self.id}, cell={self.cell_id})"


@dataclass
class InstallMissingPackagesRequest:
    # TODO: index URL (index/channel/...)
    manager: str

    # Map from package name to desired version
    # If the package name is not in the map, the latest version
    # will be installed
    versions: dict[str, str]


@dataclass
class PreviewDatasetColumnRequest:
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


@dataclass
class PreviewSQLTableRequest:
    """Preview table details in an SQL database"""

    request_id: RequestId
    engine: str
    database: str
    schema: str
    table_name: str


@dataclass
class PreviewSQLTableListRequest:
    """Preview list of tables in an SQL schema"""

    request_id: RequestId
    engine: str
    database: str
    schema: str


@dataclass
class PreviewDataSourceConnectionRequest:
    """Fetch a datasource connection"""

    engine: str


@dataclass
class ListSecretKeysRequest:
    request_id: RequestId


@dataclass
class ModelMessage:
    state: dict[str, Any]
    buffer_paths: list[list[Union[str, int]]]


@dataclass
class SetModelMessageRequest:
    model_id: WidgetModelId
    message: ModelMessage
    buffers: Optional[list[str]] = None


@dataclass
class RefreshSecretsRequest:
    pass


ControlRequest = Union[
    CreationRequest,
    DeleteCellRequest,
    ExecuteMultipleRequest,
    ExecuteScratchpadRequest,
    ExecuteStaleRequest,
    FunctionCallRequest,
    InstallMissingPackagesRequest,
    ListSecretKeysRequest,
    PdbRequest,
    PreviewDatasetColumnRequest,
    PreviewSQLTableListRequest,
    PreviewDataSourceConnectionRequest,
    PreviewSQLTableRequest,
    RefreshSecretsRequest,
    RenameRequest,
    SetCellConfigRequest,
    SetUIElementValueRequest,
    SetModelMessageRequest,
    SetUserConfigRequest,
    StopRequest,
]
