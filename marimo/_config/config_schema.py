# Copyright 2026 Marimo. All rights reserved.
"""Struct schema for configuration defaults and field metadata.

The dictionary interfaces in `config.py` remain in use during migration.
"""

from __future__ import annotations

import os
from typing import Annotated, Any, Literal

from msgspec import UNSET, Meta, UnsetType, field

from marimo._config.packages import infer_package_manager
from marimo._config.schema_utils import Config
from marimo._config.types import (
    CacheVerification,
    CopilotMode,
    ExecutionType,
    ExportType,
    OnCellChangeType,
    SqlOutputType,
    StoreKey,
    Theme,
    WidthType,
)


class CompletionConfig(Config, kw_only=True):
    """Configuration for code completion.

    Settings for code completion in the marimo editor."""

    activate_on_typing: Annotated[
        bool,
        Meta(
            description="if `False`, completion won't activate until the completion hotkey is entered"
        ),
    ] = True
    signature_hint_on_typing: Annotated[
        bool,
        Meta(
            description="if `False`, signature hint won't be shown when typing"
        ),
    ] = False
    copilot: Annotated[
        bool | Literal["github", "codeium", "custom"],
        Meta(description='one of `"github"`, `"codeium"`, or `"custom"`'),
    ] = False
    auto_close_pairs: Annotated[
        bool,
        Meta(
            description="if `False`, typing an opening bracket, parenthesis, or quote will not automatically insert the closing character"
        ),
    ] = True
    codeium_api_key: Annotated[
        str | UnsetType | None,
        Meta(description="the Codeium API key", extra={"sensitive": True}),
    ] = UNSET
    api_key: Annotated[
        str | UnsetType | None,
        Meta(
            description="Deprecated completion API key. Use an AI provider configuration instead.",
            extra={"sensitive": True, "deprecated": True},
            extra_json_schema={"deprecated": True},
        ),
    ] = UNSET
    model: Annotated[
        str | UnsetType | None,
        Meta(
            description="Deprecated completion model. Use ai.models.autocomplete_model instead.",
            extra={"deprecated": True},
            extra_json_schema={"deprecated": True},
        ),
    ] = UNSET
    base_url: Annotated[
        str | UnsetType | None,
        Meta(
            description="Deprecated completion API endpoint. Use an AI provider configuration instead.",
            extra={"deprecated": True},
            extra_json_schema={"deprecated": True},
        ),
    ] = UNSET


class SaveConfig(Config, kw_only=True):
    """Configuration for saving."""

    autosave: Annotated[
        Literal["off", "after_delay"],
        Meta(description='one of `"off"` or `"after_delay"`'),
    ] = "after_delay"
    autosave_delay: Annotated[
        int,
        Meta(description="Delay in milliseconds before automatically saving."),
    ] = 1000
    format_on_save: Annotated[
        bool, Meta(description="if `True`, format the code on save")
    ] = False


class KeymapConfig(Config, kw_only=True):
    """Configuration for keymaps."""

    preset: Annotated[
        Literal["default", "vim"],
        Meta(description='one of `"default"` or `"vim"`'),
    ] = "default"
    overrides: Annotated[
        dict[str, str],
        Meta(description="a dict of keymap actions to their keymap override"),
    ] = field(default_factory=dict)
    vimrc: Annotated[
        str | UnsetType | None,
        Meta(description="path to a vimrc file to load keymaps from"),
    ] = UNSET
    destructive_delete: Annotated[
        bool | UnsetType,
        Meta(description="if `True`, allows deleting cells with content."),
    ] = UNSET


class VenvConfig(Config, kw_only=True):
    """Configuration for an external Python environment in edit mode.

    Launches the notebook kernel in an existing virtualenv. Applies to
    single notebooks and directories when editing without `--sandbox`."""

    path: Annotated[
        str | UnsetType,
        Meta(
            description="path to a virtualenv directory (absolute or relative to pyproject.toml)"
        ),
    ] = UNSET
    writable: Annotated[
        bool | UnsetType,
        Meta(
            description="if true, marimo will manage script metadata (inline dependencies). Defaults to false."
        ),
    ] = UNSET


