# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from typing import Any, Literal, Optional

import msgspec

from marimo._ast.cell import CellConfig
from marimo._runtime.commands import (
    ClearCacheCommand,
    CodeCompletionCommand,
    DebugCellCommand,
    DeleteCellCommand,
    ExecuteCellsCommand,
    ExecuteScratchpadCommand,
    GetCacheInfoCommand,
    HTTPRequest,
    InstallPackagesCommand,
    InvokeFunctionCommand,
    ListDataSourceConnectionCommand,
    ListSecretKeysCommand,
    ListSQLTablesCommand,
    PreviewDatasetColumnCommand,
    PreviewSQLTableCommand,
    UpdateCellConfigCommand,
    UpdateUIElementCommand,
    UpdateUserConfigCommand,
    UpdateWidgetModelCommand,
    ValidateSQLCommand,
)
from marimo._types.ids import CellId_t, UIElementId


class ListSecretKeysRequest(ListSecretKeysCommand, tag=False):
    def as_command(self) -> ListSecretKeysCommand:
        return ListSecretKeysCommand(request_id=self.request_id)


class ClearCacheRequest(ClearCacheCommand, tag=False):
    def as_command(self) -> ClearCacheCommand:
        return ClearCacheCommand()


class GetCacheInfoRequest(GetCacheInfoCommand, tag=False):
    def as_command(self) -> GetCacheInfoCommand:
        return GetCacheInfoCommand()


class DebugCellRequest(DebugCellCommand, tag=False):
    def as_command(self) -> DebugCellCommand:
        return DebugCellCommand(cell_id=self.cell_id, request=self.request)


class ExecuteScratchpadRequest(ExecuteScratchpadCommand, tag=False):
    def as_command(self) -> ExecuteScratchpadCommand:
        return ExecuteScratchpadCommand(code=self.code, request=self.request)


class InvokeFunctionRequest(InvokeFunctionCommand, tag=False):
    def as_command(self) -> InvokeFunctionCommand:
        return InvokeFunctionCommand(
            function_call_id=self.function_call_id,
            namespace=self.namespace,
            function_name=self.function_name,
            args=self.args,
        )


class UpdateUIElementRequest(UpdateUIElementCommand, tag=False):
    def as_command(self) -> UpdateUIElementCommand:
        return UpdateUIElementCommand(
            object_ids=self.object_ids,
            values=self.values,
            request=self.request,
            token=self.token,
        )


class UpdateWidgetModelRequest(UpdateWidgetModelCommand, tag=False):
    def as_command(self) -> UpdateWidgetModelCommand:
        return UpdateWidgetModelCommand(
            model_id=self.model_id,
            message=self.message,
            buffers=self.buffers,
        )


class ListDataSourceConnectionRequest(
    ListDataSourceConnectionCommand, tag=False
):
    def as_command(self) -> ListDataSourceConnectionCommand:
        return ListDataSourceConnectionCommand(engine=self.engine)


class ListSQLTablesRequest(ListSQLTablesCommand, tag=False):
    def as_command(self) -> ListSQLTablesCommand:
        return ListSQLTablesCommand(
            request_id=self.request_id,
            engine=self.engine,
            database=self.database,
            schema=self.schema,
        )


class PreviewDatasetColumnRequest(PreviewDatasetColumnCommand, tag=False):
    def as_command(self) -> PreviewDatasetColumnCommand:
        return PreviewDatasetColumnCommand(
            source_type=self.source_type,
            source=self.source,
            table_name=self.table_name,
            column_name=self.column_name,
            fully_qualified_table_name=self.fully_qualified_table_name,
        )


class PreviewSQLTableRequest(PreviewSQLTableCommand, tag=False):
    def as_command(self) -> PreviewSQLTableCommand:
        return PreviewSQLTableCommand(
            request_id=self.request_id,
            engine=self.engine,
            database=self.database,
            schema=self.schema,
            table_name=self.table_name,
        )


