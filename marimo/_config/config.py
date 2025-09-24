# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from marimo._config.packages import infer_package_manager
from marimo._config.utils import deep_copy

if sys.version_info < (3, 11):
    from typing_extensions import NotRequired
else:
    from typing import NotRequired

from typing import (
    Any,
    Literal,
    Optional,
    TypedDict,
    Union,
    cast,
)

from marimo._output.rich_help import mddoc
from marimo._utils.deep_merge import deep_merge


@mddoc
@dataclass
class CompletionConfig(TypedDict):
    """Configuration for code completion.

    A dict with key/value pairs configuring code completion in the marimo
    editor.

    **Keys.**

    - `activate_on_typing`: if `False`, completion won't activate
    until the completion hotkey is entered
    - `copilot`: one of `"github"`, `"codeium"`, or `"custom"`
    - `codeium_api_key`: the Codeium API key
    """

    activate_on_typing: bool
    copilot: Union[bool, Literal["github", "codeium", "custom"]]

    # Codeium
    codeium_api_key: NotRequired[Optional[str]]

    # @deprecated: use `ai.models.autocomplete_model` instead
    api_key: NotRequired[Optional[str]]
    model: NotRequired[Optional[str]]
    base_url: NotRequired[Optional[str]]


@mddoc
@dataclass
class SaveConfig(TypedDict):
    """Configuration for saving.

    **Keys.**

    - `autosave`: one of `"off"` or `"after_delay"`
    - `delay`: number of milliseconds to wait before autosaving
    - `format_on_save`: if `True`, format the code on save
    """

    autosave: Literal["off", "after_delay"]
    autosave_delay: int
    format_on_save: bool


@mddoc
@dataclass
class KeymapConfig(TypedDict):
    """Configuration for keymaps.

    **Keys.**

    - `preset`: one of `"default"` or `"vim"`
    - `overrides`: a dict of keymap actions to their keymap override
    - `vimrc`: path to a vimrc file to load keymaps from
    - `destructive_delete`: if `True`, allows deleting cells with content.
    """

    preset: Literal["default", "vim"]
    overrides: NotRequired[dict[str, str]]
    vimrc: NotRequired[Optional[str]]
    destructive_delete: NotRequired[bool]


OnCellChangeType = Literal["lazy", "autorun"]
ExecutionType = Literal["relaxed", "strict"]


# TODO(akshayka): remove normal, migrate to compact
# normal == compact
WidthType = Literal["normal", "compact", "medium", "full", "columns"]
Theme = Literal["light", "dark", "system"]
ExportType = Literal["html", "markdown", "ipynb"]
SqlOutputType = Literal["polars", "lazy-polars", "pandas", "native", "auto"]
StoreKey = Literal["file", "redis", "rest", "tiered"]


@mddoc
@dataclass
class RuntimeConfig(TypedDict):
    """Configuration for runtime.

    **Keys.**

    - `auto_instantiate`: if `False`, cells won't automatically
        run on startup. This only applies when editing a notebook,
        and not when running as an application.
        The default is `True`.
    - `auto_reload`: if `lazy`, cells importing modified modules will marked
      as stale; if `autorun`, affected cells will be automatically run. similar
      to IPython's %autoreload extension but with more code intelligence.
    - `reactive_tests`: if `True`, marimo will automatically run pytest on cells containing only test functions and test classes.
      execution.
    - `on_cell_change`: if `lazy`, cells will be marked stale when their
      ancestors run but won't autorun; if `autorun`, cells will automatically
      run when their ancestors run.
    - `execution_type`: if `relaxed`, marimo will not clone cell declarations;
      if `strict` marimo will clone cell declarations by default, avoiding
      hidden potential state build up.
    - `watcher_on_save`: how to handle file changes when saving. `"lazy"` marks
        affected cells as stale, `"autorun"` automatically runs affected cells.
    - `output_max_bytes`: the maximum size in bytes of cell outputs; larger
        values may affect frontend performance
    - `std_stream_max_bytes`: the maximum size in bytes of console outputs;
      larger values may affect frontend performance
    - `pythonpath`: a list of directories to add to the Python search path.
        Directories will be added to the head of sys.path. Similar to the
        `PYTHONPATH` environment variable, the directories will be included in
        where Python will look for imported modules.
    - `dotenv`: a list of paths to `.env` files to load.
        If the file does not exist, it will be silently ignored.
        The default is `[".env"]` if a pyproject.toml is found, otherwise `[]`.
    - `default_sql_output`: the default output format for SQL queries. Can be one of:
        `"auto"`, `"native"`, `"polars"`, `"lazy-polars"`, or `"pandas"`.
        The default is `"auto"`.
    - `default_auto_download`: an Optional list of export types to automatically snapshot your notebook as:
       `html`, `markdown`, `ipynb`.
       The default is None.
    """

    auto_instantiate: bool
    auto_reload: Literal["off", "lazy", "autorun"]
    reactive_tests: bool
    on_cell_change: OnCellChangeType
    watcher_on_save: Literal["lazy", "autorun"]
    output_max_bytes: int
    std_stream_max_bytes: int
    pythonpath: NotRequired[list[str]]
    dotenv: NotRequired[list[str]]
    default_sql_output: SqlOutputType
    default_auto_download: NotRequired[list[ExportType]]


