# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Literal, Optional

import msgspec

from marimo._ast.cell import CellConfig
from marimo._messaging.notebook.changes import DocumentChange
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
    ListSQLSchemasCommand,
    ListSQLTablesCommand,
    ModelCommand,
    PreviewDatasetColumnCommand,
    PreviewSQLTableCommand,
    StorageDownloadCommand,
    StorageListEntriesCommand,
    UpdateCellConfigCommand,
    UpdateUIElementCommand,
    UpdateUserConfigCommand,
    ValidateSQLCommand,
)
from marimo._types.ids import CellId_t, UIElementId


class ListSecretKeysRequest(ListSecretKeysCommand, tag=False):
    """HTTP request model for listing available secret keys."""

    def as_command(self) -> ListSecretKeysCommand:
        """Convert this request to its corresponding runtime command."""
        return ListSecretKeysCommand(request_id=self.request_id)


class ClearCacheRequest(ClearCacheCommand, tag=False):
    """HTTP request model for clearing the notebook execution cache."""

    def as_command(self) -> ClearCacheCommand:
        """Convert this request to its corresponding runtime command."""
        return ClearCacheCommand()


class GetCacheInfoRequest(GetCacheInfoCommand, tag=False):
    """HTTP request model for retrieving notebook cache metadata."""

    def as_command(self) -> GetCacheInfoCommand:
        """Convert this request to its corresponding runtime command."""
        return GetCacheInfoCommand()


class DebugCellRequest(DebugCellCommand, tag=False):
    """HTTP request model for starting a debugger session on a cell."""

    def as_command(self) -> DebugCellCommand:
        """Convert this request to its corresponding runtime command."""
        return DebugCellCommand(cell_id=self.cell_id, request=self.request)


class ExecuteScratchpadRequest(ExecuteScratchpadCommand, tag=False):
    """HTTP request model for executing code in the scratchpad."""

    def as_command(self) -> ExecuteScratchpadCommand:
        """Convert this request to its corresponding runtime command."""
        return ExecuteScratchpadCommand(code=self.code, request=self.request)


class InvokeFunctionRequest(InvokeFunctionCommand, tag=False):
    """HTTP request model for invoking a registered marimo function."""

    def as_command(self) -> InvokeFunctionCommand:
        """Convert this request to its corresponding runtime command."""
        return InvokeFunctionCommand(
            function_call_id=self.function_call_id,
            namespace=self.namespace,
            function_name=self.function_name,
            args=self.args,
        )


class UpdateUIElementRequest(UpdateUIElementCommand, tag=False):
    """HTTP request model for updating the value of one or more UI elements."""

    def as_command(self) -> UpdateUIElementCommand:
        """Convert this request to its corresponding runtime command."""
        return UpdateUIElementCommand(
            object_ids=self.object_ids,
            values=self.values,
            request=self.request,
            token=self.token,
        )


class ModelRequest(ModelCommand, tag=False):
    """HTTP request model for sending a message to a widget model."""

    def as_command(self) -> ModelCommand:
        """Convert this request to its corresponding runtime command."""
        return ModelCommand(
            model_id=self.model_id,
            message=self.message,
            buffers=self.buffers,
        )


class ListDataSourceConnectionRequest(
    ListDataSourceConnectionCommand, tag=False
):
    """HTTP request model for listing available data source connections."""

    def as_command(self) -> ListDataSourceConnectionCommand:
        """Convert this request to its corresponding runtime command."""
        return ListDataSourceConnectionCommand(engine=self.engine)


class ListSQLTablesRequest(ListSQLTablesCommand, tag=False):
    """HTTP request model for listing tables in a SQL database."""

    def as_command(self) -> ListSQLTablesCommand:
        """Convert this request to its corresponding runtime command."""
        return ListSQLTablesCommand(
            request_id=self.request_id,
            engine=self.engine,
            database=self.database,
            schema=self.schema,
        )


