# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Dict

import click
from starlette.schemas import SchemaGenerator

import marimo._data.models as data
import marimo._messaging.errors as errors
import marimo._messaging.ops as ops
import marimo._runtime.requests as requests
import marimo._server.models.completion as completion
import marimo._server.models.export as export
import marimo._server.models.files as files
import marimo._server.models.home as home
import marimo._server.models.models as models
import marimo._snippets.snippets as snippets
from marimo import __version__
from marimo._ast.cell import CellConfig, CellStatusType
from marimo._config.config import MarimoConfig
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.mime import MIME
from marimo._plugins.core.web_component import JSONType
from marimo._server.api.router import build_routes
from marimo._utils.dataclass_to_openapi import (
    PythonTypeToOpenAPI,
)


def _generate_schema() -> dict[str, Any]:
    # dataclass components used in websocket messages
    # these are always snake_case
    MESSAGES = [
        # Base
        MIME,
        CellStatusType,
        KnownMimeType,
        CellChannel,
        data.NonNestedLiteral,
        data.DataType,
        CellConfig,
        MarimoConfig,
        # Errors
        errors.CycleError,
        errors.MultipleDefinitionError,
        errors.DeleteNonlocalError,
        errors.MarimoInterruptionError,
        errors.MarimoAncestorStoppedError,
        errors.MarimoAncestorPreventedError,
        errors.MarimoStrictExecutionError,
        errors.MarimoExceptionRaisedError,
        errors.MarimoSyntaxError,
        errors.UnknownError,
        errors.Error,
        # Outputs
        CellOutput,
        # Data
        data.DataTableColumn,
        data.DataTable,
        data.ColumnSummary,
        # Operations
        ops.CellOp,
        ops.HumanReadableStatus,
        ops.FunctionCallResult,
        ops.RemoveUIElements,
        ops.Interrupted,
        ops.CompletedRun,
        ops.KernelReady,
        ops.CompletionResult,
        ops.Alert,
        ops.MissingPackageAlert,
        ops.InstallingPackageAlert,
        ops.Reconnected,
        ops.Banner,
        ops.Reload,
        ops.VariableDeclaration,
        ops.VariableValue,
        ops.Variables,
        ops.VariableValues,
        ops.Datasets,
        ops.DataColumnPreview,
        ops.QueryParamsSet,
        ops.QueryParamsAppend,
        ops.QueryParamsDelete,
        ops.QueryParamsClear,
        ops.UpdateCellCodes,
        ops.UpdateCellIdsRequest,
        ops.FocusCell,
        ops.MessageOperation,
    ]

    # dataclass components used in requests/responses
    REQUEST_RESPONSES = [
        # Sub components
        requests.AppMetadata,
        home.MarimoFile,
        files.FileInfo,
        requests.ExecutionRequest,
        snippets.SnippetSection,
        snippets.Snippet,
        snippets.Snippets,
        requests.SetUIElementValueRequest,
        # Requests/responses
        completion.AiCompletionRequest,
        export.ExportAsHTMLRequest,
        export.ExportAsMarkdownRequest,
        export.ExportAsScriptRequest,
        files.FileCreateRequest,
        files.FileCreateResponse,
        files.FileDeleteRequest,
        files.FileDeleteResponse,
        files.FileDetailsRequest,
        files.FileDetailsResponse,
        files.FileListRequest,
        files.FileListResponse,
        files.FileMoveRequest,
        files.FileMoveResponse,
        files.FileUpdateRequest,
        files.FileUpdateResponse,
        home.RecentFilesResponse,
        home.ShutdownSessionRequest,
        home.WorkspaceFilesRequest,
        home.WorkspaceFilesResponse,
        models.BaseResponse,
        models.FormatRequest,
        models.FormatResponse,
        models.InstantiateRequest,
        models.OpenFileRequest,
        models.ReadCodeResponse,
        models.RenameFileRequest,
        models.RunRequest,
        models.SaveAppConfigurationRequest,
        models.SaveNotebookRequest,
        models.SaveUserConfigurationRequest,
        models.StdinRequest,
        models.SuccessResponse,
        models.SuccessResponse,
        models.UpdateComponentValuesRequest,
        requests.CodeCompletionRequest,
        requests.CreationRequest,
        requests.DeleteCellRequest,
        requests.ExecuteMultipleRequest,
        requests.ExecuteStaleRequest,
        requests.ExecutionRequest,
        requests.FunctionCallRequest,
        requests.InstallMissingPackagesRequest,
        requests.PreviewDatasetColumnRequest,
        requests.SetCellConfigRequest,
        requests.SetUserConfigRequest,
        requests.StopRequest,
    ]

    processed_classes: Dict[Any, str] = {
        JSONType: "JSONType",
    }
    component_schemas: Dict[str, Any] = {
        # Hand-written schema to avoid circular dependencies
        "JSONType": {
            "oneOf": [
                {"type": "string"},
                {"type": "number"},
                {"type": "object"},
                {"type": "array"},
                {"type": "boolean"},
                {"type": "null"},
            ]
        }
    }
    # We must override the names of some Union Types,
    # otherwise, their __name__ is "Union"
    name_overrides: Dict[Any, str] = {
        JSONType: "JSONType",
        errors.Error: "Error",
        KnownMimeType: "MimeType",
        data.DataType: "DataType",
        data.NonNestedLiteral: "NonNestedLiteral",
        CellStatusType: "CellStatus",
        CellChannel: "CellChannel",
        ops.MessageOperation: "MessageOperation",
    }

    converter = PythonTypeToOpenAPI(
        camel_case=False, name_overrides=name_overrides
    )
    for cls in MESSAGES:
        # Remove self from the list
        # since it may not have been processed yet
        if cls in processed_classes:
            del processed_classes[cls]
        name = name_overrides.get(cls, cls.__name__)  # type: ignore[attr-defined]
        component_schemas[name] = converter.convert(cls, processed_classes)
        processed_classes[cls] = name

    converter = PythonTypeToOpenAPI(
        camel_case=True, name_overrides=name_overrides
    )
    for cls in REQUEST_RESPONSES:
        # Remove self from the list
        # since it may not have been processed yet
        if cls in processed_classes:
            del processed_classes[cls]
        name = name_overrides.get(cls, cls.__name__)  # type: ignore[attr-defined]
        component_schemas[name] = converter.convert(cls, processed_classes)
        processed_classes[cls] = name

    schemas = SchemaGenerator(
        {
            "openapi": "3.1.0",
            "info": {"title": "marimo API", "version": __version__},
            "components": {
                "schemas": {
                    **component_schemas,
                }
            },
        }
    )

    return schemas.get_schema(routes=build_routes())


@click.group(
    help="""Various commands for the marimo development.""", hidden=True
)
def development() -> None:
    pass


@click.command(help="""Print the marimo OpenAPI schema""")
def openapi() -> None:
    """
    Example usage:

        marimo development openapi
    """
    import yaml

    print(yaml.dump(_generate_schema(), default_flow_style=False))


development.add_command(openapi)
