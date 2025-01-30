# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterator,
    List,
    Mapping,
    Optional,
    Tuple,
    TypeVar,
    Union,
)
from uuid import uuid4

from marimo._ast.cell import CellId_t
from marimo._config.config import MarimoConfig
from marimo._data.models import DataTableSource

if TYPE_CHECKING:
    from starlette.datastructures import URL
    from starlette.requests import HTTPConnection

UIElementId = str
CompletionRequestId = str
FunctionCallId = str

T = TypeVar("T")
ListOrValue = Union[T, List[T]]
SerializedQueryParams = Dict[str, ListOrValue[str]]
Primitive = Union[str, bool, int, float]
SerializedCLIArgs = Dict[str, ListOrValue[Primitive]]


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

    @staticmethod
    def from_request(request: HTTPConnection) -> "HTTPRequest":
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
            # Left out for now. This may contain information that the app author
            # does not want to expose.
            # session=request.session if "session" in request else {},
            # auth=request.auth if "auth" in request else {},
        )


@dataclass
class ExecutionRequest:
    cell_id: CellId_t
    code: str
    # incoming request, e.g. from Starlette or FastAPI
    request: Optional[HTTPRequest] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class ExecuteStaleRequest: ...


@dataclass
class ExecuteMultipleRequest:
    # ids of cells to run
    cell_ids: List[CellId_t]
    # code to register/run for each cell
    codes: List[str]
    # incoming request, e.g. from Starlette or FastAPI
    request: Optional[HTTPRequest] = None
    # time at which the request was received
    timestamp: float = field(default_factory=time.time)

    @property
    def execution_requests(self) -> List[ExecutionRequest]:
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
    request: Optional[HTTPRequest]


@dataclass
class RenameRequest:
    filename: str


@dataclass
class SetUIElementValueRequest:
    object_ids: List[UIElementId]
    values: List[Any]
    # Incoming request, e.g. from Starlette or FastAPI
    request: Optional[HTTPRequest] = None
    # uniquely identifies the request
    token: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        assert len(self.object_ids) == len(self.values), (
            "Mismatched object_ids and values"
        )

    @staticmethod
    def from_ids_and_values(
        ids_and_values: List[Tuple[UIElementId, Any]],
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
    def ids_and_values(self) -> List[Tuple[UIElementId, Any]]:
        return list(zip(self.object_ids, self.values))


@dataclass
class FunctionCallRequest:
    function_call_id: FunctionCallId
    namespace: str
    function_name: str
    args: Dict[str, Any]


@dataclass
class AppMetadata:
    """Hold metadata about the app, like its filename."""

    query_params: SerializedQueryParams
    cli_args: SerializedCLIArgs

    filename: Optional[str] = None


@dataclass
class SetCellConfigRequest:
    # Map from Cell ID to (possibly partial) CellConfig
    configs: Dict[CellId_t, Dict[str, Any]]


@dataclass
class SetUserConfigRequest:
    # MarimoConfig TypedDict
    config: MarimoConfig


@dataclass
class CreationRequest:
    execution_requests: Tuple[ExecutionRequest, ...]
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


@dataclass
class InstallMissingPackagesRequest:
    # TODO: index URL (index/channel/...)
    manager: str

    # Map from package name to desired version
    # If the package name is not in the map, the latest version
    # will be installed
    versions: Dict[str, str]


@dataclass
class PreviewDatasetColumnRequest:
    # The source type of the dataset
    source_type: DataTableSource
    # The source of the dataset
    source: str
    # The name of the dataset
    # This currently corresponds to the variable name
    table_name: str
    # The name of the column
    column_name: str


ControlRequest = Union[
    ExecuteMultipleRequest,
    ExecuteScratchpadRequest,
    ExecuteStaleRequest,
    CreationRequest,
    DeleteCellRequest,
    FunctionCallRequest,
    RenameRequest,
    SetCellConfigRequest,
    SetUserConfigRequest,
    SetUIElementValueRequest,
    StopRequest,
    InstallMissingPackagesRequest,
    PreviewDatasetColumnRequest,
]
