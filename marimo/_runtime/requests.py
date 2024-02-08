# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Union

from marimo._ast.cell import CellId_t


@dataclass
class ExecutionRequest:
    cell_id: CellId_t
    code: str


@dataclass
class ExecuteMultipleRequest:
    execution_requests: tuple[ExecutionRequest, ...]


@dataclass
class SetUIElementValueRequest:
    # (object id, value) tuples
    ids_and_values: list[tuple[str, Any]]


@dataclass
class FunctionCallRequest:
    function_call_id: str
    namespace: str
    function_name: str
    args: dict[str, Any]


@dataclass
class AppMetadata:
    """Hold metadata about the app, like its filename."""

    filename: Optional[str] = None


@dataclass
class SetCellConfigRequest:
    configs: dict[CellId_t, dict[str, object]]


@dataclass
class CreationRequest:
    execution_requests: tuple[ExecutionRequest, ...]
    set_ui_element_value_request: SetUIElementValueRequest


@dataclass
class DeleteRequest:
    cell_id: CellId_t


@dataclass
class StopRequest:
    pass


@dataclass
class CompletionRequest:
    completion_id: str
    document: str
    cell_id: CellId_t


@dataclass
class ConfigurationRequest:
    # stringified MarimoConfig
    config: str


ControlRequest = Union[
    ExecuteMultipleRequest,
    CreationRequest,
    DeleteRequest,
    FunctionCallRequest,
    SetCellConfigRequest,
    SetUIElementValueRequest,
    StopRequest,
    ConfigurationRequest,
]