@mddoc
@dataclass
class DisplayConfig(TypedDict):
    """Configuration for display.

    **Keys.**

    - `theme`: `"light"`, `"dark"`, or `"system"`
    - `code_editor_font_size`: font size for the code editor
    - `cell_output`: `"above"` or `"below"`
    - `dataframes`: `"rich"` or `"plain"`
    - `custom_css`: list of paths to custom CSS files
    - `default_table_page_size`: default number of rows to display in tables
    - `default_table_max_columns`: default maximum number of columns to display in tables
    - `reference_highlighting`: if `True`, highlight reactive variable references
    - `locale`: locale for date formatting and internationalization (e.g., "en-US", "en-GB", "de-DE")
    """

    theme: Theme
    code_editor_font_size: int
    cell_output: Literal["above", "below"]
    default_width: WidthType
    dataframes: Literal["rich", "plain"]
    custom_css: NotRequired[list[str]]
    default_table_page_size: int
    default_table_max_columns: int
    reference_highlighting: NotRequired[bool]
    locale: NotRequired[Optional[str]]


@mddoc
@dataclass
class FormattingConfig(TypedDict):
    """Configuration for code formatting.

    **Keys.**

    - `line_length`: max line length
    """

    line_length: int


@dataclass
class ServerConfig(TypedDict):
    """Configuration for the server.

    **Keys.**

    - `browser`: the web browser to use. `"default"` or a browser registered
        with Python's webbrowser module (eg, `"firefox"` or `"chrome"`)
    - `follow_symlink`: if true, the server will follow symlinks it finds
        inside its static assets directory.
    """

    browser: Union[Literal["default"], str]
    follow_symlink: bool


@dataclass
class PackageManagementConfig(TypedDict):
    """Configuration options for package management.

    **Keys.**

    - `manager`: the package manager to use
    """

    manager: Literal["pip", "rye", "uv", "poetry", "pixi"]


CopilotMode = Literal["ask", "manual"]


@mddoc
@dataclass
class AiModelConfig(TypedDict):
    """Configuration options for an AI model.

    **Keys.**

    - `chat_model`: the model to use for chat completions
    - `edit_model`: the model to use for edit completions
    - `autocomplete_model`: the model to use for code completion/autocomplete
    - `displayed_models`: a list of models to display in the UI
    - `custom_models`: a list of custom models to use that are not from the default list
    """

    chat_model: NotRequired[str]
    edit_model: NotRequired[str]
    autocomplete_model: NotRequired[str]

    displayed_models: list[str]
    custom_models: list[str]


@dataclass
class AiConfig(TypedDict, total=False):
    """Configuration options for AI.

    **Keys.**

    - `rules`: custom rules to include in all AI completion prompts
    - `max_tokens`: the maximum number of tokens to use in AI completions
    - `mode`: the mode to use for AI completions. Can be one of: `"ask"` or `"manual"`
    - `models`: the models to use for AI completions
    - `open_ai`: the OpenAI config
    - `anthropic`: the Anthropic config
    - `google`: the Google AI config
    - `bedrock`: the Bedrock config
    - `azure`: the Azure config
    - `ollama`: the Ollama config
    - `github`: the GitHub config
    - `open_ai_compatible`: the OpenAI-compatible config
    """

    rules: NotRequired[str]
    max_tokens: NotRequired[int]
    mode: NotRequired[CopilotMode]
    models: AiModelConfig

    # providers
    open_ai: OpenAiConfig
    anthropic: AnthropicConfig
    google: GoogleAiConfig
    bedrock: BedrockConfig
    azure: OpenAiConfig
    ollama: OpenAiConfig
    github: GitHubConfig
    open_ai_compatible: OpenAiConfig