class RuntimeConfig(Config, kw_only=True):
    """Configuration for runtime."""

    auto_instantiate: Annotated[
        bool,
        Meta(
            description="if `False`, cells won't automatically run on startup. This only applies when editing a notebook, and not when running as an application."
        ),
    ] = False
    auto_reload: Annotated[
        Literal["off", "lazy", "autorun"],
        Meta(
            description="If `lazy`, mark cells importing modified modules as stale; if `autorun`, automatically run affected cells. Similar to IPython's %autoreload extension, with dependency-aware execution."
        ),
    ] = "off"
    reactive_tests: Annotated[
        bool,
        Meta(
            description="If `True`, automatically run pytest on cells containing only test functions and test classes."
        ),
    ] = True
    on_cell_change: Annotated[
        OnCellChangeType,
        Meta(
            description="if `lazy`, cells will be marked stale when their ancestors run but won't autorun; if `autorun`, cells will automatically run when their ancestors run."
        ),
    ] = "autorun"
    watcher_on_save: Annotated[
        Literal["lazy", "autorun"],
        Meta(
            description='how to handle file changes when saving. `"lazy"` marks affected cells as stale, `"autorun"` automatically runs affected cells.'
        ),
    ] = "lazy"
    output_max_bytes: Annotated[
        int,
        Meta(
            description="the maximum size in bytes of cell outputs; larger values may affect frontend performance"
        ),
    ] = field(
        default_factory=lambda: int(
            os.getenv("MARIMO_OUTPUT_MAX_BYTES", "8000000")
        )
    )
    serve_cached_sessions_in_apps: Annotated[
        bool | UnsetType,
        Meta(
            description="if `True`, initialize applications with session cache."
        ),
    ] = UNSET
    std_stream_max_bytes: Annotated[
        int,
        Meta(
            description="the maximum size in bytes of console outputs; larger values may affect frontend performance"
        ),
    ] = field(
        default_factory=lambda: int(
            os.getenv("MARIMO_STD_STREAM_MAX_BYTES", "1000000")
        )
    )
    pythonpath: Annotated[
        list[str] | UnsetType,
        Meta(
            description="a list of directories to add to the Python search path. Directories will be added to the head of sys.path. Similar to the `PYTHONPATH` environment variable, the directories will be included in where Python will look for imported modules."
        ),
    ] = UNSET
    dotenv: Annotated[
        list[str] | UnsetType,
        Meta(
            description="a list of paths to `.env` files to load. If the file does not exist, it will be silently ignored. Relative paths resolve against the directory holding the `pyproject.toml`, or the notebook's directory when there is none.",
            extra={"sensitive": True},
        ),
    ] = UNSET
    default_sql_output: Annotated[
        SqlOutputType,
        Meta(
            description='the default output format for SQL queries. Can be one of: `"auto"`, `"native"`, `"polars"`, `"lazy-polars"`, or `"pandas"`.'
        ),
    ] = "auto"
    default_auto_download: Annotated[
        list[ExportType] | UnsetType,
        Meta(
            description="an Optional list of export types to automatically snapshot your notebook as: `html`, `markdown`, `ipynb`."
        ),
    ] = UNSET
    default_csv_encoding: Annotated[
        str, Meta(description="the default encoding for CSV exports.")
    ] = "utf-8"
    show_tracebacks: Annotated[
        bool,
        Meta(
            description="if `True`, show detailed error tracebacks in run mode. When enabled, exceptions will display a clickable toast that opens a modal with the full traceback."
        ),
    ] = False
    execution_type: Annotated[
        ExecutionType | UnsetType,
        Meta(description="Cell declaration handling: relaxed or strict."),
    ] = UNSET
    cache_cells: Annotated[
        bool | UnsetType,
        Meta(description="Enable experimental automatic cell caching."),
    ] = UNSET
    pin_modules: Annotated[
        bool | UnsetType,
        Meta(description="Pin imported modules when caching cells."),
    ] = UNSET


