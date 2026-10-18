# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

import msgspec
import msgspec.json

from marimo._data.models import DataType
from marimo._messaging.errors import Error as MarimoError
from marimo._messaging.notification import NotificationMessage
from marimo._runtime.commands import ClientCommand


def _generate_schema_components(
    roots: list[object], named_exports: dict[str, object]
) -> dict[str, Any]:
    """Generate named exports and their dependencies, preserving brands."""
    types = [*roots, *named_exports.values()]
    schemas, components = msgspec.json.schema_components(
        types, ref_template="#/components/schemas/{name}"
    )
    _enrich_branded_types(components, types)
    for name, schema in zip(named_exports, schemas[len(roots) :]):
        if name in components:
            if schema == {"$ref": f"#/components/schemas/{name}"}:
                continue
            raise ValueError(
                f"Schema export {name!r} conflicts with a generated schema"
            )
        components[name] = schema
    return components


def _enrich_branded_types(
    component_schemas: dict[str, Any],
    models: list[object],
) -> None:
    """Post-process schemas to replace NewType string fields with $ref
    branded types.

    msgspec.json.schema_components() strips NewType wrappers, emitting plain
    `{type: string}` for fields like `CellId_t`. This function:

    1. Adds named schemas for each branded type (e.g. `CellId: {type: string}`).
    2. Walks every model struct's type hints and replaces inline schemas with
       `$ref` pointers wherever a field's annotation is (or contains) a
       registered NewType.
    """
    import types as _types
    import typing
    from typing import Union

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
        """Produce a branded schema for *ty*, or `None`."""
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

    # Step 2 — collect *all* reachable struct types (not just roots,
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
        _visit_annotation(model)

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
        # Some models contain references that cannot be resolved here.
        except Exception:  # noqa: S112
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


def generate_server_api_schema() -> dict[str, Any]:
    from starlette.schemas import SchemaGenerator

    import marimo._data._external_storage.models as storage
    import marimo._data.models as data
    import marimo._secrets.models as secrets_models
    from marimo._ai._types import ChatMessage
    from marimo._ast.cell import CellConfig, RuntimeStateType
    from marimo._config import config
    from marimo._messaging.cell_output import CellChannel, CellOutput
    from marimo._messaging.mimetypes import KnownMimeType
    from marimo._metadata import opengraph
    from marimo._runtime.packages.package_manager import PackageDescription
    from marimo._schemas import export
    from marimo._server.ai.tools.types import ToolDefinition
    from marimo._server.api.router import build_routes
    from marimo._server.models import (
        completion,
        files,
        home,
        lsp,
        models,
        packages,
        secrets,
    )
    from marimo._session import requests as session_requests
    from marimo._snippets import snippets

    roots = [
        # Base
        RuntimeStateType,
        KnownMimeType,
        CellChannel,
        data.NonNestedLiteral,
        CellConfig,
        config.OpenAiConfig,
        config.AnthropicConfig,
        config.GitHubConfig,
        config.GoogleAiConfig,
        config.BedrockConfig,
        config.AiConfig,
        config.MarimoConfig,
        config.StoreConfig,
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
        # ai
        ChatMessage,
        ToolDefinition,
        # Sub components
        home.MarimoFile,
        opengraph.OpenGraphMetadata,
        files.FileInfo,
        files.FileRoot,
        snippets.SnippetSection,
        snippets.Snippet,
        snippets.Snippets,
        # Requests/responses
        completion.VariableContext,
        completion.SchemaColumn,
        completion.SchemaTable,
        completion.AiCompletionContext,
        completion.AiCompletionRequest,
        completion.AiInlineCompletionRequest,
        completion.ChatRequest,
        export.AutoExportAsIPYNBRequest,
        export.AutoExportAsMarkdownRequest,
        export.ExportAsHTMLRequest,
        export.ExportAsMarkdownRequest,
        export.ExportAsScriptRequest,
        export.ExportAsIPYNBRequest,
        export.ExportAsPDFRequest,
        export.ExportAvailabilityResponse,
        export.InstallExportRequirementsRequest,
        export.UpdateCellOutputsRequest,
        files.FileCreateMultipartRequest,
        files.FileCreateRequest,
        files.FileCreateResponse,
        files.FileDeleteRequest,
        files.FileDeleteResponse,
        files.FileDetailsRequest,
        files.FileDetailsResponse,
        files.FileListRequest,
        files.FileListResponse,
        files.FileRootsResponse,
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
        packages.SandboxRequest,
        packages.SandboxResponse,
        packages.UpdateManifestRequest,
        packages.SyncSandboxResponse,
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
        models.BaseResponse,
        models.ClearCacheRequest,
        models.CodeCompletionRequest,
        models.CopyNotebookRequest,
        models.DebugCellRequest,
        models.DeleteCellRequest,
        models.DiscoverDataSourcesRequest,
        models.ExecuteScratchpadRequest,
        models.FormatCellsRequest,
        models.FormatResponse,
        models.GetCacheInfoRequest,
        models.InstallPackagesRequest,
        session_requests.InstantiateNotebookRequest,
        models.InvokeAiToolRequest,
        models.InvokeAiToolResponse,
        models.InvokeFunctionRequest,
        models.KernelStatusResponse,
        models.ListDataSourceConnectionRequest,
        models.ListSecretKeysRequest,
        models.ListSQLTablesRequest,
        models.ListSQLSchemasRequest,
        models.MCPRefreshResponse,
        models.MCPStatusResponse,
        models.PreviewDatasetColumnRequest,
        models.PreviewSQLTableRequest,
        models.SetBreakpointsRequest,
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
        models.UpdateCellConfigRequest,
        models.NotebookDocumentTransactionRequest,
        models.FocusCellRequest,
        session_requests.UpdateUIElementValuesRequest,
        models.UpdateUIElementRequest,
        models.UpdateUserConfigRequest,
        models.ModelRequest,
        models.ValidateSQLRequest,
    ]

    named_exports = {
        "NotificationMessage": NotificationMessage,
        "ClientCommand": ClientCommand,
        "MarimoError": MarimoError,
        "DataType": DataType,
    }
    component_schemas = _generate_schema_components(roots, named_exports)

    # Preserve existing consumers while they migrate to the named exports.
    legacy_exports = {
        "notification": "NotificationMessage",
        "command": "ClientCommand",
        "error": "MarimoError",
        "data_type": "DataType",
    }
    component_schemas["KnownUnions"] = {
        "title": "KnownUnions",
        "type": "object",
        "properties": {
            field: {"$ref": f"#/components/schemas/{name}"}
            for field, name in legacy_exports.items()
        },
        "required": list(legacy_exports),
    }

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
