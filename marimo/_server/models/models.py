# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Union

from marimo._ast.cell import CellConfig, CellId_t
from marimo._config.config import MarimoConfig

UIElementId = str


@dataclass
class UpdateComponentValuesRequest:
    object_ids: list[UIElementId]
    values: list[Union[str, bool, int, float, None]]


@dataclass
class InstantiateRequest:
    object_ids: list[UIElementId]
    values: list[Union[str, bool, int, float, None]]


@dataclass
class FunctionCallRequest:
    function_call_id: str
    namespace: str
    function_name: str
    args: dict[str, Any]


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
    directories: list[str]
    files: list[str]


@dataclass
class FormatRequest:
    codes: dict[CellId_t, str]
    line_length: int


@dataclass
class FormatResponse:
    codes: dict[CellId_t, str]


@dataclass
class ReadCodeResponse:
    contents: str


@dataclass
class RenameFileRequest:
    filename: str


@dataclass
class RunRequest:
    # ids of cells to run
    cell_ids: list[CellId_t]
    # code to register/run for each cell
    codes: list[str]


@dataclass
class SaveRequest:
    # code for each cell
    codes: list[str]
    # name of each cell
    names: list[str]
    # config for each cell
    configs: list[CellConfig]
    # path to app
    filename: str
    # layout of app
    layout: Optional[dict[str, Any]] = None


@dataclass
class SaveAppConfigurationRequest:
    # partial app config
    config: dict[str, Any]


@dataclass
class SaveUserConfigurationRequest:
    # user configuration
    config: MarimoConfig


@dataclass
class SetCellConfigRequest:
    # Map from Cell ID to (possibly partial) CellConfig
    configs: dict[CellId_t, dict[str, object]]


@dataclass
class StdinRequest:
    text: str