@dataclass
class OpenAiConfig(TypedDict, total=False):
    """Configuration options for OpenAI or OpenAI-compatible services.

    **Keys.**

    - `api_key`: the OpenAI API key
    - `base_url`: the base URL for the API
    - `ssl_verify` : Boolean argument for httpx passed to open ai client. httpx defaults to true, but some use cases to let users override to False in some testing scenarios
    - `ca_bundle_path`: custom ca bundle to be used for verifying SSL certificates. Used to create custom SSL context for httpx client
    - `client_pem` : custom path of a client .pem cert used for verifying identity of client server
    - `extra_headers`: extra headers to be passed to the OpenAI client
    """

    api_key: str
    base_url: NotRequired[str]
    ssl_verify: NotRequired[bool]
    ca_bundle_path: NotRequired[str]
    client_pem: NotRequired[str]
    extra_headers: NotRequired[dict[str, str]]

    # @deprecated: use `ai.models.chat_model` instead
    model: NotRequired[str]


@dataclass
class AnthropicConfig(TypedDict, total=False):
    """Configuration options for Anthropic.

    **Keys.**

    - `api_key`: the Anthropic API key
    """

    api_key: str


@dataclass
class GoogleAiConfig(TypedDict, total=False):
    """Configuration options for Google AI.

    **Keys.**

    - `api_key`: the Google AI API key
    """

    api_key: str


@dataclass
class BedrockConfig(TypedDict, total=False):
    """Configuration options for Bedrock.

    **Keys.**

    - `profile_name`: the AWS profile to use
    - `region_name`: the AWS region to use
    - `aws_access_key_id`: the AWS access key ID
    - `aws_secret_access_key`: the AWS secret access key
    """

    profile_name: NotRequired[str]
    region_name: NotRequired[str]
    aws_access_key_id: NotRequired[str]
    aws_secret_access_key: NotRequired[str]


@dataclass
class GitHubConfig(TypedDict, total=False):
    """Configuration options for GitHub.

    **Keys.**

    - `api_key`: the GitHub API token
    - `base_url`: the base URL for the API
    """

    api_key: str
    base_url: NotRequired[str]


@dataclass
class PythonLanguageServerConfig(TypedDict, total=False):
    """
    Configuration options for Python Language Server.

    pylsp handles completion, hover, go-to-definition, and diagnostics.
    """

    enabled: bool
    enable_mypy: bool
    enable_ruff: bool
    enable_flake8: bool
    enable_pydocstyle: bool
    enable_pylint: bool
    enable_pyflakes: bool


@dataclass
class BasedpyrightServerConfig(TypedDict, total=False):
    """
    Configuration options for basedpyright Language Server.

    basedpyright handles completion, hover, go-to-definition, and diagnostics,
    but we only use it for diagnostics.
    """

    enabled: bool


@dataclass
class TyLanguageServerConfig(TypedDict, total=False):
    """
    Configuration options for Ty Language Server.

    ty handles completion, hover, go-to-definition, and diagnostics,
    but we only use it for diagnostics.
    """

    enabled: bool


@dataclass
class LanguageServersConfig(TypedDict, total=False):
    """Configuration options for language servers.

    **Keys.**

    - `pylsp`: the pylsp config
    """

    pylsp: PythonLanguageServerConfig
    basedpyright: BasedpyrightServerConfig
    ty: TyLanguageServerConfig


@dataclass
class DiagnosticsConfig(TypedDict, total=False):
    """Configuration options for diagnostics.

    **Keys.**

    - `enabled`: if `True`, diagnostics will be shown in the editor
    """

    enabled: bool


@dataclass
class SnippetsConfig(TypedDict):
    """Configuration for snippets.

    **Keys.**

    - `custom_path`: the path to the custom snippets directory
    """

    custom_paths: NotRequired[list[str]]
    include_default_snippets: NotRequired[bool]


@dataclass
class DatasourcesConfig(TypedDict):
    """Configuration for datasources panel.

    **Keys.**

    - `auto_discover_schemas`: if `True`, include schemas in the datasource
    - `auto_discover_tables`: if `True`, include tables in the datasource
    - `auto_discover_columns`: if `True`, include columns & table metadata in the datasource
    """

    auto_discover_schemas: NotRequired[Union[bool, Literal["auto"]]]
    auto_discover_tables: NotRequired[Union[bool, Literal["auto"]]]
    auto_discover_columns: NotRequired[Union[bool, Literal["auto"]]]


