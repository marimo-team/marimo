# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

from marimo._cli.errors import (
    MarimoCLIMissingDependencyError,
    MarimoCLIRuntimeError,
)
from marimo._cli.help_formatter import ColoredCommand, ColoredGroup
from marimo._data.models import DataType
from marimo._messaging.errors import Error as MarimoError
from marimo._messaging.notification import NotificationMessage
from marimo._runtime.commands import CommandMessage

if TYPE_CHECKING:
    import psutil


def _enrich_branded_types(
    component_schemas: dict[str, Any],
    models: list[object],
) -> None:
    """Post-process schemas to replace NewType string fields with $ref
    branded types.

    msgspec.json.schema_components() strips NewType wrappers, emitting plain
    ``{type: string}`` for fields like ``CellId_t``. This function:

    1. Adds named schemas for each branded type (e.g. ``CellId: {type: string}``).
    2. Walks every model struct's type hints and replaces inline schemas with
       ``$ref`` pointers wherever a field's annotation is (or contains) a
       registered NewType.
    """
    import types as _types
    import typing
    from typing import Union

    import msgspec

    from marimo._types.ids import (
        CellId_t,
        RequestId,
        SessionId,
        UIElementId,
        VariableName,
        WidgetModelId,
    )

    branded: dict[Any, tuple[str, str]] = {
        CellId_t: ("CellId", "cell-id"),
        UIElementId: ("UIElementId", "ui-element-id"),
        SessionId: ("SessionId", "session-id"),
        VariableName: ("VariableName", "variable-name"),
        RequestId: ("RequestId", "request-id"),
        WidgetModelId: ("WidgetModelId", "widget-model-id"),
    }

    # Step 1 — add named schemas for each branded type
    for schema_name, format_value in branded.values():
        component_schemas[schema_name] = {
            "type": "string",
            "format": format_value,
        }

    def make_ref(name: str) -> dict[str, str]:
        return {"$ref": f"#/components/schemas/{name}"}

    def _is_union(origin: Any) -> bool:
        return origin is Union or origin is getattr(_types, "UnionType", None)

    def resolve(ty: Any) -> dict[str, Any] | None:
        """Produce a branded schema for *ty*, or ``None``."""
        if ty in branded:
            return make_ref(branded[ty][0])

        origin = typing.get_origin(ty)
        args = typing.get_args(ty)

        # Union / Optional
        if _is_union(origin):
            non_none = [a for a in args if a is not type(None)]
            has_none = len(non_none) < len(args)
            if len(non_none) == 1:
                inner = resolve(non_none[0])
                if inner is not None:
                    if has_none:
                        return {"anyOf": [inner, {"type": "null"}]}
                    return inner
            return None

        # list[T]
        if origin is list:
            if args:
                inner = resolve(args[0])
                if inner is not None:
                    return {"type": "array", "items": inner}
            return None

        # tuple[T, ...]
        if origin is tuple:
            if len(args) == 2 and args[1] is Ellipsis:
                inner = resolve(args[0])
                if inner is not None:
                    return {"type": "array", "items": inner}
            return None

        # dict[K, V] — brand the value type (keys are always strings in JSON)
        if origin is dict and len(args) == 2:
            val = resolve(args[1])
            if val is not None:
                return {"type": "object", "additionalProperties": val}

        return None

    # Step 2 — collect *all* reachable struct types (not just MODELS,
    # since msgspec pulls in transitively-referenced structs too).
    all_structs: dict[str, type] = {}

    def _visit_type(ty: Any) -> None:
        if isinstance(ty, type) and issubclass(ty, msgspec.Struct):
            if ty.__name__ in all_structs:
                return
            all_structs[ty.__name__] = ty
            try:
                for hint in typing.get_type_hints(ty).values():
                    _visit_annotation(hint)
            except Exception:
                pass

    def _visit_annotation(ty: Any) -> None:
        if isinstance(ty, type):
            _visit_type(ty)
            return
        for arg in typing.get_args(ty):
            if arg is not Ellipsis and arg is not type(None):
                _visit_annotation(arg)

    for model in models:
        _visit_type(model)

    # Step 3 — walk collected structs and replace inline schemas with $refs.
    # Use msgspec.structs.fields() to map Python names → schema keys,
    # which accounts for rename="camel" and other rename strategies.
    for schema_name, struct_cls in all_structs.items():
        schema = component_schemas.get(schema_name)
        if schema is None:
            continue

        properties = schema.get("properties", {})

        try:
            hints = typing.get_type_hints(struct_cls)
        except Exception:
            continue

        field_to_schema_key: dict[str, str] = {}
        try:
            for fi in msgspec.structs.fields(struct_cls):
                field_to_schema_key[fi.name] = fi.encode_name
        except Exception:
            field_to_schema_key = {name: name for name in hints}

        for field_name, field_type in hints.items():
            schema_key = field_to_schema_key.get(field_name, field_name)
            if schema_key not in properties:
                continue

            replacement = resolve(field_type)
            if replacement is not None:
                # Preserve default value from the original schema
                existing = properties[schema_key]
                if isinstance(existing, dict) and "default" in existing:
                    replacement["default"] = existing["default"]
                properties[schema_key] = replacement

    # Step 4 — replace inline {type: string, contentEncoding: base64}
    # with a named $ref. msgspec already emits contentEncoding for
    # bytes fields; we just need to give it a name so the TS codegen
    # can brand it.
    component_schemas["Base64String"] = {
        "type": "string",
        "format": "base64",
        "contentEncoding": "base64",
    }

    def _make_base64_ref() -> dict[str, str]:
        # Fresh dict each time to avoid YAML anchor deduplication
        return {"$ref": "#/components/schemas/Base64String"}

    def _replace_base64(obj: Any) -> Any:
        if isinstance(obj, dict):
            if (
                obj.get("type") == "string"
                and obj.get("contentEncoding") == "base64"
            ):
                return _make_base64_ref()
            return {k: _replace_base64(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_replace_base64(item) for item in obj]
        return obj

    for schema_name in list(component_schemas):
        if schema_name == "Base64String":
            continue
        component_schemas[schema_name] = _replace_base64(
            component_schemas[schema_name]
        )


def _generate_server_api_schema() -> dict[str, Any]:
    import msgspec
    import msgspec.json
    from starlette.schemas import SchemaGenerator

    import marimo._data._external_storage.models as storage
    import marimo._data.models as data
    import marimo._messaging.notification as notifications
    import marimo._secrets.models as secrets_models
    from marimo._ai._types import ChatMessage
    from marimo._ast.cell import CellConfig, RuntimeStateType
    from marimo._config import config
    from marimo._messaging import errors
    from marimo._messaging.cell_output import CellChannel, CellOutput
    from marimo._messaging.mimetypes import KnownMimeType
    from marimo._metadata import opengraph
    from marimo._runtime import commands
    from marimo._runtime.packages.package_manager import PackageDescription
    from marimo._server.ai.tools.types import ToolDefinition
    from marimo._server.api.router import build_routes
    from marimo._server.models import (
        completion,
        export,
        files,
        home,
        lsp,
        models,
        packages,
        secrets,
    )
    from marimo._snippets import snippets

    MODELS = [
        # Base
        RuntimeStateType,
        KnownMimeType,
        CellChannel,
        data.NonNestedLiteral,
        data.DataType,
        CellConfig,
        config.OpenAiConfig,
        config.AnthropicConfig,
        config.GitHubConfig,
        config.GoogleAiConfig,
        config.BedrockConfig,
        config.AiConfig,
        config.MarimoConfig,
        config.StoreConfig,
        # Errors
        errors.SetupRootError,
        errors.MultipleDefinitionError,
        errors.CycleError,
        errors.MultipleDefinitionError,
        errors.ImportStarError,
        errors.MarimoInterruptionError,
        errors.MarimoInternalError,
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
        data.ColumnStats,
        data.DataSourceConnection,
        data.Schema,
        data.Database,
        # Storage
        storage.StorageEntry,
        storage.StorageNamespace,
        # Secrets
        secrets_models.SecretKeysWithProvider,
        secrets.CreateSecretRequest,
        # Operations
        notifications.CellNotification,
        notifications.HumanReadableStatus,
        notifications.FunctionCallResultNotification,
        notifications.UIElementMessageNotification,
        notifications.RemoveUIElementsNotification,
        notifications.InterruptedNotification,
        notifications.CompletedRunNotification,
        notifications.KernelReadyNotification,
        notifications.CompletionResultNotification,
        notifications.AlertNotification,
        notifications.MissingPackageAlertNotification,
        notifications.InstallingPackageAlertNotification,
        notifications.ReconnectedNotification,
        notifications.BannerNotification,
        notifications.ReloadNotification,
        notifications.VariableDeclarationNotification,
        notifications.VariableValue,
        notifications.VariablesNotification,
        notifications.VariableValuesNotification,
        notifications.DatasetsNotification,
        notifications.DataColumnPreviewNotification,
        notifications.SQLTablePreviewNotification,
        notifications.SQLTableListPreviewNotification,
        notifications.SQLSchemaListPreviewNotification,
        notifications.DataSourceConnectionsNotification,
        notifications.StorageNamespacesNotification,
        notifications.SecretKeysResultNotification,
        notifications.CacheClearedNotification,
        notifications.CacheInfoNotification,
        notifications.QueryParamsSetNotification,
        notifications.QueryParamsAppendNotification,
        notifications.QueryParamsDeleteNotification,
        notifications.QueryParamsClearNotification,
        notifications.FocusCellNotification,
        notifications.NotificationMessage,
        # ai
        ChatMessage,
        ToolDefinition,
        # Sub components
        home.MarimoFile,
        opengraph.OpenGraphMetadata,
        files.FileInfo,
        commands.ExecuteCellCommand,
        snippets.SnippetSection,
        snippets.Snippet,
        snippets.Snippets,
        commands.UpdateUIElementCommand,
        # Requests/responses
        completion.VariableContext,
        completion.SchemaColumn,
        completion.SchemaTable,
        completion.AiCompletionContext,
        completion.AiCompletionRequest,
        completion.AiInlineCompletionRequest,
        completion.ChatRequest,
        export.ExportAsHTMLRequest,
        export.ExportAsMarkdownRequest,
        export.ExportAsScriptRequest,
        export.ExportAsIPYNBRequest,
        export.ExportAsPDFRequest,
        export.UpdateCellOutputsRequest,
        files.FileCreateRequest,
        files.FileCreateResponse,
        files.FileDeleteRequest,
        files.FileDeleteResponse,
        files.FileDetailsRequest,
        files.FileDetailsResponse,
        files.FileListRequest,
        files.FileListResponse,
        files.FileSearchRequest,
        files.FileSearchResponse,
        files.FileMoveRequest,
        files.FileMoveResponse,
        files.FileCopyRequest,
        files.FileCopyResponse,
        files.FileOpenRequest,
        files.FileUpdateRequest,
        files.FileUpdateResponse,
        secrets.ListSecretKeysResponse,
        secrets.DeleteSecretRequest,
        packages.AddPackageRequest,
        PackageDescription,
        packages.ListPackagesResponse,
        packages.PackageOperationResponse,
        packages.RemovePackageRequest,
        packages.DependencyTreeResponse,
        lsp.LspHealthResponse,
        lsp.LspRestartRequest,
        lsp.LspRestartResponse,
        lsp.LspServerHealth,
        home.OpenTutorialRequest,
        home.RecentFilesResponse,
        home.RunningNotebooksResponse,
        home.ShutdownSessionRequest,
        home.WorkspaceFilesRequest,
        home.WorkspaceFilesResponse,
        commands.ClearCacheCommand,
        commands.CodeCompletionCommand,
        commands.DebugCellCommand,
        commands.DeleteCellCommand,
        commands.ExecuteCellsCommand,
        commands.ExecuteScratchpadCommand,
        commands.ExecuteStaleCellsCommand,
        commands.ExecuteCellCommand,
        commands.GetCacheInfoCommand,
        commands.HTTPRequest,
        commands.InstallPackagesCommand,
        commands.InvokeFunctionCommand,
        commands.ListDataSourceConnectionCommand,
        commands.ListSecretKeysCommand,
        commands.ListSQLTablesCommand,
        commands.ListSQLSchemasCommand,
        commands.ModelMessage,
        commands.PreviewDatasetColumnCommand,
        commands.PreviewSQLTableCommand,
        commands.RenameNotebookCommand,
        commands.StopKernelCommand,
        commands.UpdateCellConfigCommand,
        commands.UpdateUserConfigCommand,
        commands.ModelCommand,
        commands.ValidateSQLCommand,
        models.BaseResponse,
        models.ClearCacheRequest,
        models.CodeCompletionRequest,
        models.CopyNotebookRequest,
        models.DebugCellRequest,
        models.DeleteCellRequest,
        models.ExecuteScratchpadRequest,
        models.FormatCellsRequest,
        models.FormatResponse,
        models.GetCacheInfoRequest,
        models.InstallPackagesRequest,
        models.InstantiateNotebookRequest,
        models.InvokeAiToolRequest,
        models.InvokeAiToolResponse,
        models.InvokeFunctionRequest,
        models.ListDataSourceConnectionRequest,
        models.ListSecretKeysRequest,
        models.ListSQLTablesRequest,
        models.ListSQLSchemasRequest,
        models.MCPRefreshResponse,
        models.MCPStatusResponse,
        models.PreviewDatasetColumnRequest,
        models.PreviewSQLTableRequest,
        models.StorageListEntriesRequest,
        models.StorageDownloadRequest,
        models.ReadCodeResponse,
        models.RenameNotebookRequest,
        models.ExecuteCellsRequest,
        models.SaveAppConfigurationRequest,
        models.SaveNotebookRequest,
        models.SaveUserConfigurationRequest,
        models.StdinRequest,
        models.SuccessResponse,
        models.SuccessResponse,
        models.UpdateCellConfigRequest,
        models.NotebookDocumentTransactionRequest,
        models.FocusCellRequest,
        models.UpdateUIElementValuesRequest,
        models.UpdateUIElementRequest,
        models.UpdateUserConfigRequest,
        models.ModelRequest,
        models.ValidateSQLRequest,
    ]

    # Hack to get the unions to be included in the schema
    class KnownUnions(msgspec.Struct):
        notification: NotificationMessage
        command: CommandMessage
        error: MarimoError
        data_type: DataType

    _defs, component_schemas = msgspec.json.schema_components(
        MODELS + [KnownUnions],
        ref_template="#/components/schemas/{name}",
    )

    _enrich_branded_types(component_schemas, MODELS)

    schemas_generator = SchemaGenerator(
        {
            "openapi": "3.1.0",
            "info": {"title": "marimo API"},
            "components": {
                "schemas": component_schemas,
            },
        }
    )

    return schemas_generator.get_schema(routes=build_routes())


@click.group(
    cls=ColoredGroup,
    help="""Various commands for the marimo development.""",
    hidden=True,
)
def development() -> None:
    pass


@click.command(cls=ColoredCommand, help="""Print the marimo OpenAPI schema""")
def openapi() -> None:
    """
    Example usage:

        marimo development openapi
    """
    import yaml

    click.echo(
        yaml.dump(_generate_server_api_schema(), default_flow_style=False)
    )


@click.group(
    cls=ColoredGroup,
    help="Various commands for the marimo processes",
    hidden=True,
)
def ps() -> None:
    pass


def get_marimo_processes() -> list[psutil.Process]:
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
    from marimo._cli.print import orange

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

    for proc in get_marimo_processes():
        # Ignore self
        if proc.pid == os.getpid():
            continue
        proc.kill()
        click.echo(f"Killed process {proc.pid}")

    click.echo("Killed all marimo processes")


@click.command(
    cls=ColoredCommand,
    help="Inline packages according to PEP 723",
    name="inline-packages",
)
@click.argument(
    "name",
    required=True,
    type=click.Path(
        path_type=Path, exists=True, file_okay=True, dir_okay=False
    ),
)
def inline_packages(name: Path) -> None:
    """
    Example usage:

        marimo development inline-packages

    This uses some heuristics to guess the package names from the imports in
    the file.

    Requires uv.
    Installation: https://docs.astral.sh/uv/getting-started/installation/
    """
    from marimo._dependencies.dependencies import DependencyManager
    from marimo._runtime.packages.module_name_to_pypi_name import (
        module_name_to_pypi_name,
    )

    # Validate uv is installed
    if not DependencyManager.which("uv"):
        raise MarimoCLIMissingDependencyError(
            "uv is not installed.",
            "uv",
            additional_tip=(
                "See https://docs.astral.sh/uv/getting-started/installation/"
            ),
        )

    # Validate the file exists
    if not name.exists():
        raise click.FileError(str(name))

    package_names = module_name_to_pypi_name()

    def get_pypi_package_names() -> list[str]:
        tree = ast.parse(name.read_text(encoding="utf-8"), filename=name)

        imported_modules = set[str]()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
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
            str(name),
        ]
        + pypi_names
    )


