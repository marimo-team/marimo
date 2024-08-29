# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import os
import subprocess
import sys
from typing import TYPE_CHECKING, Any, Dict

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
from marimo._ast.cell import CellConfig, RuntimeStateType
from marimo._cli.print import orange
from marimo._config.config import MarimoConfig
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.mime import MIME
from marimo._plugins.core.web_component import JSONType
from marimo._runtime.packages.module_name_to_pypi_name import (
    module_name_to_pypi_name,
)
from marimo._server.api.router import build_routes
from marimo._utils.dataclass_to_openapi import (
    PythonTypeToOpenAPI,
)

if TYPE_CHECKING:
    import psutil


def _generate_schema() -> dict[str, Any]:
    # dataclass components used in websocket messages
    # these are always snake_case
    MESSAGES = [
        # Base
        MIME,
        RuntimeStateType,
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
        ops.SendUIElementMessage,
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
        home.RunningNotebooksResponse,
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
        models.RunScratchpadRequest,
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
        requests.ExecuteScratchpadRequest,
        requests.ExecuteStaleRequest,
        requests.ExecutionRequest,
        requests.FunctionCallRequest,
        requests.InstallMissingPackagesRequest,
        requests.PreviewDatasetColumnRequest,
        requests.RenameRequest,
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
        RuntimeStateType: "RuntimeState",
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

    click.echo(yaml.dump(_generate_schema(), default_flow_style=False))


@click.group(help="Various commands for the marimo processes", hidden=True)
def ps() -> None:
    pass


def get_marimo_processes() -> list["psutil.Process"]:
    import psutil

    def is_marimo_process(proc: psutil.Process) -> bool:
        if proc.name() == "marimo":
            return True

        if proc.name().lower() == "python":
            try:
                cmds = proc.cmdline()
            except psutil.AccessDenied:
                return False
            except psutil.ZombieProcess:
                return False
            # any endswith marimo
            has_marimo = any(x.endswith("marimo") for x in cmds)
            # any command equals "tutorial", "edit", or "run"
            has_running_command = any(
                x in {"run", "tutorial", "edit"} for x in cmds
            )
            return has_marimo and has_running_command

        return False

    result: list[psutil.Process] = []

    for proc in psutil.process_iter():
        if is_marimo_process(proc):
            result.append(proc)

    return result


@ps.command(help="List the marimo processes", name="list")
def list_processes() -> None:
    """
    Example usage:

        marimo development ps list
    """
    # pretty print processes
    result = get_marimo_processes()
    for proc in result:
        cmds = proc.cmdline()
        cmd = " ".join(cmds[1:])
        click.echo(f"PID: {orange(str(proc.pid))} | {cmd}")


@ps.command(help="Kill the marimo processes")
def killall() -> None:
    """
    Example usage:

        marimo development ps killall
    """
    import os

    for proc in get_marimo_processes():
        # Ignore self
        if proc.pid == os.getpid():
            continue
        proc.kill()
        click.echo(f"Killed process {proc.pid}")

    click.echo("Killed all marimo processes")


@click.command(
    help="Inline packages according to PEP 723", name="inline-packages"
)
@click.argument("name", required=True)
def inline_packages(
    name: str,
) -> None:
    """
    Example usage:

        marimo development inline-packages

    This uses some heuristics to guess the package names from the imports in
    the file.

    Requires uv.
    Installation: https://docs.astral.sh/uv/getting-started/installation/
    """

    # Validate uv is installed
    if not DependencyManager.which("uv"):
        raise click.UsageError(
            "uv is not installed. See https://docs.astral.sh/uv/getting-started/installation/"
        )

    # Validate the file exists
    if not os.path.exists(name):
        raise click.FileError(name)

    # Validate >=3.10 for sys.stdlib_module_names
    if sys.version_info < (3, 10):
        # TOD: add support for < 3.10
        # We can use https://github.com/omnilib/stdlibs
        # to get the stdlib module names
        raise click.UsageError("Requires Python >=3.10")

    package_names = module_name_to_pypi_name()

    def get_pypi_package_names() -> list[str]:
        with open(name, "r") as file:
            tree = ast.parse(file.read(), filename=name)

        imported_modules = set[str]()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_modules.add(node.module.split(".")[0])

        pypi_names = [
            package_names.get(mod, mod.replace("_", "-"))
            for mod in imported_modules
        ]

        return pypi_names

    def is_stdlib_module(module_name: str) -> bool:
        return module_name in sys.stdlib_module_names

    pypi_names = get_pypi_package_names()

    # Filter out python distribution packages
    pypi_names = [name for name in pypi_names if not is_stdlib_module(name)]

    click.echo(f"Inlining packages: {pypi_names}")
    click.echo(f"into script: {name}")
    subprocess.run(
        [
            "uv",
            "add",
            "--script",
            name,
        ]
        + pypi_names
    )


development.add_command(inline_packages)
development.add_command(openapi)
development.add_command(ps)
