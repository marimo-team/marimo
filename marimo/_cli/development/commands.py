# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Dict, Type

import click
from starlette.schemas import SchemaGenerator

import marimo._runtime.requests as requests
import marimo._server.models.completion as completion
import marimo._server.models.export as export
import marimo._server.models.files as files
import marimo._server.models.home as home
import marimo._server.models.models as models
import marimo._snippets.snippets as snippets
from marimo import __version__
from marimo._ast.cell import CellConfig
from marimo._config.config import MarimoConfig
from marimo._server.api.router import build_routes
from marimo._utils.dataclass_to_openapi import dataclass_to_openapi_spec


def _generate_schema() -> dict[str, Any]:
    # dataclass components that we can generate schemas for
    COMPONENTS = [
        # Sub components
        requests.AppMetadata,
        home.MarimoFile,
        files.FileInfo,
        MarimoConfig,
        CellConfig,
        requests.ExecutionRequest,
        snippets.SnippetSection,
        snippets.Snippet,
        snippets.Snippets,
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
        models.BaseResponse,
        models.FormatRequest,
        models.FormatResponse,
        models.InstantiateRequest,
        models.OpenFileRequest,
        models.ReadCodeResponse,
        models.RenameFileRequest,
        models.RunRequest,
        models.SaveAppConfigurationRequest,
        models.SaveRequest,
        models.SaveUserConfigurationRequest,
        models.StdinRequest,
        models.SuccessResponse,
        models.SuccessResponse,
        models.UpdateComponentValuesRequest,
        requests.CompletionRequest,
        requests.CreationRequest,
        requests.DeleteRequest,
        requests.ExecuteMultipleRequest,
        requests.ExecuteStaleRequest,
        requests.ExecutionRequest,
        requests.FunctionCallRequest,
        requests.InstallMissingPackagesRequest,
        requests.PreviewDatasetColumnRequest,
        requests.SetCellConfigRequest,
        requests.SetUIElementValueRequest,
        requests.SetUserConfigRequest,
        requests.StopRequest,
    ]

    processed_classes: Dict[Type[Any], str] = {}

    component_schemas: Dict[str, Any] = {}
    for cls in COMPONENTS:
        # Remove self from the list
        # since it may not have been processed yet
        if cls in processed_classes:
            del processed_classes[cls]
        component_schemas[cls.__name__] = dataclass_to_openapi_spec(
            cls, processed_classes
        )

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


@click.group(help="""Various commands for the marimo development.""")
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