class ValidateSQLRequest(ValidateSQLCommand, tag=False):
    def as_command(self) -> ValidateSQLCommand:
        return ValidateSQLCommand(
            query=self.query,
            only_parse=self.only_parse,
            engine=self.engine,
            dialect=self.dialect,
            request_id=self.request_id,
        )


class UpdateUserConfigRequest(UpdateUserConfigCommand, tag=False):
    def as_command(self) -> UpdateUserConfigCommand:
        return UpdateUserConfigCommand(config=self.config)


class DeleteCellRequest(DeleteCellCommand, tag=False):
    def as_command(self) -> DeleteCellCommand:
        return DeleteCellCommand(cell_id=self.cell_id)


class InstallPackagesRequest(InstallPackagesCommand, tag=False):
    def as_command(self) -> InstallPackagesCommand:
        return InstallPackagesCommand(
            manager=self.manager, versions=self.versions
        )


class UpdateCellConfigRequest(UpdateCellConfigCommand, tag=False):
    def as_command(self) -> UpdateCellConfigCommand:
        return UpdateCellConfigCommand(configs=self.configs)


class CodeCompletionRequest(CodeCompletionCommand, tag=False):
    def as_command(self) -> CodeCompletionCommand:
        return CodeCompletionCommand(
            id=self.id,
            document=self.document,
            cell_id=self.cell_id,
        )


class UpdateUIElementValuesRequest(msgspec.Struct, rename="camel"):
    object_ids: list[UIElementId]
    values: list[Any]

    # Validate same length
    def __post_init__(self) -> None:
        assert len(self.object_ids) == len(self.values), (
            "Mismatched object_ids and values"
        )


class InstantiateNotebookRequest(UpdateUIElementValuesRequest):
    auto_run: bool = True
    # Optional: cell codes to use instead of the codes from the file.
    # This is used when the frontend has local edits that should be
    # used instead of the file codes (e.g., pre-connect editing).
    # Maps cell_id -> code.
    codes: Optional[dict[CellId_t, str]] = None


class BaseResponse(msgspec.Struct, rename="camel"):
    success: bool


class SuccessResponse(BaseResponse):
    success: bool = True


class ErrorResponse(BaseResponse):
    success: bool = False
    message: Optional[str] = None


class FormatCellsRequest(msgspec.Struct, rename="camel"):
    codes: dict[CellId_t, str]
    line_length: int


class FormatResponse(msgspec.Struct, rename="camel"):
    codes: dict[CellId_t, str]


class ReadCodeResponse(msgspec.Struct, rename="camel"):
    contents: str


class RenameNotebookRequest(msgspec.Struct, rename="camel"):
    filename: str


class UpdateCellIdsRequest(msgspec.Struct, rename="camel"):
    cell_ids: list[CellId_t]


class ExecuteCellsRequest(msgspec.Struct, rename="camel"):
    # ids of cells to run
    cell_ids: list[CellId_t]
    # code to register/run for each cell
    codes: list[str]
    # incoming request, e.g. from Starlette or FastAPI
    request: Optional[HTTPRequest] = None

    def as_command(self) -> ExecuteCellsCommand:
        return ExecuteCellsCommand(
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
    # deep partial user configuration
    config: dict[str, Any]


class StdinRequest(msgspec.Struct, rename="camel"):
    text: str


class InvokeAiToolRequest(msgspec.Struct, rename="camel"):
    tool_name: str
    arguments: dict[str, Any]


class InvokeAiToolResponse(BaseResponse):
    tool_name: str
    result: Any
    error: Optional[str] = None


class MCPStatusResponse(msgspec.Struct, rename="camel"):
    status: Literal["ok", "partial", "error"]
    error: Optional[str] = None
    servers: dict[
        str, Literal["pending", "connected", "disconnected", "failed"]
    ] = {}  # server_name -> status


class MCPRefreshResponse(BaseResponse):
    error: Optional[str] = None
    servers: dict[str, bool] = {}  # server_name -> connected