class ListSQLSchemasRequest(ListSQLSchemasCommand, tag=False):
    """HTTP request model for listing schemas in a SQL database."""

    def as_command(self) -> ListSQLSchemasCommand:
        """Convert this request to its corresponding runtime command."""
        return ListSQLSchemasCommand(
            request_id=self.request_id,
            engine=self.engine,
            database=self.database,
        )


class PreviewDatasetColumnRequest(PreviewDatasetColumnCommand, tag=False):
    """HTTP request model for previewing statistics of a dataset column."""

    def as_command(self) -> PreviewDatasetColumnCommand:
        """Convert this request to its corresponding runtime command."""
        return PreviewDatasetColumnCommand(
            source_type=self.source_type,
            source=self.source,
            table_name=self.table_name,
            column_name=self.column_name,
            fully_qualified_table_name=self.fully_qualified_table_name,
        )


class PreviewSQLTableRequest(PreviewSQLTableCommand, tag=False):
    """HTTP request model for previewing the schema of a SQL table."""

    def as_command(self) -> PreviewSQLTableCommand:
        """Convert this request to its corresponding runtime command."""
        return PreviewSQLTableCommand(
            request_id=self.request_id,
            engine=self.engine,
            database=self.database,
            schema=self.schema,
            table_name=self.table_name,
        )


class ValidateSQLRequest(ValidateSQLCommand, tag=False):
    """HTTP request model for validating or parsing a SQL query."""

    def as_command(self) -> ValidateSQLCommand:
        """Convert this request to its corresponding runtime command."""
        return ValidateSQLCommand(
            query=self.query,
            only_parse=self.only_parse,
            engine=self.engine,
            dialect=self.dialect,
            request_id=self.request_id,
        )


class StorageListEntriesRequest(StorageListEntriesCommand, tag=False):
    """HTTP request model for listing entries in a storage namespace."""

    def as_command(self) -> StorageListEntriesCommand:
        """Convert this request to its corresponding runtime command."""
        return StorageListEntriesCommand(
            request_id=self.request_id,
            namespace=self.namespace,
            limit=self.limit,
            prefix=self.prefix,
        )


class StorageDownloadRequest(StorageDownloadCommand, tag=False):
    """HTTP request model for downloading a file from storage."""

    def as_command(self) -> StorageDownloadCommand:
        """Convert this request to its corresponding runtime command."""
        return StorageDownloadCommand(
            request_id=self.request_id,
            namespace=self.namespace,
            path=self.path,
            preview=self.preview,
        )


class UpdateUserConfigRequest(UpdateUserConfigCommand, tag=False):
    """HTTP request model for updating the user configuration."""

    def as_command(self) -> UpdateUserConfigCommand:
        """Convert this request to its corresponding runtime command."""
        return UpdateUserConfigCommand(config=self.config)


class DeleteCellRequest(DeleteCellCommand, tag=False):
    """HTTP request model for deleting a cell from the notebook."""

    def as_command(self) -> DeleteCellCommand:
        """Convert this request to its corresponding runtime command."""
        return DeleteCellCommand(cell_id=self.cell_id)


class InstallPackagesRequest(InstallPackagesCommand, tag=False):
    """HTTP request model for installing Python packages into the environment."""

    def as_command(self) -> InstallPackagesCommand:
        """Convert this request to its corresponding runtime command."""
        return InstallPackagesCommand(
            manager=self.manager, versions=self.versions, source=self.source
        )


class UpdateCellConfigRequest(UpdateCellConfigCommand, tag=False):
    """HTTP request model for updating configuration options on one or more cells."""

    def as_command(self) -> UpdateCellConfigCommand:
        """Convert this request to its corresponding runtime command."""
        return UpdateCellConfigCommand(configs=self.configs)


class CodeCompletionRequest(CodeCompletionCommand, tag=False):
    """HTTP request model for requesting code completion suggestions for a cell."""

    def as_command(self) -> CodeCompletionCommand:
        """Convert this request to its corresponding runtime command."""
        return CodeCompletionCommand(
            id=self.id,
            document=self.document,
            cell_id=self.cell_id,
        )