@mddoc
@dataclass
class SharingConfig(TypedDict):
    """Configuration for sharing features.

    **Keys.**

    - `html`: if `False`, HTML sharing options will be hidden from the UI
    - `wasm`: if `False`, WebAssembly sharing options will be hidden from the UI
    """

    html: NotRequired[bool]
    wasm: NotRequired[bool]


@dataclass
class StoreConfig(TypedDict, total=False):
    """Configuration for cache stores."""

    type: StoreKey
    args: dict[str, Any]


CacheConfig = Union[list[StoreConfig], StoreConfig]


class ExperimentalConfig(TypedDict, total=False):
    """
    Configuration for experimental features.

    Features exposed on the frontend must match the frontend config.
    """

    markdown: bool  # Used in playground (community cloud)
    inline_ai_tooltip: bool
    wasm_layouts: bool  # Used in playground (community cloud)
    rtc_v2: bool
    performant_table_charts: bool
    mcp_docs: bool
    sql_linter: bool
    sql_mode: bool

    # Internal features
    cache: CacheConfig
    execution_type: ExecutionType


# Prefer to accept any dict since feature flags can change frequently
# But maintain type safety for known flags
ExperimentalConfigType = dict[str, Any]


@mddoc
@dataclass
class MarimoConfig(TypedDict):
    """Configuration for the marimo editor"""

    completion: CompletionConfig
    display: DisplayConfig
    formatting: FormattingConfig
    keymap: KeymapConfig
    runtime: RuntimeConfig
    save: SaveConfig
    server: ServerConfig
    package_management: PackageManagementConfig
    ai: NotRequired[AiConfig]
    language_servers: NotRequired[LanguageServersConfig]
    diagnostics: NotRequired[DiagnosticsConfig]
    experimental: NotRequired[ExperimentalConfigType]
    snippets: NotRequired[SnippetsConfig]
    datasources: NotRequired[DatasourcesConfig]
    sharing: NotRequired[SharingConfig]
    # We don't support configuring MCP servers yet
    # mcp: NotRequired[MCPConfig]


@mddoc
@dataclass
class MCPServerStdioConfig(TypedDict):
    """Configuration for STDIO transport MCP servers"""

    command: str
    args: NotRequired[Optional[list[str]]]
    env: NotRequired[Optional[dict[str, str]]]
    disabled: NotRequired[Optional[bool]]


@mddoc
@dataclass
class MCPServerStreamableHttpConfig(TypedDict):
    """Configuration for Streamable HTTP transport MCP servers"""

    url: str
    headers: NotRequired[Optional[dict[str, str]]]
    timeout: NotRequired[Optional[float]]
    env: NotRequired[Optional[dict[str, str]]]
    disabled: NotRequired[Optional[bool]]


MCPServerConfig = Union[MCPServerStdioConfig, MCPServerStreamableHttpConfig]


@mddoc
@dataclass
class MCPConfig(TypedDict):
    """
    Configuration for MCP servers

    Note: the field name `mcpServers` is camelCased to match MCP server
    config conventions used by popular AI applications (e.g. Cursor, Claude Desktop, etc.)
    """

    mcpServers: dict[str, MCPServerConfig]


DEFAULT_MCP_CONFIG: MCPConfig = MCPConfig(
    mcpServers={
        "marimo": MCPServerStreamableHttpConfig(
            url="https://mcp.marimo.app/mcp"
        ),
        # TODO(bjoaquinc): add more Marimo MCP servers here after they are implemented
    }
)


@mddoc
@dataclass
class PartialMarimoConfig(TypedDict, total=False):
    """Partial configuration for the marimo editor"""

    completion: CompletionConfig
    display: DisplayConfig
    formatting: FormattingConfig
    keymap: KeymapConfig
    runtime: RuntimeConfig
    save: SaveConfig
    server: ServerConfig
    package_management: PackageManagementConfig
    ai: NotRequired[AiConfig]
    language_servers: NotRequired[LanguageServersConfig]
    diagnostics: NotRequired[DiagnosticsConfig]
    experimental: NotRequired[ExperimentalConfigType]
    snippets: SnippetsConfig
    datasources: NotRequired[DatasourcesConfig]
    sharing: NotRequired[SharingConfig]