class DisplayConfig(Config, kw_only=True):
    """Configuration for display."""

    theme: Annotated[
        Theme, Meta(description='`"light"`, `"dark"`, or `"system"`')
    ] = "light"
    code_editor_font_size: Annotated[
        int, Meta(description="font size for the code editor")
    ] = 14
    cell_output: Annotated[
        Literal["above", "below"], Meta(description='`"above"` or `"below"`')
    ] = "below"
    default_width: Annotated[
        WidthType, Meta(description="Default notebook width.")
    ] = "medium"
    dataframes: Annotated[
        Literal["rich", "plain"], Meta(description='`"rich"` or `"plain"`')
    ] = "rich"
    custom_css: Annotated[
        list[str] | UnsetType,
        Meta(description="list of paths to custom CSS files"),
    ] = UNSET
    default_table_page_size: Annotated[
        int, Meta(description="default number of rows to display in tables")
    ] = 10
    default_table_max_columns: Annotated[
        int,
        Meta(
            description="default maximum number of columns to display in tables"
        ),
    ] = 50
    reference_highlighting: Annotated[
        bool,
        Meta(description="if `True`, highlight reactive variable references"),
    ] = True
    code_lens: Annotated[
        bool,
        Meta(
            description="if `True`, show inline icons in cell editors linking datasources, storage buckets, and caches to their panels"
        ),
    ] = True
    locale: Annotated[
        str | UnsetType | None,
        Meta(
            description='locale for date formatting and internationalization (e.g., "en-US", "en-GB", "de-DE")'
        ),
    ] = UNSET


class FormattingConfig(Config, kw_only=True):
    """Configuration for code formatting."""

    line_length: Annotated[int, Meta(description="max line length")] = 79


class ServerConfig(Config, kw_only=True):
    """Configuration for the server."""

    browser: Annotated[
        Literal["default"] | str,
        Meta(
            description='the web browser to use. `"default"` or a browser registered with Python\'s webbrowser module (eg, `"firefox"` or `"chrome"`)'
        ),
    ] = "default"
    follow_symlink: Annotated[
        bool,
        Meta(
            description="if true, the server will follow symlinks it finds inside its static assets directory."
        ),
    ] = False
    disable_file_downloads: Annotated[
        bool | UnsetType,
        Meta(
            description="if true, the file download button will be hidden in the file explorer."
        ),
    ] = UNSET
    transport: Annotated[
        Literal["websocket", "sse"] | UnsetType,
        Meta(
            description='experimental. The transport used to stream kernel messages to the frontend, typically set with the `MARIMO_SERVER_TRANSPORT` environment variable. `"websocket"` (default) uses the `/ws` WebSocket endpoint; `"sse"` uses server-sent events over HTTP, for deployments behind proxies or services that do not support WebSockets. Terminal, LSP, and real-time collaboration still require WebSockets; RTC is disabled when using `"sse"`.'
        ),
    ] = UNSET


class PackageManagementConfig(Config, kw_only=True):
    """Configuration options for package management."""

    manager: Annotated[
        Literal["pip", "rye", "uv", "poetry", "pixi"],
        Meta(description="the package manager to use"),
    ] = field(default_factory=infer_package_manager)


class AiModelConfig(Config, kw_only=True):
    """Configuration options for an AI model."""

    chat_model: Annotated[
        str | UnsetType | None,
        Meta(description="the model to use for chat completions"),
    ] = UNSET
    edit_model: Annotated[
        str | UnsetType | None,
        Meta(description="the model to use for edit completions"),
    ] = UNSET
    autocomplete_model: Annotated[
        str | UnsetType | None,
        Meta(description="the model to use for code completion/autocomplete"),
    ] = UNSET
    displayed_models: Annotated[
        list[str], Meta(description="a list of models to display in the UI")
    ] = field(default_factory=list)
    custom_models: Annotated[
        list[str],
        Meta(
            description="a list of custom models to use that are not from the default list"
        ),
    ] = field(default_factory=list)