class UpdateUIElementValuesRequest(msgspec.Struct, rename="camel"):
    """Request to batch-update the values of multiple UI elements by object ID."""
    object_ids: list[UIElementId]
    values: list[Any]

    # Validate same length
    def __post_init__(self) -> None:
        assert len(self.object_ids) == len(self.values), (
            "Mismatched object_ids and values"
        )


class InstantiateNotebookRequest(UpdateUIElementValuesRequest):
    """Request to instantiate a notebook session with initial UI element values."""

    auto_run: bool = True
    # Optional: cell codes to use instead of the codes from the file.
    # This is used when the frontend has local edits that should be
    # used instead of the file codes (e.g., pre-connect editing).
    # Maps cell_id -> code.
    codes: Optional[dict[CellId_t, str]] = None


class BaseResponse(msgspec.Struct, rename="camel"):
    """Base response struct with a success flag."""

    success: bool


class SuccessResponse(BaseResponse):
    """Response indicating a successful operation."""

    success: bool = True


class ErrorResponse(BaseResponse):
    """Response indicating a failed operation with an optional error message."""

    success: bool = False
    message: Optional[str] = None


class FormatCellsRequest(msgspec.Struct, rename="camel"):
    """Request to format cell code using the configured line length."""

    codes: dict[CellId_t, str]
    line_length: int


class FormatResponse(msgspec.Struct, rename="camel"):
    """Response containing formatted code for each requested cell."""

    codes: dict[CellId_t, str]


class ReadCodeResponse(msgspec.Struct, rename="camel"):
    """Response containing the raw source code of the notebook file."""

    contents: str


class RenameNotebookRequest(msgspec.Struct, rename="camel"):
    """Request to rename the current notebook file."""

    filename: str


class NotebookDocumentTransactionRequest(msgspec.Struct, rename="camel"):
    """Request to apply a batch of document changes to the notebook."""

    changes: list[DocumentChange]


class FocusCellRequest(msgspec.Struct, rename="camel"):
    """Request to move editor focus to a specific cell."""

    cell_id: CellId_t


class ExecuteCellsRequest(msgspec.Struct, rename="camel"):
    """Request to register and execute one or more cells by ID."""
    # ids of cells to run
    cell_ids: list[CellId_t]
    # code to register/run for each cell
    codes: list[str]
    # incoming request, e.g. from Starlette or FastAPI
    request: Optional[HTTPRequest] = None

    def as_command(self) -> ExecuteCellsCommand:
        """Convert this request to its corresponding runtime command."""
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
    """Request to save the current notebook's cells and layout to disk."""

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
    """Request to copy a notebook file from one path to another."""

    # path to app
    source: str
    destination: str


class SaveAppConfigurationRequest(msgspec.Struct, rename="camel"):
    """Request to save a partial update to the app-level configuration."""

    # partial app config
    config: dict[str, Any]


class SaveUserConfigurationRequest(msgspec.Struct, rename="camel"):
    """Request to save a deep-partial update to the user configuration."""

    # deep partial user configuration
    config: dict[str, Any]


class StdinRequest(msgspec.Struct, rename="camel"):
    """Request to send text to the kernel's standard input stream."""

    text: str


class InvokeAiToolRequest(msgspec.Struct, rename="camel"):
    """Request to invoke a named AI tool with the given arguments."""

    tool_name: str
    arguments: dict[str, Any]


class InvokeAiToolResponse(BaseResponse):
    """Response containing the result or error from an AI tool invocation."""

    tool_name: str
    result: Any
    error: Optional[str] = None


class MCPStatusResponse(msgspec.Struct, rename="camel"):
    """Response containing the connection status of all configured MCP servers."""

    status: Literal["ok", "partial", "error"]
    error: Optional[str] = None
    servers: dict[
        str, Literal["pending", "connected", "disconnected", "failed"]
    ] = {}  # server_name -> status


class MCPRefreshResponse(BaseResponse):
    """Response from a request to refresh MCP server connections."""

    error: Optional[str] = None
    servers: dict[str, bool] = {}  # server_name -> connected
