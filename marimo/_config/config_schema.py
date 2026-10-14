# Copyright 2026 Marimo. All rights reserved.
"""Dataclass schema for configuration defaults and field metadata.

The dictionary interfaces in `config.py` remain in use during migration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import (
    Any,
    Literal,
)

from msgspec import UNSET, UnsetType

from marimo._config.packages import infer_package_manager
from marimo._config.schema import Config
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


@dataclass(kw_only=True)
class CompletionConfig(Config):
    """Configuration for code completion.

    Settings for code completion in the marimo editor."""

    activate_on_typing: bool = field(
        default=True,
        metadata={
            "description": "if `False`, completion won't activate until the completion hotkey is entered"
        },
    )
    signature_hint_on_typing: bool = field(
        default=False,
        metadata={
            "description": "if `False`, signature hint won't be shown when typing"
        },
    )
    copilot: bool | Literal["github", "codeium", "custom"] = field(
        default=False,
        metadata={
            "description": 'one of `"github"`, `"codeium"`, or `"custom"`'
        },
    )
    auto_close_pairs: bool = field(
        default=True,
        metadata={
            "description": "if `False`, typing an opening bracket, parenthesis, or quote will not automatically insert the closing character"
        },
    )
    codeium_api_key: str | UnsetType | None = field(
        default=UNSET,
        repr=False,
        metadata={"description": "the Codeium API key", "sensitive": True},
    )
    api_key: str | UnsetType | None = field(
        default=UNSET,
        repr=False,
        metadata={
            "description": "Deprecated completion API key. Use an AI provider configuration instead.",
            "sensitive": True,
            "deprecated": True,
        },
    )
    model: str | UnsetType | None = field(
        default=UNSET,
        metadata={
            "description": "Deprecated completion model. Use ai.models.autocomplete_model instead.",
            "deprecated": True,
        },
    )
    base_url: str | UnsetType | None = field(
        default=UNSET,
        metadata={
            "description": "Deprecated completion API endpoint. Use an AI provider configuration instead.",
            "deprecated": True,
        },
    )


@dataclass(kw_only=True)
class SaveConfig(Config):
    """Configuration for saving."""

    autosave: Literal["off", "after_delay"] = field(
        default="after_delay",
        metadata={"description": 'one of `"off"` or `"after_delay"`'},
    )
    autosave_delay: int = field(
        default=1000,
        metadata={
            "description": "Delay in milliseconds before automatically saving."
        },
    )
    format_on_save: bool = field(
        default=False,
        metadata={"description": "if `True`, format the code on save"},
    )


@dataclass(kw_only=True)
class KeymapConfig(Config):
    """Configuration for keymaps."""

    preset: Literal["default", "vim"] = field(
        default="default",
        metadata={"description": 'one of `"default"` or `"vim"`'},
    )
    overrides: dict[str, str] = field(
        default_factory=dict,
        metadata={
            "description": "a dict of keymap actions to their keymap override"
        },
    )
    vimrc: str | UnsetType | None = field(
        default=UNSET,
        metadata={"description": "path to a vimrc file to load keymaps from"},
    )
    destructive_delete: bool | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "if `True`, allows deleting cells with content."
        },
    )


@dataclass(kw_only=True)
class VenvConfig(Config):
    """Configuration for an external Python environment in edit mode.

    Launches the notebook kernel in an existing virtualenv. Applies to
    single notebooks and directories when editing without `--sandbox`."""

    path: str | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "path to a virtualenv directory (absolute or relative to pyproject.toml)"
        },
    )
    writable: bool | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "if true, marimo will manage script metadata (inline dependencies). Defaults to false."
        },
    )


@dataclass(kw_only=True)
class RuntimeConfig(Config):
    """Configuration for runtime."""

    auto_instantiate: bool = field(
        default=False,
        metadata={
            "description": "if `False`, cells won't automatically run on startup. This only applies when editing a notebook, and not when running as an application."
        },
    )
    auto_reload: Literal["off", "lazy", "autorun"] = field(
        default="off",
        metadata={
            "description": "If `lazy`, mark cells importing modified modules as stale; if `autorun`, automatically run affected cells. Similar to IPython's %autoreload extension, with dependency-aware execution."
        },
    )
    reactive_tests: bool = field(
        default=True,
        metadata={
            "description": "If `True`, automatically run pytest on cells containing only test functions and test classes."
        },
    )
    on_cell_change: OnCellChangeType = field(
        default="autorun",
        metadata={
            "description": "if `lazy`, cells will be marked stale when their ancestors run but won't autorun; if `autorun`, cells will automatically run when their ancestors run."
        },
    )
    watcher_on_save: Literal["lazy", "autorun"] = field(
        default="lazy",
        metadata={
            "description": 'how to handle file changes when saving. `"lazy"` marks affected cells as stale, `"autorun"` automatically runs affected cells.'
        },
    )
    output_max_bytes: int = field(
        default_factory=lambda: int(
            os.getenv("MARIMO_OUTPUT_MAX_BYTES", "8000000")
        ),
        metadata={
            "description": "the maximum size in bytes of cell outputs; larger values may affect frontend performance"
        },
    )
    serve_cached_sessions_in_apps: bool | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "if `True`, initialize applications with session cache."
        },
    )
    std_stream_max_bytes: int = field(
        default_factory=lambda: int(
            os.getenv("MARIMO_STD_STREAM_MAX_BYTES", "1000000")
        ),
        metadata={
            "description": "the maximum size in bytes of console outputs; larger values may affect frontend performance"
        },
    )
    pythonpath: list[str] | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "a list of directories to add to the Python search path. Directories will be added to the head of sys.path. Similar to the `PYTHONPATH` environment variable, the directories will be included in where Python will look for imported modules."
        },
    )
    dotenv: list[str] | UnsetType = field(
        default=UNSET,
        repr=False,
        metadata={
            "description": "a list of paths to `.env` files to load. If the file does not exist, it will be silently ignored. Relative paths resolve against the directory holding the `pyproject.toml`, or the notebook's directory when there is none.",
            "sensitive": True,
        },
    )
    default_sql_output: SqlOutputType = field(
        default="auto",
        metadata={
            "description": 'the default output format for SQL queries. Can be one of: `"auto"`, `"native"`, `"polars"`, `"lazy-polars"`, or `"pandas"`.'
        },
    )
    default_auto_download: list[ExportType] | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "an Optional list of export types to automatically snapshot your notebook as: `html`, `markdown`, `ipynb`."
        },
    )
    default_csv_encoding: str = field(
        default="utf-8",
        metadata={"description": "the default encoding for CSV exports."},
    )
    show_tracebacks: bool = field(
        default=False,
        metadata={
            "description": "if `True`, show detailed error tracebacks in run mode. When enabled, exceptions will display a clickable toast that opens a modal with the full traceback."
        },
    )

    execution_type: ExecutionType | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "Cell declaration handling: relaxed or strict."
        },
    )
    cache_cells: bool | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "Enable experimental automatic cell caching."
        },
    )
    pin_modules: bool | UnsetType = field(
        default=UNSET,
        metadata={"description": "Pin imported modules when caching cells."},
    )


@dataclass(kw_only=True)
class DisplayConfig(Config):
    """Configuration for display."""

    theme: Theme = field(
        default="light",
        metadata={"description": '`"light"`, `"dark"`, or `"system"`'},
    )
    code_editor_font_size: int = field(
        default=14, metadata={"description": "font size for the code editor"}
    )
    cell_output: Literal["above", "below"] = field(
        default="below", metadata={"description": '`"above"` or `"below"`'}
    )
    default_width: WidthType = field(
        default="medium", metadata={"description": "Default notebook width."}
    )
    dataframes: Literal["rich", "plain"] = field(
        default="rich", metadata={"description": '`"rich"` or `"plain"`'}
    )
    custom_css: list[str] | UnsetType = field(
        default=UNSET,
        metadata={"description": "list of paths to custom CSS files"},
    )
    default_table_page_size: int = field(
        default=10,
        metadata={
            "description": "default number of rows to display in tables"
        },
    )
    default_table_max_columns: int = field(
        default=50,
        metadata={
            "description": "default maximum number of columns to display in tables"
        },
    )
    reference_highlighting: bool = field(
        default=True,
        metadata={
            "description": "if `True`, highlight reactive variable references"
        },
    )
    code_lens: bool = field(
        default=True,
        metadata={
            "description": "if `True`, show inline icons in cell editors linking datasources, storage buckets, and caches to their panels"
        },
    )
    locale: str | UnsetType | None = field(
        default=UNSET,
        metadata={
            "description": 'locale for date formatting and internationalization (e.g., "en-US", "en-GB", "de-DE")'
        },
    )


@dataclass(kw_only=True)
class FormattingConfig(Config):
    """Configuration for code formatting."""

    line_length: int = field(
        default=79, metadata={"description": "max line length"}
    )


@dataclass(kw_only=True)
class ServerConfig(Config):
    """Configuration for the server."""

    browser: Literal["default"] | str = field(
        default="default",
        metadata={
            "description": 'the web browser to use. `"default"` or a browser registered with Python\'s webbrowser module (eg, `"firefox"` or `"chrome"`)'
        },
    )
    follow_symlink: bool = field(
        default=False,
        metadata={
            "description": "if true, the server will follow symlinks it finds inside its static assets directory."
        },
    )
    disable_file_downloads: bool | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "if true, the file download button will be hidden in the file explorer."
        },
    )
    transport: Literal["websocket", "sse"] | UnsetType = field(
        default=UNSET,
        metadata={
            "description": 'experimental. The transport used to stream kernel messages to the frontend, typically set with the `MARIMO_SERVER_TRANSPORT` environment variable. `"websocket"` (default) uses the `/ws` WebSocket endpoint; `"sse"` uses server-sent events over HTTP, for deployments behind proxies or services that do not support WebSockets. Terminal, LSP, and real-time collaboration still require WebSockets; RTC is disabled when using `"sse"`.'
        },
    )


@dataclass(kw_only=True)
class PackageManagementConfig(Config):
    """Configuration options for package management."""

    manager: Literal["pip", "rye", "uv", "poetry", "pixi"] = field(
        default_factory=infer_package_manager,
        metadata={"description": "the package manager to use"},
    )


@dataclass(kw_only=True)
class AiModelConfig(Config):
    """Configuration options for an AI model."""

    chat_model: str | UnsetType | None = field(
        default=UNSET,
        metadata={"description": "the model to use for chat completions"},
    )
    edit_model: str | UnsetType | None = field(
        default=UNSET,
        metadata={"description": "the model to use for edit completions"},
    )
    autocomplete_model: str | UnsetType | None = field(
        default=UNSET,
        metadata={
            "description": "the model to use for code completion/autocomplete"
        },
    )
    displayed_models: list[str] = field(
        default_factory=list,
        metadata={"description": "a list of models to display in the UI"},
    )
    custom_models: list[str] = field(
        default_factory=list,
        metadata={
            "description": "a list of custom models to use that are not from the default list"
        },
    )


@dataclass(kw_only=True)
class AiConfig(Config):
    """Configuration options for AI."""

    enabled: bool = field(
        default=True,
        metadata={
            "description": "if `False`, hide AI actions and panels in the marimo UI"
        },
    )
    rules: str | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "custom rules to include in all AI completion prompts"
        },
    )
    max_tokens: int | UnsetType | None = field(
        default=UNSET,
        metadata={
            "description": "the maximum number of tokens to use in AI completions"
        },
    )
    mode: CopilotMode | UnsetType = field(
        default=UNSET,
        metadata={
            "description": 'the mode to use for AI completions. Can be one of: `"ask"` or `"manual"`'
        },
    )
    inline_tooltip: bool | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "if `True`, enable inline AI tooltip suggestions"
        },
    )
    allow_provider_config: bool = field(
        default=True,
        metadata={
            "description": "if `False`, lock provider setup in the settings UI, making them read-only. Users cannot bring their own credentials or add custom providers. Default `True`."
        },
    )
    models: AiModelConfig = field(
        default_factory=AiModelConfig,
        metadata={"description": "the models to use for AI completions"},
    )
    open_ai: OpenAiConfig | UnsetType = field(
        default=UNSET, metadata={"description": "the OpenAI config"}
    )
    anthropic: AnthropicConfig | UnsetType = field(
        default=UNSET, metadata={"description": "the Anthropic config"}
    )
    google: GoogleAiConfig | UnsetType = field(
        default=UNSET, metadata={"description": "the Google AI config"}
    )
    bedrock: BedrockConfig | UnsetType = field(
        default=UNSET, metadata={"description": "the Bedrock config"}
    )
    azure: OpenAiConfig | UnsetType = field(
        default=UNSET, metadata={"description": "the Azure config"}
    )
    ollama: OpenAiConfig | UnsetType = field(
        default=UNSET, metadata={"description": "the Ollama config"}
    )
    github: GitHubConfig | UnsetType = field(
        default=UNSET, metadata={"description": "the GitHub Copilot config"}
    )
    openrouter: OpenAiConfig | UnsetType = field(
        default=UNSET, metadata={"description": "the OpenRouter config"}
    )
    wandb: OpenAiConfig | UnsetType = field(
        default=UNSET, metadata={"description": "the Weights & Biases config"}
    )
    opencode_go: OpenAiConfig | UnsetType = field(
        default=UNSET, metadata={"description": "the OpenCode Go config"}
    )
    custom_providers: dict[str, OpenAiConfig] = field(
        default_factory=dict,
        metadata={
            "description": "a dict of custom OpenAI-compatible providers"
        },
    )
    open_ai_compatible: OpenAiConfig | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "the OpenAI-compatible config (deprecated, use custom_providers)",
            "deprecated": True,
        },
    )


@dataclass(kw_only=True)
class OpenAiConfig(Config):
    """Configuration options for OpenAI or OpenAI-compatible services."""

    api_key: str | UnsetType = field(
        default=UNSET,
        repr=False,
        metadata={
            "description": "the OpenAI API key or an `env:` reference",
            "sensitive": True,
        },
    )
    base_url: str | UnsetType = field(
        default=UNSET, metadata={"description": "the base URL for the API"}
    )
    project: str | UnsetType = field(
        default=UNSET,
        metadata={"description": "the project ID for the OpenAI API"},
    )
    ssl_verify: bool | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "Whether to verify TLS certificates for the API client."
        },
    )
    ca_bundle_path: str | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "custom ca bundle to be used for verifying SSL certificates. Used to create custom SSL context for httpx client"
        },
    )
    client_pem: str | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "Path to a client PEM certificate for authenticating API requests."
        },
    )
    extra_headers: dict[str, str] | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "extra headers to be passed to the OpenAI client"
        },
    )
    model: str | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "Deprecated chat model. Use ai.models.chat_model instead.",
            "deprecated": True,
        },
    )


@dataclass(kw_only=True)
class AnthropicConfig(Config):
    """Configuration options for Anthropic."""

    api_key: str | UnsetType = field(
        default=UNSET,
        repr=False,
        metadata={
            "description": "the Anthropic API key or an `env:` reference",
            "sensitive": True,
        },
    )


@dataclass(kw_only=True)
class GoogleAiConfig(Config):
    """Configuration options for Google AI."""

    api_key: str | UnsetType = field(
        default=UNSET,
        repr=False,
        metadata={
            "description": "the Google AI API key or an `env:` reference",
            "sensitive": True,
        },
    )


@dataclass(kw_only=True)
class BedrockConfig(Config):
    """Configuration options for Bedrock."""

    profile_name: str | UnsetType = field(
        default=UNSET, metadata={"description": "the AWS profile to use"}
    )
    region_name: str | UnsetType = field(
        default=UNSET, metadata={"description": "the AWS region to use"}
    )
    aws_access_key_id: str | UnsetType = field(
        default=UNSET,
        repr=False,
        metadata={"description": "the AWS access key ID", "sensitive": True},
    )
    aws_secret_access_key: str | UnsetType = field(
        default=UNSET,
        repr=False,
        metadata={
            "description": "the AWS secret access key",
            "sensitive": True,
        },
    )


@dataclass(kw_only=True)
class GitHubConfig(Config):
    """Configuration options for GitHub Copilot."""

    api_key: str | UnsetType = field(
        default=UNSET,
        repr=False,
        metadata={
            "description": "a GitHub Copilot token or an `env:` reference",
            "sensitive": True,
        },
    )
    base_url: str | UnsetType = field(
        default=UNSET,
        metadata={"description": "the base URL for the GitHub Copilot API"},
    )
    copilot_settings: dict[str, Any] | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "configuration settings for GitHub Copilot LSP. Supports settings like `http` (proxy configuration), `telemetry`, and `github-enterprise` (enterprise URI)."
        },
    )


@dataclass(kw_only=True)
class PythonLanguageServerConfig(Config):
    """Configuration options for Python Language Server.

    pylsp handles completion, hover, go-to-definition, and diagnostics."""

    enabled: bool = field(
        default=False, metadata={"description": "Enable this language server."}
    )
    enable_mypy: bool = field(
        default=True,
        metadata={"description": "Enable mypy diagnostics in pylsp."},
    )
    enable_ruff: bool = field(
        default=True,
        metadata={"description": "Enable ruff diagnostics in pylsp."},
    )
    enable_flake8: bool = field(
        default=False,
        metadata={"description": "Enable flake8 diagnostics in pylsp."},
    )
    enable_pydocstyle: bool = field(
        default=False,
        metadata={"description": "Enable pydocstyle diagnostics in pylsp."},
    )
    enable_pylint: bool = field(
        default=False,
        metadata={"description": "Enable pylint diagnostics in pylsp."},
    )
    enable_pyflakes: bool = field(
        default=False,
        metadata={"description": "Enable pyflakes diagnostics in pylsp."},
    )


@dataclass(kw_only=True)
class BasedpyrightServerConfig(Config):
    """Configuration options for basedpyright Language Server.

    basedpyright handles completion, hover, go-to-definition, and diagnostics,
    but we only use it for diagnostics."""

    enabled: bool | UnsetType = field(
        default=UNSET, metadata={"description": "Enable this language server."}
    )


@dataclass(kw_only=True)
class TyLanguageServerConfig(Config):
    """Configuration options for Ty Language Server.

    ty handles completion, hover, go-to-definition, and diagnostics,
    but we only use it for diagnostics."""

    enabled: bool | UnsetType = field(
        default=UNSET, metadata={"description": "Enable this language server."}
    )


@dataclass(kw_only=True)
class PyreflyLanguageServerConfig(Config):
    """Configuration options for Pyrefly Language Server.

    Pyrefly handles completion, hover, go-to-definition, and diagnostics."""

    enabled: bool | UnsetType = field(
        default=UNSET, metadata={"description": "Enable this language server."}
    )


@dataclass(kw_only=True)
class LanguageServersConfig(Config):
    """Configuration options for language servers."""

    pylsp: PythonLanguageServerConfig = field(
        default_factory=PythonLanguageServerConfig,
        metadata={"description": "the pylsp config"},
    )
    basedpyright: BasedpyrightServerConfig | UnsetType = field(
        default=UNSET, metadata={"description": "the basedpyright config"}
    )
    ty: TyLanguageServerConfig | UnsetType = field(
        default=UNSET, metadata={"description": "the ty config"}
    )
    pyrefly: PyreflyLanguageServerConfig | UnsetType = field(
        default=UNSET, metadata={"description": "the pyrefly config"}
    )


@dataclass(kw_only=True)
class DiagnosticsConfig(Config):
    """Configuration options for diagnostics."""

    enabled: bool | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "if `True`, diagnostics will be shown in the editor"
        },
    )
    sql_linter: bool = field(
        default=True,
        metadata={
            "description": "if `True`, SQL cells will have linting enabled"
        },
    )


@dataclass(kw_only=True)
class LintConfig(Config):
    """Configuration for lint rule selection.

    Follows ruff-inspired semantics for selecting which rules to run
    during `marimo check`."""

    select: list[str] | UnsetType = field(
        default=UNSET,
        metadata={
            "description": 'list of rule code prefixes that replaces the default enabled set. Use `"ALL"` to select all rules. Example: `["MB", "MR001"]`'
        },
    )
    ignore: list[str] | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "list of rule code prefixes to remove from the enabled set."
        },
    )


@dataclass(kw_only=True)
class SnippetsConfig(Config):
    """Configuration for snippets."""

    custom_paths: list[str] = field(
        default_factory=list,
        metadata={
            "description": "Paths to directories containing custom snippets."
        },
    )
    include_default_snippets: bool = field(
        default=True,
        metadata={"description": "Include the built-in snippets."},
    )


@dataclass(kw_only=True)
class DatasourcesConfig(Config):
    """Configuration for datasources panel."""

    auto_discover_schemas: bool | Literal["auto"] | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "if `True`, include schemas in the datasource"
        },
    )
    auto_discover_tables: bool | Literal["auto"] | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "if `True`, include tables in the datasource"
        },
    )
    auto_discover_columns: bool | Literal["auto"] | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "if `True`, include columns & table metadata in the datasource"
        },
    )


@dataclass(kw_only=True)
class FolderConfig(Config):
    """Configuration for an additional file browser root."""

    path: str = field(
        metadata={"description": "the absolute path to the folder"}
    )
    name: str | UnsetType = field(
        default=UNSET,
        metadata={"description": "an optional display name for the folder"},
    )


@dataclass(kw_only=True)
class FileBrowserConfig(Config):
    """Configuration for the file browser panel."""

    folders: list[FolderConfig] | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "additional absolute folders to show in the file browser"
        },
    )


@dataclass(kw_only=True)
class SharingConfig(Config):
    """Configuration for sharing features."""

    html: bool | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "if `False`, HTML sharing options will be hidden from the UI"
        },
    )
    wasm: bool | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "if `False`, WebAssembly sharing options will be hidden from the UI"
        },
    )
    molab: bool | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "if `False`, molab sharing options will be hidden from the UI"
        },
    )


@dataclass(kw_only=True)
class StoreConfig(Config):
    """Configuration for a single cache store."""

    type: StoreKey | UnsetType = field(
        default=UNSET, metadata={"description": "Cache store backend."}
    )
    args: dict[str, Any] | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "Keyword arguments passed to the cache store constructor."
        },
    )


# One store, or a list composed into a TieredStore.
CacheStoreConfig = list[StoreConfig] | StoreConfig


@dataclass(kw_only=True)
class CacheConfig(Config):
    """Configuration for caching."""

    verification: CacheVerification | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "Cache signature verification posture: off, on, or strict."
        },
    )
    store: CacheStoreConfig | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "Backing cache store, or a list of stores composed into a tiered store."
        },
    )


@dataclass(kw_only=True)
class SigningConfig(Config):
    """Cache-signing trust and identity."""

    trusted_signers: dict[str, str] | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "Trusted key fingerprints (SHA256:<base64>) mapped to advisory labels. Trust permits code execution when restoring cached Python objects."
        },
    )
    private_key_path: str | UnsetType = field(
        default=UNSET,
        repr=False,
        metadata={
            "description": "Absolute path to this machine's private signing key. Not exposed to the frontend.",
            "sensitive": True,
        },
    )


@dataclass(kw_only=True)
class ExperimentalConfig(Config):
    """Configuration for experimental features.

    Features exposed on the frontend must match the frontend config."""

    markdown: bool | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "Enable experimental Markdown notebook features."
        },
    )
    wasm_layouts: bool | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "Enable experimental layouts in WebAssembly notebooks."
        },
    )
    rtc_v2: bool | UnsetType = field(
        default=UNSET,
        metadata={"description": "Enable real-time collaboration."},
    )
    isolate_apps: bool | UnsetType = field(
        default=UNSET,
        metadata={"description": "Run applications in separate processes."},
    )
    debugger: bool | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "Enable live debugging with gutter breakpoints and pdb."
        },
    )
    line_timing: bool | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "Highlight the active line and show per-line execution timing."
        },
    )
    execution_type: ExecutionType | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "Experimental cell declaration handling: relaxed or strict."
        },
    )


@dataclass(kw_only=True)
class MCPServerStdioConfig(Config):
    """Configuration for STDIO transport MCP servers"""

    command: str = field(
        metadata={"description": "Command used to launch the MCP server."}
    )
    args: list[str] | UnsetType | None = field(
        default=UNSET,
        metadata={
            "description": "Arguments passed to the MCP server command."
        },
    )
    env: dict[str, str] | UnsetType | None = field(
        default=UNSET,
        metadata={
            "description": "Environment variables supplied to the MCP server."
        },
    )
    disabled: bool | UnsetType | None = field(
        default=UNSET, metadata={"description": "Disable this MCP server."}
    )


@dataclass(kw_only=True)
class MCPServerStreamableHttpConfig(Config):
    """Configuration for Streamable HTTP transport MCP servers"""

    url: str = field(
        metadata={"description": "URL of the streamable HTTP MCP server."}
    )
    headers: dict[str, str] | UnsetType | None = field(
        default=UNSET,
        metadata={"description": "HTTP headers sent to the MCP server."},
    )
    timeout: float | UnsetType | None = field(
        default=UNSET,
        metadata={
            "description": "Timeout in seconds for MCP server requests."
        },
    )
    env: dict[str, str] | UnsetType | None = field(
        default=UNSET,
        metadata={
            "description": "Environment variables used by the MCP server configuration."
        },
    )
    disabled: bool | UnsetType | None = field(
        default=UNSET, metadata={"description": "Disable this MCP server."}
    )


MCPServerConfig = MCPServerStdioConfig | MCPServerStreamableHttpConfig


@dataclass(kw_only=True)
class MCPConfig(Config):
    """Configuration for MCP servers

    Note: the field name `mcpServers` is camelCased to match MCP server
    config conventions used by popular AI applications (e.g. Cursor, Claude Desktop, etc.)"""

    mcpServers: dict[str, MCPServerConfig] = field(
        default_factory=dict,
        metadata={"description": "Named MCP server configurations."},
    )
    presets: list[Literal["marimo", "context7"]] = field(
        default_factory=list,
        metadata={"description": "Built-in MCP server presets to enable."},
    )


@dataclass(kw_only=True)
class MarimoConfig(Config):
    """Configuration for the marimo editor"""

    completion: CompletionConfig = field(
        default_factory=CompletionConfig,
        metadata={"description": "Configuration for code completion."},
    )
    display: DisplayConfig = field(
        default_factory=DisplayConfig,
        metadata={"description": "Configuration for display."},
    )
    formatting: FormattingConfig = field(
        default_factory=FormattingConfig,
        metadata={"description": "Configuration for code formatting."},
    )
    keymap: KeymapConfig = field(
        default_factory=KeymapConfig,
        metadata={"description": "Configuration for keymaps."},
    )
    runtime: RuntimeConfig = field(
        default_factory=RuntimeConfig,
        metadata={"description": "Configuration for runtime."},
    )
    save: SaveConfig = field(
        default_factory=SaveConfig,
        metadata={"description": "Configuration for saving."},
    )
    server: ServerConfig = field(
        default_factory=ServerConfig,
        metadata={"description": "Configuration for the server."},
    )
    package_management: PackageManagementConfig = field(
        default_factory=PackageManagementConfig,
        metadata={
            "description": "Configuration options for package management."
        },
    )
    ai: AiConfig = field(
        default_factory=AiConfig,
        metadata={"description": "Configuration options for AI."},
    )
    language_servers: LanguageServersConfig = field(
        default_factory=LanguageServersConfig,
        metadata={
            "description": "Configuration options for language servers."
        },
    )
    diagnostics: DiagnosticsConfig = field(
        default_factory=DiagnosticsConfig,
        metadata={"description": "Configuration options for diagnostics."},
    )
    lint: LintConfig | UnsetType = field(
        default=UNSET,
        metadata={"description": "Configuration for lint rule selection."},
    )
    experimental: ExperimentalConfig | UnsetType = field(
        default=UNSET,
        metadata={"description": "Configuration for experimental features."},
    )
    snippets: SnippetsConfig = field(
        default_factory=SnippetsConfig,
        metadata={"description": "Configuration for snippets."},
    )
    datasources: DatasourcesConfig | UnsetType = field(
        default=UNSET,
        metadata={"description": "Configuration for datasources panel."},
    )
    file_browser: FileBrowserConfig | UnsetType = field(
        default=UNSET,
        metadata={"description": "Configuration for the file browser panel."},
    )
    sharing: SharingConfig | UnsetType = field(
        default=UNSET,
        metadata={"description": "Configuration for sharing features."},
    )
    mcp: MCPConfig = field(
        default_factory=MCPConfig,
        metadata={"description": "Configuration for MCP servers"},
    )
    venv: VenvConfig | UnsetType = field(
        default=UNSET,
        metadata={
            "description": "Configuration for an external Python environment in edit mode."
        },
    )
    cache: CacheConfig | UnsetType = field(
        default=UNSET, metadata={"description": "Configuration for caching."}
    )
    signing: SigningConfig | UnsetType = field(
        default=UNSET,
        metadata={"description": "Cache-signing trust and identity."},
    )