class AiConfig(Config, kw_only=True):
    """Configuration options for AI."""

    enabled: Annotated[
        bool,
        Meta(
            description="if `False`, hide AI actions and panels in the marimo UI"
        ),
    ] = True
    rules: Annotated[
        str | UnsetType,
        Meta(
            description="custom rules to include in all AI completion prompts"
        ),
    ] = UNSET
    max_tokens: Annotated[
        int | UnsetType | None,
        Meta(
            description="the maximum number of tokens to use in AI completions"
        ),
    ] = UNSET
    mode: Annotated[
        CopilotMode | UnsetType,
        Meta(
            description='the mode to use for AI completions. Can be one of: `"ask"` or `"manual"`'
        ),
    ] = UNSET
    inline_tooltip: Annotated[
        bool | UnsetType,
        Meta(description="if `True`, enable inline AI tooltip suggestions"),
    ] = UNSET
    allow_provider_config: Annotated[
        bool,
        Meta(
            description="if `False`, lock provider setup in the settings UI, making them read-only. Users cannot bring their own credentials or add custom providers. Default `True`."
        ),
    ] = True
    models: Annotated[
        AiModelConfig, Meta(description="the models to use for AI completions")
    ] = field(default_factory=AiModelConfig)
    open_ai: Annotated[
        OpenAiConfig | UnsetType, Meta(description="the OpenAI config")
    ] = UNSET
    anthropic: Annotated[
        AnthropicConfig | UnsetType, Meta(description="the Anthropic config")
    ] = UNSET
    google: Annotated[
        GoogleAiConfig | UnsetType, Meta(description="the Google AI config")
    ] = UNSET
    bedrock: Annotated[
        BedrockConfig | UnsetType, Meta(description="the Bedrock config")
    ] = UNSET
    azure: Annotated[
        OpenAiConfig | UnsetType, Meta(description="the Azure config")
    ] = UNSET
    ollama: Annotated[
        OpenAiConfig | UnsetType, Meta(description="the Ollama config")
    ] = UNSET
    github: Annotated[
        GitHubConfig | UnsetType, Meta(description="the GitHub Copilot config")
    ] = UNSET
    openrouter: Annotated[
        OpenAiConfig | UnsetType, Meta(description="the OpenRouter config")
    ] = UNSET
    wandb: Annotated[
        OpenAiConfig | UnsetType,
        Meta(description="the Weights & Biases config"),
    ] = UNSET
    opencode_go: Annotated[
        OpenAiConfig | UnsetType, Meta(description="the OpenCode Go config")
    ] = UNSET
    custom_providers: Annotated[
        dict[str, OpenAiConfig],
        Meta(description="a dict of custom OpenAI-compatible providers"),
    ] = field(default_factory=dict)
    open_ai_compatible: Annotated[
        OpenAiConfig | UnsetType,
        Meta(
            description="the OpenAI-compatible config (deprecated, use custom_providers)",
            extra={"deprecated": True},
            extra_json_schema={"deprecated": True},
        ),
    ] = UNSET


class OpenAiConfig(Config, kw_only=True):
    """Configuration options for OpenAI or OpenAI-compatible services."""

    api_key: Annotated[
        str | UnsetType,
        Meta(
            description="the OpenAI API key or an `env:` reference",
            extra={"sensitive": True},
        ),
    ] = UNSET
    base_url: Annotated[
        str | UnsetType, Meta(description="the base URL for the API")
    ] = UNSET
    project: Annotated[
        str | UnsetType, Meta(description="the project ID for the OpenAI API")
    ] = UNSET
    ssl_verify: Annotated[
        bool | UnsetType,
        Meta(
            description="Whether to verify TLS certificates for the API client."
        ),
    ] = UNSET
    ca_bundle_path: Annotated[
        str | UnsetType,
        Meta(
            description="custom ca bundle to be used for verifying SSL certificates. Used to create custom SSL context for httpx client"
        ),
    ] = UNSET
    client_pem: Annotated[
        str | UnsetType,
        Meta(
            description="Path to a client PEM certificate for authenticating API requests."
        ),
    ] = UNSET
    extra_headers: Annotated[
        dict[str, str] | UnsetType,
        Meta(description="extra headers to be passed to the OpenAI client"),
    ] = UNSET
    model: Annotated[
        str | UnsetType,
        Meta(
            description="Deprecated chat model. Use ai.models.chat_model instead.",
            extra={"deprecated": True},
            extra_json_schema={"deprecated": True},
        ),
    ] = UNSET


