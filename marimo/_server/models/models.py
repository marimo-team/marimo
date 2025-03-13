# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

from marimo._ast.cell import CellConfig
from marimo._config.config import MarimoConfig
from marimo._runtime.requests import (
    ExecuteMultipleRequest,
    ExecuteScratchpadRequest,
    HTTPRequest,
    RenameRequest,
)
from marimo._types.ids import CellId_t, UIElementId


@dataclass
class UpdateComponentValuesRequest:
    object_ids: list[UIElementId]
    values: list[Any]

    def zip(
        self,
    ) -> list[tuple[UIElementId, Any]]:
        return list(zip(self.object_ids, self.values))

    # Validate same length
    def __post_init__(self) -> None:
        assert len(self.object_ids) == len(self.values), (
            "Mismatched object_ids and values"
        )


@dataclass
class InstantiateRequest(UpdateComponentValuesRequest):
    auto_run: bool = True


@dataclass
class BaseResponse:
    success: bool


@dataclass
class SuccessResponse(BaseResponse):
    success: bool = True


@dataclass
class ErrorResponse(BaseResponse):
    success: bool = False
    message: Optional[str] = None


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

    def as_execution_request(self) -> RenameRequest:
        return RenameRequest(filename=os.path.abspath(self.filename))


@dataclass
class RunRequest:
    # ids of cells to run
    cell_ids: list[CellId_t]
    # code to register/run for each cell
    codes: list[str]
    # incoming request, e.g. from Starlette or FastAPI
    request: Optional[HTTPRequest] = None

    def as_execution_request(self) -> ExecuteMultipleRequest:
        return ExecuteMultipleRequest(
            cell_ids=self.cell_ids,
            codes=self.codes,
            request=self.request,
        )

    # Validate same length
    def __post_init__(self) -> None:
        assert len(self.cell_ids) == len(self.codes), (
            "Mismatched cell_ids and codes"
        )


@dataclass
class RunScratchpadRequest:
    code: str
    # incoming request, e.g. from Starlette or FastAPI
    request: Optional[HTTPRequest] = None

    def as_execution_request(self) -> ExecuteScratchpadRequest:
        return ExecuteScratchpadRequest(
            code=self.code,
            request=self.request,
        )


@dataclass
class SaveNotebookRequest:
    # id of each cell
    cell_ids: list[CellId_t]
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
    # persist the file to disk
    persist: bool = True

    # Validate same length
    def __post_init__(self) -> None:
        assert len(self.cell_ids) == len(self.codes), (
            "Mismatched cell_ids and codes"
        )
        assert len(self.cell_ids) == len(self.names), (
            "Mismatched cell_ids and names"
        )
        assert len(self.cell_ids) == len(self.configs), (
            "Mismatched cell_ids and configs"
        )


@dataclass
class CopyNotebookRequest:
    # path to app
    source: str
    destination: str

    # Validate filenames are valid, and destination path does not already exist
    def __post_init__(self) -> None:
        destination = os.path.basename(self.destination)
        assert self.source is not None
        assert self.destination is not None
        assert os.path.exists(self.source), (
            f'File "{self.source}" does not exist.'
            + "Please save the notebook and try again."
        )
        assert not os.path.exists(self.destination), (
            f'File "{destination}" already exists in this directory.'
        )


@dataclass
class SaveAppConfigurationRequest:
    # partial app config
    config: dict[str, Any]


@dataclass
class SaveUserConfigurationRequest:
    # user configuration
    config: MarimoConfig


@dataclass
class StdinRequest:
    text: str
