# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from marimo._ast.cell import CellId_t

UIElementId = str
CompletionRequestId = str
FunctionCallId = str


@dataclass
class ExecutionRequest:
    cell_id: CellId_t
    code: str


@dataclass
class ExecuteMultipleRequest:
    execution_requests: List[ExecutionRequest]


@dataclass
class SetUIElementValueRequest:
    # (object id, value) tuples
    ids_and_values: List[Tuple[UIElementId, Any]]


@dataclass
class FunctionCallRequest:
    function_call_id: FunctionCallId
    namespace: str
    function_name: str
    args: Dict[str, Any]


@dataclass
class AppMetadata:
    """Hold metadata about the app, like its filename."""

    filename: Optional[str] = None


@dataclass
class SetCellConfigRequest:
    # Map from Cell ID to (possibly partial) CellConfig
    configs: Dict[CellId_t, Dict[str, object]]


@dataclass
class CreationRequest:
    execution_requests: Tuple[ExecutionRequest, ...]
    set_ui_element_value_request: SetUIElementValueRequest


@dataclass
class DeleteRequest:
    cell_id: CellId_t


@dataclass
class StopRequest:
    pass


@dataclass
class CompletionRequest:
    id: CompletionRequestId
    document: str
    cell_id: CellId_t


ControlRequest = Union[
    ExecuteMultipleRequest,
    CreationRequest,
    DeleteRequest,
    FunctionCallRequest,
    SetCellConfigRequest,
    SetUIElementValueRequest,
    StopRequest,
]