class AnthropicConfig(Config, kw_only=True):
    """Configuration options for Anthropic."""

    api_key: Annotated[
        str | UnsetType,
        Meta(
            description="the Anthropic API key or an `env:` reference",
            extra={"sensitive": True},
        ),
    ] = UNSET


class GoogleAiConfig(Config, kw_only=True):
    """Configuration options for Google AI."""

    api_key: Annotated[
        str | UnsetType,
        Meta(
            description="the Google AI API key or an `env:` reference",
            extra={"sensitive": True},
        ),
    ] = UNSET


class BedrockConfig(Config, kw_only=True):
    """Configuration options for Bedrock."""

    profile_name: Annotated[
        str | UnsetType, Meta(description="the AWS profile to use")
    ] = UNSET
    region_name: Annotated[
        str | UnsetType, Meta(description="the AWS region to use")
    ] = UNSET
    aws_access_key_id: Annotated[
        str | UnsetType,
        Meta(description="the AWS access key ID", extra={"sensitive": True}),
    ] = UNSET
    aws_secret_access_key: Annotated[
        str | UnsetType,
        Meta(
            description="the AWS secret access key", extra={"sensitive": True}
        ),
    ] = UNSET


class GitHubConfig(Config, kw_only=True):
    """Configuration options for GitHub Copilot."""

    api_key: Annotated[
        str | UnsetType,
        Meta(
            description="a GitHub Copilot token or an `env:` reference",
            extra={"sensitive": True},
        ),
    ] = UNSET
    base_url: Annotated[
        str | UnsetType,
        Meta(description="the base URL for the GitHub Copilot API"),
    ] = UNSET
    copilot_settings: Annotated[
        dict[str, Any] | UnsetType,
        Meta(
            description="configuration settings for GitHub Copilot LSP. Supports settings like `http` (proxy configuration), `telemetry`, and `github-enterprise` (enterprise URI)."
        ),
    ] = UNSET


class PythonLanguageServerConfig(Config, kw_only=True):
    """Configuration options for Python Language Server.

    pylsp handles completion, hover, go-to-definition, and diagnostics."""

    enabled: Annotated[
        bool, Meta(description="Enable this language server.")
    ] = False
    enable_mypy: Annotated[
        bool, Meta(description="Enable mypy diagnostics in pylsp.")
    ] = True
    enable_ruff: Annotated[
        bool, Meta(description="Enable ruff diagnostics in pylsp.")
    ] = True
    enable_flake8: Annotated[
        bool, Meta(description="Enable flake8 diagnostics in pylsp.")
    ] = False
    enable_pydocstyle: Annotated[
        bool, Meta(description="Enable pydocstyle diagnostics in pylsp.")
    ] = False
    enable_pylint: Annotated[
        bool, Meta(description="Enable pylint diagnostics in pylsp.")
    ] = False
    enable_pyflakes: Annotated[
        bool, Meta(description="Enable pyflakes diagnostics in pylsp.")
    ] = False


class BasedpyrightServerConfig(Config, kw_only=True):
    """Configuration options for basedpyright Language Server.

    basedpyright handles completion, hover, go-to-definition, and diagnostics,
    but we only use it for diagnostics."""

    enabled: Annotated[
        bool | UnsetType, Meta(description="Enable this language server.")
    ] = UNSET


class TyLanguageServerConfig(Config, kw_only=True):
    """Configuration options for Ty Language Server.

    ty handles completion, hover, go-to-definition, and diagnostics,
    but we only use it for diagnostics."""

    enabled: Annotated[
        bool | UnsetType, Meta(description="Enable this language server.")
    ] = UNSET


