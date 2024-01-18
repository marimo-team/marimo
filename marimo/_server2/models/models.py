from __future__ import annotations

from typing import Any, Optional, Union

from marimo._ast.cell import CellConfig, CellId_t
from marimo._config.config import MarimoConfig
from marimo._server2.models.base import CamelModel

UIElementId = str


class UpdateComponentValuesRequest(CamelModel):
    object_ids: list[UIElementId]
    values: list[Union[str, bool, int, float, None]]


class InstantiateRequest(CamelModel):
    object_ids: list[UIElementId]
    values: list[Union[str, bool, int, float, None]]


class FunctionCallRequest(CamelModel):
    function_call_id: str
    namespace: str
    function_name: str
    args: dict[str, Any]


class BaseResponse(CamelModel):
    success: bool


class SuccessResponse(BaseResponse):
    success: bool = True


class CodeCompleteRequest(CamelModel):
    id: str
    document: str
    cell_id: CellId_t


class DeleteCellRequest(CamelModel):
    cell_id: CellId_t


class DirectoryAutocompleteRequest(CamelModel):
    prefix: str


class DirectoryAutocompleteResponse(CamelModel):
    directories: list[str]
    files: list[str]


class FormatRequest(CamelModel):
    codes: dict[CellId_t, str]
    line_length: int


class FormatResponse(CamelModel):
    codes: dict[CellId_t, str]


class ReadCodeResponse(CamelModel):
    contents: str


class RenameFileRequest(CamelModel):
    filename: str


class RunRequest(CamelModel):
    # ids of cells to run
    cell_ids: list[CellId_t]
    # code to register/run for each cell
    codes: list[str]


class SaveRequest(CamelModel):
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


class SaveAppConfigurationRequest(CamelModel):
    # partial app config
    config: dict[str, Any]


class SaveUserConfigurationRequest(CamelModel):
    # user configuration
    config: MarimoConfig


class SetCellConfigRequest(CamelModel):
    # Map from Cell ID to (possibly partial) CellConfig
    configs: dict[CellId_t, dict[str, object]]


class StdinRequest(CamelModel):
    text: str
