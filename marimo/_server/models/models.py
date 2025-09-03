# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import dataclasses
import os
from typing import Any, Optional

import msgspec

from marimo._ast.cell import CellConfig
from marimo._config.config import MarimoConfig
from marimo._runtime.requests import (
    ExecuteMultipleRequest,
    HTTPRequest,
    RenameRequest,
)
from marimo._types.ids import CellId_t, UIElementId
from marimo._utils.case import deep_to_camel_case


class UpdateComponentValuesRequest(msgspec.Struct, rename="camel"):
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


class InstantiateRequest(UpdateComponentValuesRequest):
    auto_run: bool = True


class BaseResponse(msgspec.Struct, rename="camel"):
    success: bool


class SuccessResponse(BaseResponse):
    success: bool = True


class ErrorResponse(BaseResponse):
    success: bool = False
    message: Optional[str] = None


class FormatRequest(msgspec.Struct, rename="camel"):
    codes: dict[CellId_t, str]
    line_length: int


class FormatResponse(msgspec.Struct, rename="camel"):
    codes: dict[CellId_t, str]


class ReadCodeResponse(msgspec.Struct, rename="camel"):
    contents: str


class RenameFileRequest(msgspec.Struct, rename="camel"):
    filename: str

    def as_execution_request(self) -> RenameRequest:
        return RenameRequest(filename=os.path.abspath(self.filename))


class RunRequest(msgspec.Struct, rename="camel"):
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


class SaveNotebookRequest(msgspec.Struct, rename="camel"):
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


class CopyNotebookRequest(msgspec.Struct, rename="camel"):
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


class SaveAppConfigurationRequest(msgspec.Struct, rename="camel"):
    # partial app config
    config: dict[str, Any]


class SaveUserConfigurationRequest(msgspec.Struct, rename="camel"):
    # user configuration
    config: MarimoConfig


class StdinRequest(msgspec.Struct, rename="camel"):
    text: str


class InvokeAiToolRequest(msgspec.Struct, rename="camel"):
    tool_name: str
    arguments: dict[str, Any]


class InvokeAiToolResponse(BaseResponse):
    tool_name: str
    result: Any
    error: Optional[str] = None