class PyreflyLanguageServerConfig(Config, kw_only=True):
    """Configuration options for Pyrefly Language Server.

    Pyrefly handles completion, hover, go-to-definition, and diagnostics."""

    enabled: Annotated[
        bool | UnsetType, Meta(description="Enable this language server.")
    ] = UNSET


class LanguageServersConfig(Config, kw_only=True):
    """Configuration options for language servers."""

    pylsp: Annotated[
        PythonLanguageServerConfig, Meta(description="the pylsp config")
    ] = field(default_factory=PythonLanguageServerConfig)
    basedpyright: Annotated[
        BasedpyrightServerConfig | UnsetType,
        Meta(description="the basedpyright config"),
    ] = UNSET
    ty: Annotated[
        TyLanguageServerConfig | UnsetType, Meta(description="the ty config")
    ] = UNSET
    pyrefly: Annotated[
        PyreflyLanguageServerConfig | UnsetType,
        Meta(description="the pyrefly config"),
    ] = UNSET


class DiagnosticsConfig(Config, kw_only=True):
    """Configuration options for diagnostics."""

    enabled: Annotated[
        bool | UnsetType,
        Meta(description="if `True`, diagnostics will be shown in the editor"),
    ] = UNSET
    sql_linter: Annotated[
        bool,
        Meta(description="if `True`, SQL cells will have linting enabled"),
    ] = True


class LintConfig(Config, kw_only=True):
    """Configuration for lint rule selection.

    Follows ruff-inspired semantics for selecting which rules to run
    during `marimo check`."""

    select: Annotated[
        list[str] | UnsetType,
        Meta(
            description='list of rule code prefixes that replaces the default enabled set. Use `"ALL"` to select all rules. Example: `["MB", "MR001"]`'
        ),
    ] = UNSET
    ignore: Annotated[
        list[str] | UnsetType,
        Meta(
            description="list of rule code prefixes to remove from the enabled set."
        ),
    ] = UNSET


class SnippetsConfig(Config, kw_only=True):
    """Configuration for snippets."""

    custom_paths: Annotated[
        list[str],
        Meta(description="Paths to directories containing custom snippets."),
    ] = field(default_factory=list)
    include_default_snippets: Annotated[
        bool, Meta(description="Include the built-in snippets.")
    ] = True


class DatasourcesConfig(Config, kw_only=True):
    """Configuration for datasources panel."""

    auto_discover_schemas: Annotated[
        bool | Literal["auto"] | UnsetType,
        Meta(description="if `True`, include schemas in the datasource"),
    ] = UNSET
    auto_discover_tables: Annotated[
        bool | Literal["auto"] | UnsetType,
        Meta(description="if `True`, include tables in the datasource"),
    ] = UNSET
    auto_discover_columns: Annotated[
        bool | Literal["auto"] | UnsetType,
        Meta(
            description="if `True`, include columns & table metadata in the datasource"
        ),
    ] = UNSET


class FolderConfig(Config, kw_only=True):
    """Configuration for an additional file browser root."""

    path: Annotated[str, Meta(description="the absolute path to the folder")]
    name: Annotated[
        str | UnsetType,
        Meta(description="an optional display name for the folder"),
    ] = UNSET


class FileBrowserConfig(Config, kw_only=True):
    """Configuration for the file browser panel."""

    folders: Annotated[
        list[FolderConfig] | UnsetType,
        Meta(
            description="additional absolute folders to show in the file browser"
        ),
    ] = UNSET


class SharingConfig(Config, kw_only=True):
    """Configuration for sharing features."""

    html: Annotated[
        bool | UnsetType,
        Meta(
            description="if `False`, HTML sharing options will be hidden from the UI"
        ),
    ] = UNSET
    wasm: Annotated[
        bool | UnsetType,
        Meta(
            description="if `False`, WebAssembly sharing options will be hidden from the UI"
        ),
    ] = UNSET
    molab: Annotated[
        bool | UnsetType,
        Meta(
            description="if `False`, molab sharing options will be hidden from the UI"
        ),
    ] = UNSET


