# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, TypeVar, Union
from uuid import uuid4

from marimo._ast.cell import CellId_t
from marimo._config.config import MarimoConfig
from marimo._data.models import DataTableSource

UIElementId = str
CompletionRequestId = str
FunctionCallId = str

T = TypeVar("T")
ListOrValue = Union[T, List[T]]
SerializedQueryParams = Dict[str, ListOrValue[str]]
Primitive = Union[str, bool, int, float]
SerializedCLIArgs = Dict[str, ListOrValue[Primitive]]


@dataclass
class ExecutionRequest:
    cell_id: CellId_t
    code: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class ExecuteStaleRequest: ...


@dataclass
class ExecuteMultipleRequest:
    # ids of cells to run
    cell_ids: List[CellId_t]
    # code to register/run for each cell
    codes: List[str]
    # time at which the request was received
    timestamp: float = field(default_factory=time.time)

    @property
    def execution_requests(self) -> List[ExecutionRequest]:
        return [
            ExecutionRequest(
                cell_id=cell_id, code=code, timestamp=self.timestamp
            )
            for cell_id, code in zip(self.cell_ids, self.codes)
        ]

    def __post_init__(self) -> None:
        assert len(self.cell_ids) == len(
            self.codes
        ), "Mismatched cell_ids and codes"


@dataclass
class ExecuteScratchpadRequest:
    code: str


@dataclass
class RenameRequest:
    filename: str


@dataclass
class SetUIElementValueRequest:
    object_ids: List[UIElementId]
    values: List[Any]
    # uniquely identifies the request
    token: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        assert len(self.object_ids) == len(
            self.values
        ), "Mismatched object_ids and values"

    @staticmethod
    def from_ids_and_values(
        ids_and_values: List[Tuple[UIElementId, Any]],
    ) -> SetUIElementValueRequest:
        if not ids_and_values:
            return SetUIElementValueRequest(object_ids=[], values=[])
        object_ids, values = zip(*ids_and_values)
        return SetUIElementValueRequest(
            object_ids=list(object_ids), values=list(values)
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
    # TODO: package manager (pip/conda/...), index URL (index/channel/...)
    manager: str


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
