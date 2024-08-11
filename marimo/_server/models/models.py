# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from marimo._ast.cell import CellConfig, CellId_t
from marimo._config.config import MarimoConfig
from marimo._runtime.requests import (
    ExecuteMultipleRequest,
    ExecuteScratchpadRequest,
    RenameRequest,
)

UIElementId = str


@dataclass
class UpdateComponentValuesRequest:
    object_ids: List[UIElementId]
    values: List[Any]

    def zip(
        self,
    ) -> List[tuple[UIElementId, Any]]:
        return list(zip(self.object_ids, self.values))

    # Validate same length
    def __post_init__(self) -> None:
        assert len(self.object_ids) == len(
            self.values
        ), "Mismatched object_ids and values"


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

    def as_execution_request(self) -> RenameRequest:
        return RenameRequest(filename=os.path.abspath(self.filename))


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
        return ExecuteMultipleRequest(cell_ids=self.cell_ids, codes=self.codes)

    # Validate same length
    def __post_init__(self) -> None:
        assert len(self.cell_ids) == len(
            self.codes
        ), "Mismatched cell_ids and codes"


@dataclass
class RunScratchpadRequest:
    code: str

    def as_execution_request(self) -> ExecuteScratchpadRequest:
        return ExecuteScratchpadRequest(code=self.code)


@dataclass
class SaveNotebookRequest:
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
    # persist the file to disk
    persist: bool = True

    # Validate same length
    def __post_init__(self) -> None:
        assert len(self.cell_ids) == len(
            self.codes
        ), "Mismatched cell_ids and codes"
        assert len(self.cell_ids) == len(
            self.names
        ), "Mismatched cell_ids and names"
        assert len(self.cell_ids) == len(
            self.configs
        ), "Mismatched cell_ids and configs"


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