class StoreConfig(Config, kw_only=True):
    """Configuration for a single cache store."""

    type: Annotated[
        StoreKey | UnsetType, Meta(description="Cache store backend.")
    ] = UNSET
    args: Annotated[
        dict[str, Any] | UnsetType,
        Meta(
            description="Keyword arguments passed to the cache store constructor."
        ),
    ] = UNSET


CacheStoreConfig = list[StoreConfig] | StoreConfig


class CacheConfig(Config, kw_only=True):
    """Configuration for caching."""

    verification: Annotated[
        CacheVerification | UnsetType,
        Meta(
            description="Cache signature verification posture: off, on, or strict."
        ),
    ] = UNSET
    store: Annotated[
        CacheStoreConfig | UnsetType,
        Meta(
            description="Backing cache store, or a list of stores composed into a tiered store."
        ),
    ] = UNSET


class SigningConfig(Config, kw_only=True):
    """Cache-signing trust and identity."""

    trusted_signers: Annotated[
        dict[str, str] | UnsetType,
        Meta(
            description="Trusted key fingerprints (SHA256:<base64>) mapped to advisory labels. Trust permits code execution when restoring cached Python objects."
        ),
    ] = UNSET
    private_key_path: Annotated[
        str | UnsetType,
        Meta(
            description="Absolute path to this machine's private signing key. Not exposed to the frontend.",
            extra={"sensitive": True},
        ),
    ] = UNSET


class ExperimentalConfig(Config, kw_only=True):
    """Configuration for experimental features.

    Features exposed on the frontend must match the frontend config."""

    markdown: Annotated[
        bool | UnsetType,
        Meta(description="Enable experimental Markdown notebook features."),
    ] = UNSET
    wasm_layouts: Annotated[
        bool | UnsetType,
        Meta(
            description="Enable experimental layouts in WebAssembly notebooks."
        ),
    ] = UNSET
    rtc_v2: Annotated[
        bool | UnsetType, Meta(description="Enable real-time collaboration.")
    ] = UNSET
    isolate_apps: Annotated[
        bool | UnsetType,
        Meta(description="Run applications in separate processes."),
    ] = UNSET
    debugger: Annotated[
        bool | UnsetType,
        Meta(
            description="Enable live debugging with gutter breakpoints and pdb."
        ),
    ] = UNSET
    line_timing: Annotated[
        bool | UnsetType,
        Meta(
            description="Highlight the active line and show per-line execution timing."
        ),
    ] = UNSET
    execution_type: Annotated[
        ExecutionType | UnsetType,
        Meta(
            description="Experimental cell declaration handling: relaxed or strict."
        ),
    ] = UNSET


class MCPServerStdioConfig(
    Config, kw_only=True, tag="stdio", tag_field="__marimo_transport__"
):
    """Configuration for STDIO transport MCP servers"""

    command: Annotated[
        str, Meta(description="Command used to launch the MCP server.")
    ]
    args: Annotated[
        list[str] | UnsetType | None,
        Meta(description="Arguments passed to the MCP server command."),
    ] = UNSET
    env: Annotated[
        dict[str, str] | UnsetType | None,
        Meta(description="Environment variables supplied to the MCP server."),
    ] = UNSET
    disabled: Annotated[
        bool | UnsetType | None, Meta(description="Disable this MCP server.")
    ] = UNSET


class MCPServerStreamableHttpConfig(
    Config, kw_only=True, tag="http", tag_field="__marimo_transport__"
):
    """Configuration for Streamable HTTP transport MCP servers"""

    url: Annotated[
        str, Meta(description="URL of the streamable HTTP MCP server.")
    ]
    headers: Annotated[
        dict[str, str] | UnsetType | None,
        Meta(description="HTTP headers sent to the MCP server."),
    ] = UNSET
    timeout: Annotated[
        float | UnsetType | None,
        Meta(description="Timeout in seconds for MCP server requests."),
    ] = UNSET
    env: Annotated[
        dict[str, str] | UnsetType | None,
        Meta(
            description="Environment variables used by the MCP server configuration."
        ),
    ] = UNSET
    disabled: Annotated[
        bool | UnsetType | None, Meta(description="Disable this MCP server.")
    ] = UNSET


