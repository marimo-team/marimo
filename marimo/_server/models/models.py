# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from marimo._ast.cell import CellConfig, CellId_t
from marimo._config.config import MarimoConfig
from marimo._runtime.requests import ExecuteMultipleRequest, ExecutionRequest

UIElementId = str


@dataclass
class UpdateComponentValuesRequest:
    object_ids: List[UIElementId]
    values: List[Union[str, bool, int, float, None]]

    def zip(
        self,
    ) -> List[tuple[UIElementId, Union[str, bool, int, float, None]]]:
        return list(zip(self.object_ids, self.values))


@dataclass
class InstantiateRequest(UpdateComponentValuesRequest):
    pass


@dataclass
class BaseResponse:
    success: bool


@dataclass
class SuccessResponse(BaseResponse):
    success: bool = True


@dataclass
class FormatRequest:
    codes: Dict[CellId_t, str]
    line_length: int


@dataclass
class FormatResponse:
    codes: Dict[CellId_t, str]


@dataclass
class ReadCodeResponse:
    contents: str


@dataclass
class RenameFileRequest:
    filename: str


@dataclass
class OpenFileRequest:
    path: str


@dataclass
class RunRequest:
    # ids of cells to run
    cell_ids: List[CellId_t]
    # code to register/run for each cell
    codes: List[str]

    def as_execution_request(self) -> ExecuteMultipleRequest:
        return ExecuteMultipleRequest(
            execution_requests=[
                ExecutionRequest(cell_id=cid, code=code)
                for cid, code in zip(self.cell_ids, self.codes)
            ]
        )


@dataclass
class SaveRequest:
    # id of each cell
    cell_ids: List[CellId_t]
    # code for each cell
    codes: List[str]
    # name of each cell
    names: List[str]
    # config for each cell
    configs: List[CellConfig]
    # path to app
    filename: str
    # layout of app
    layout: Optional[Dict[str, Any]] = None


@dataclass
class SaveAppConfigurationRequest:
    # partial app config
    config: Dict[str, Any]


@dataclass
class SaveUserConfigurationRequest:
    # user configuration
    config: MarimoConfig


@dataclass
class StdinRequest:
    text: str