DEFAULT_CONFIG: MarimoConfig = {
    "completion": {"activate_on_typing": True, "copilot": False},
    "display": {
        "theme": "light",
        "code_editor_font_size": 14,
        "cell_output": "above",
        "default_width": "medium",
        "dataframes": "rich",
        "default_table_page_size": 10,
        "default_table_max_columns": 50,
        "reference_highlighting": False,
    },
    "formatting": {"line_length": 79},
    "keymap": {"preset": "default", "overrides": {}},
    "runtime": {
        "auto_instantiate": True,
        "auto_reload": "off",
        "reactive_tests": True,
        "on_cell_change": "autorun",
        "watcher_on_save": "lazy",
        "output_max_bytes": int(
            os.getenv("MARIMO_OUTPUT_MAX_BYTES", 8_000_000)
        ),
        "std_stream_max_bytes": int(
            os.getenv("MARIMO_STD_STREAM_MAX_BYTES", 1_000_000)
        ),
        "default_sql_output": "auto",
    },
    "save": {
        "autosave": "after_delay",
        "autosave_delay": 1000,
        "format_on_save": False,
    },
    "package_management": {"manager": infer_package_manager()},
    "server": {
        "browser": "default",
        "follow_symlink": False,
    },
    "language_servers": {
        "pylsp": {
            "enabled": True,
            "enable_mypy": True,
            "enable_ruff": True,
            "enable_flake8": False,
            "enable_pydocstyle": False,
            "enable_pylint": False,
            "enable_pyflakes": False,
        }
    },
    "ai": {
        "models": {
            "displayed_models": [],
            "custom_models": [],
        }
    },
    "snippets": {
        "custom_paths": [],
        "include_default_snippets": True,
    },
}


def merge_default_config(
    config: PartialMarimoConfig | MarimoConfig,
) -> MarimoConfig:
    """Merge a user configuration with the default configuration."""
    return merge_config(DEFAULT_CONFIG, config)


def merge_config(
    config: MarimoConfig, new_config: PartialMarimoConfig | MarimoConfig
) -> MarimoConfig:
    """Merge a user configuration with a new configuration. The new config
    will take precedence over the default config.

    Args:
        config: The default configuration.
        new_config: The new configuration to merge with the default config.

    Returns:
        A merged configuration.
    """
    # Remove the keymap overrides from the incoming config,
    # so that they don't get merged into the new config
    if new_config.get("keymap", {}).get("overrides") is not None:
        # Clone config to avoid modifying the original
        config = deep_copy(config)
        config.get("keymap", {}).pop("overrides", {})

    merged = cast(
        MarimoConfig,
        deep_merge(
            cast(dict[Any, Any], config), cast(dict[Any, Any], new_config)
        ),
    )

    # Patches for backward compatibility
    if "runtime" in merged:
        if (
            merged["runtime"].get("auto_reload") is False  # type:ignore[comparison-overlap]
        ):
            merged["runtime"]["auto_reload"] = "off"
        elif (
            merged["runtime"].get("auto_reload") is True  # type:ignore[comparison-overlap]
        ):
            merged["runtime"]["auto_reload"] = "lazy"
        elif (
            merged["runtime"].get("auto_reload") == "detect"  # type:ignore[comparison-overlap]
        ):
            merged["runtime"]["auto_reload"] = "lazy"

    # If missing ai.models.chat_model or ai.models.edit_model, use ai.open_ai.model
    openai_model = merged.get("ai", {}).get("open_ai", {}).get("model")
    chat_model = merged.get("ai", {}).get("models", {}).get("chat_model")
    edit_model = merged.get("ai", {}).get("models", {}).get("edit_model")
    if not chat_model and not edit_model and openai_model:
        merged_ai_config = cast(dict[Any, Any], merged.get("ai", {}))
        models_config = {
            "models": {
                "chat_model": chat_model or openai_model,
                "edit_model": edit_model or openai_model,
            }
        }
        merged["ai"] = cast(
            AiConfig, deep_merge(merged_ai_config, models_config)
        )

    # Migrate completion.model to ai.models.autocomplete_model
    completion_model = merged.get("completion", {}).get("model")
    autocomplete_model = (
        merged.get("ai", {}).get("models", {}).get("autocomplete_model")
    )
    if completion_model and not autocomplete_model:
        merged_ai_config = cast(dict[Any, Any], merged.get("ai", {}))
        models_config = {
            "models": {
                "autocomplete_model": completion_model,
            }
        }
        merged["ai"] = cast(
            AiConfig, deep_merge(merged_ai_config, models_config)
        )

    return merged
