# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from marimo._ast.cell import CellConfig, CellId_t
from marimo._config.config import MarimoConfig

UIElementId = str


@dataclass
class UpdateComponentValuesRequest:
    object_ids: List[UIElementId]
    values: List[Union[str, bool, int, float, None]]


@dataclass
class InstantiateRequest:
    object_ids: List[UIElementId]
    values: List[Union[str, bool, int, float, None]]


@dataclass
class FunctionCallRequest:
    function_call_id: str
    namespace: str
    function_name: str
    args: Dict[str, Any]


@dataclass
class BaseResponse:
    success: bool


@dataclass
class SuccessResponse(BaseResponse):
    success: bool = True


@dataclass
class CodeCompleteRequest:
    id: str
    document: str
    cell_id: CellId_t


@dataclass
class DeleteCellRequest:
    cell_id: CellId_t


@dataclass
class DirectoryAutocompleteRequest:
    prefix: str


@dataclass
class DirectoryAutocompleteResponse:
    directories: List[str]
    files: List[str]


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
class RunRequest:
    # ids of cells to run
    cell_ids: List[CellId_t]
    # code to register/run for each cell
    codes: List[str]


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
class SetCellConfigRequest:
    # Map from Cell ID to (possibly partial) CellConfig
    configs: Dict[CellId_t, Dict[str, object]]


@dataclass
class StdinRequest:
    text: str