@click.command(cls=ColoredCommand, help="Print all routes")
def print_routes() -> None:
    from starlette.applications import Starlette
    from starlette.routing import Mount, Route, Router

    from marimo._server.main import create_starlette_app

    app = create_starlette_app(base_url="")

    def print_all_routes(app: Any, base_path: str = "") -> None:
        if not isinstance(app, (Starlette, Router)):
            return
        for route in app.routes:
            if isinstance(route, Route) and route.methods is not None:
                full_path = base_path + route.path
                for method in route.methods:
                    if method == "HEAD":
                        continue
                    click.echo(f"{method} {full_path}")
            elif isinstance(route, Mount) and route.app is not None:
                # Recursively append base path for mounted apps
                new_base_path = base_path + route.path
                print_all_routes(route.app, new_base_path)

    print_all_routes(app)
    return


@click.command(cls=ColoredCommand, help="Preview a marimo file as static HTML")
@click.argument(
    "file_path",
    required=True,
    type=click.Path(
        path_type=Path, exists=True, file_okay=True, dir_okay=False
    ),
)
@click.option(
    "--port",
    default=8080,
    help="Port to serve the preview on",
    type=int,
)
@click.option(
    "--host",
    default="localhost",
    help="Host to serve the preview on",
    type=str,
)
@click.option(
    "--headless",
    is_flag=True,
    default=False,
    help="Don't automatically open the browser",
)
def preview(file_path: Path, port: int, host: str, headless: bool) -> None:
    """
    Preview a marimo file as static HTML.

    Creates a static HTML export of the marimo file and serves it
    on a simple HTTP server for preview purposes.

    Example usage:
        marimo development preview my_notebook.py
        marimo development preview my_notebook.py --port 8000
    """
    import threading
    import webbrowser

    import uvicorn
    from starlette.applications import Starlette
    from starlette.responses import HTMLResponse
    from starlette.routing import Route
    from starlette.staticfiles import StaticFiles

    from marimo._ast.app_config import _AppConfig
    from marimo._config.config import DEFAULT_CONFIG
    from marimo._server.templates.templates import static_notebook_template
    from marimo._server.tokens import SkewProtectionToken
    from marimo._utils.paths import marimo_package_path

    if TYPE_CHECKING:
        from starlette.requests import Request

    try:
        # Run the notebook to get actual outputs
        click.echo(f"Running notebook {file_path.name}...")
        from marimo._server.export import run_app_until_completion
        from marimo._server.utils import asyncio_run
        from marimo._session.notebook import load_notebook
        from marimo._session.state.serialize import (
            serialize_notebook,
            serialize_session_view,
        )
        from marimo._utils.code import hash_code

        # Create file manager for the notebook
        file_manager = load_notebook(file_path)

        # Run the notebook to completion and get session view
        session_view, did_error = asyncio_run(
            run_app_until_completion(
                file_manager,
                cli_args={},
                argv=None,
            )
        )
        if did_error:
            click.echo(
                "Warning: Some cells had errors during execution", err=True
            )

        # Create session snapshot from the executed session
        session_snapshot = serialize_session_view(
            session_view,
            cell_ids=list(file_manager.app.cell_manager.cell_ids()),
            drop_virtual_file_outputs=False,
        )

        # Get notebook snapshot from file manager
        notebook_snapshot = serialize_notebook(
            session_view, file_manager.app.cell_manager
        )

        # Get the static assets directory
        static_root = marimo_package_path() / "_static"

        # Get base HTML template
        template_path = static_root / "index.html"

        html_template = template_path.read_text(encoding="utf-8")

        # Use local assets instead of CDN
        asset_url = f"http://{host}:{port}"
        code = file_path.read_text(encoding="utf-8")

        # Generate static HTML
        html_content = static_notebook_template(
            html=html_template,
            user_config=DEFAULT_CONFIG,
            config_overrides={},
            server_token=SkewProtectionToken("preview"),
            app_config=_AppConfig(),
            filepath=str(file_path),
            code=code,
            session_snapshot=session_snapshot,
            code_hash=hash_code(code),
            notebook_snapshot=notebook_snapshot,
            files={},
            model_notifications=session_view.get_model_notifications(),
            asset_url=asset_url,
        )

        click.echo(f"Creating preview for {file_path.name}")

        async def serve_html(request: Request) -> HTMLResponse:
            del request
            return HTMLResponse(html_content)

        # Create Starlette app
        app = Starlette(
            routes=[
                Route("/", serve_html),
                Route("/index.html", serve_html),
            ]
        )

        # Mount static files for assets
        app.mount(
            "/assets",
            StaticFiles(directory=static_root / "assets"),
            name="assets",
        )

        # Mount other static files (favicon, icons, manifest, etc.)
        app.mount(
            "/",
            StaticFiles(directory=static_root, html=False),
            name="static",
        )

        url = f"http://{host}:{port}"
        click.echo(f"Serving preview at {url}")
        click.echo("Press Ctrl+C to stop the server")

        # Open browser if requested
        if not headless:

            def open_browser() -> None:
                webbrowser.open(url)

            timer = threading.Timer(1.0, open_browser)
            timer.start()

        # Run the server
        uvicorn.run(app, host=host, port=port, log_level="error")

    except Exception as e:
        raise MarimoCLIRuntimeError(f"Error creating preview: {e}") from e


development.add_command(inline_packages)
development.add_command(openapi)
development.add_command(ps)
development.add_command(print_routes)
development.add_command(preview)