MCPServerConfig = MCPServerStdioConfig | MCPServerStreamableHttpConfig


class MCPConfig(Config, kw_only=True):
    """Configuration for MCP servers

    Note: the field name `mcpServers` is camelCased to match MCP server
    config conventions used by popular AI applications (e.g. Cursor, Claude Desktop, etc.)"""

    mcpServers: Annotated[
        dict[str, MCPServerConfig],
        Meta(description="Named MCP server configurations."),
    ] = field(default_factory=dict)
    presets: Annotated[
        list[Literal["marimo", "context7"]],
        Meta(description="Built-in MCP server presets to enable."),
    ] = field(default_factory=list)
    _mcp_path = ()


class MarimoConfig(Config, kw_only=True):
    """Configuration for the marimo editor"""

    completion: Annotated[
        CompletionConfig,
        Meta(description="Configuration for code completion."),
    ] = field(default_factory=CompletionConfig)
    display: Annotated[
        DisplayConfig, Meta(description="Configuration for display.")
    ] = field(default_factory=DisplayConfig)
    formatting: Annotated[
        FormattingConfig,
        Meta(description="Configuration for code formatting."),
    ] = field(default_factory=FormattingConfig)
    keymap: Annotated[
        KeymapConfig, Meta(description="Configuration for keymaps.")
    ] = field(default_factory=KeymapConfig)
    runtime: Annotated[
        RuntimeConfig, Meta(description="Configuration for runtime.")
    ] = field(default_factory=RuntimeConfig)
    save: Annotated[
        SaveConfig, Meta(description="Configuration for saving.")
    ] = field(default_factory=SaveConfig)
    server: Annotated[
        ServerConfig, Meta(description="Configuration for the server.")
    ] = field(default_factory=ServerConfig)
    package_management: Annotated[
        PackageManagementConfig,
        Meta(description="Configuration options for package management."),
    ] = field(default_factory=PackageManagementConfig)
    ai: Annotated[
        AiConfig, Meta(description="Configuration options for AI.")
    ] = field(default_factory=AiConfig)
    language_servers: Annotated[
        LanguageServersConfig,
        Meta(description="Configuration options for language servers."),
    ] = field(default_factory=LanguageServersConfig)
    diagnostics: Annotated[
        DiagnosticsConfig,
        Meta(description="Configuration options for diagnostics."),
    ] = field(default_factory=DiagnosticsConfig)
    lint: Annotated[
        LintConfig | UnsetType,
        Meta(description="Configuration for lint rule selection."),
    ] = UNSET
    experimental: Annotated[
        ExperimentalConfig | UnsetType,
        Meta(description="Configuration for experimental features."),
    ] = UNSET
    snippets: Annotated[
        SnippetsConfig, Meta(description="Configuration for snippets.")
    ] = field(default_factory=SnippetsConfig)
    datasources: Annotated[
        DatasourcesConfig | UnsetType,
        Meta(description="Configuration for datasources panel."),
    ] = UNSET
    file_browser: Annotated[
        FileBrowserConfig | UnsetType,
        Meta(description="Configuration for the file browser panel."),
    ] = UNSET
    sharing: Annotated[
        SharingConfig | UnsetType,
        Meta(description="Configuration for sharing features."),
    ] = UNSET
    mcp: Annotated[
        MCPConfig, Meta(description="Configuration for MCP servers")
    ] = field(default_factory=MCPConfig)
    venv: Annotated[
        VenvConfig | UnsetType,
        Meta(
            description="Configuration for an external Python environment in edit mode."
        ),
    ] = UNSET
    cache: Annotated[
        CacheConfig | UnsetType, Meta(description="Configuration for caching.")
    ] = UNSET
    signing: Annotated[
        SigningConfig | UnsetType,
        Meta(description="Cache-signing trust and identity."),
    ] = UNSET
    _mcp_path = ("mcp",)
