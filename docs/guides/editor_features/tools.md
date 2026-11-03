# AI tools

!!! warning "Experimental Feature"
    Tools are currently experimental and under active development. Tool definitions and availability may change.

marimo exposes a set of tools that allow AI assistants to interact with your notebooks. These tools enable AI agents to read notebook content, inspect cell runtime data, access variables, handle errors, and more.

## Using tools

Tool availability depends on the [notebook access level](ai_completion.md#chat-panel) you choose in the chat panel:

| Notebook access | Marimo notebook tools |
|-----------------|-----------------------|
| **Read only** | Read-only inspection, data, debugging, and reference tools |
| **Suggest edits** | All **Read only** notebook tools plus cell proposals for review |
| **Full access** | Python execution in the live kernel and on-demand reference guides (see below) |

**Read only** and **Suggest edits** also enable tools from connected MCP servers. These
access levels apply to marimo's built-in notebook tools; they do not restrict
what connected MCP tools can do. Manage external tools in your
[MCP client configuration](mcp.md#mcp-client).

External AI applications can also access the inspection, data, debugging, and
reference tools through the [marimo MCP server](mcp.md#mcp-server).

## Available tools

### Inspection

| Tool | Description |
|------|-------------|
| **get_active_notebooks** | List all currently active marimo notebooks. Returns summary statistics and notebook details including names, paths, and session IDs. Start here to discover which notebooks are available. |
| **get_lightweight_cell_map** | Get an overview of notebook structure showing a preview of each cell. Takes a `session_id` and optional `preview_lines` parameter. Returns cell IDs, preview text, line counts, cell types (code, markdown, SQL), runtime state (`idle`, `running`, `queued`, etc.), and `has_output`/`has_console_output` flags. |
| **get_cell_runtime_data** | Get detailed runtime information for one or more cells. Takes `session_id` and `cell_ids` (list) parameters. Returns full cell code, error details, runtime metadata (execution time, runtime state), and variables defined by each cell. |
| **get_cell_outputs** | Get execution output from one or more cells. Takes `session_id` and `cell_ids` (list) parameters. Returns visual output (HTML, charts, tables, etc.) with mimetype, stdout messages, and stderr messages for each cell. |
| **get_cell_dependency_graph** | Get the cell dependency graph showing variable ownership and cell relationships. Takes `session_id` and optional `cell_id` and `depth` parameters. Returns cell dependency info (defined variables with kind and runtime type, referenced variables, parent/child cells), a variable ownership map, multiply-defined variables, and cycle information. Use `cell_id` to center on a specific cell and `depth` to limit traversal hops. |

### Data

| Tool | Description |
|------|-------------|
| **get_tables_and_variables** | Get information about variables and data tables in a session. Takes `session_id` and `variable_names` parameters (empty list returns all). Returns table metadata (columns, primary keys, indexes, row counts) and variable values with data types. |
| **get_database_tables** | Get database schema information with optional query filtering. Takes `session_id` and optional `query` parameter (supports regex). Returns tables with connection name, database, schema, and table details. |

### Debugging

| Tool | Description |
|------|-------------|
| **get_notebook_errors** | Get all errors in the notebook organized by cell. Takes `session_id` parameter. Returns error summary (total errors, affected cells) and per-cell error details (type, message, traceback). |
| **lint_notebook** | Get all marimo lint errors in the notebook. Returns lint errors as defined in the [lint rules documentation](../lint_rules/index.md). |

### Reference

| Tool | Description |
|------|-------------|
| **get_marimo_rules** | Get official marimo guidelines and best practices for AI assistants. Returns the content of the marimo rules file and source URL for understanding marimo-specific conventions. |

<span id="editing-agent-mode-only"></span>

### Editing

!!! note "Availability"
    These tools are only available when using the [chat panel with **Suggest edits** access](ai_completion.md#chat-panel). They are not exposed through the [MCP server](mcp.md#mcp-server).

| Tool | Description |
|------|-------------|
| **edit_notebook** | Propose adding, removing, or updating cells. Changes appear in the notebook for the user to keep or discard. This tool does not run cells. |

## Web search and fetch

At any notebook access level, the chat panel's **Capabilities** menu lets you enable web search and URL fetching. These are [provider-adaptive capabilities](https://pydantic.dev/docs/ai/core-concepts/capabilities/#provider-adaptive-tools) from [Pydantic AI](https://ai.pydantic.dev): marimo enables them automatically based on your installed packages and the model you are using.

### How capabilities are enabled

marimo picks the best available option for each capability:

| Capability | Local fallback (installed in your environment) | Native (model provider supports it) |
|------------|-----------------------------------------------|-------------------------------------|
| **Web search** | DuckDuckGo search when `ddgs` is installed | Provider-native web search (e.g. Anthropic, OpenAI Responses) |
| **Web fetch** | URL fetching via `markdownify` when installed | Provider-native web fetch |
| **X search** | — | xAI models with native X search support |

Local fallbacks take priority when their packages are installed. Otherwise, marimo uses the provider's native tools when your configured model supports them.

### Install local web search and fetch

To enable web search and fetch on any model — including local models via Ollama — install the optional Pydantic AI extras:

```bash
pip install "pydantic-ai-slim[duckduckgo,web-fetch]"
```

### Use provider-native tools

When local packages are not installed, marimo enables native tools only if your model supports them. For example:

- **Anthropic** and **OpenAI Responses** models can use native web search and web fetch
- **xAI** models (e.g. `xai/grok-2-latest`) can use native web search and X search

Configure xAI in your `marimo.toml` or through the notebook settings — see the [xAI provider guide](../configuration/llm_providers.md#xai).


<span id="code-mode"></span>

## Full access

!!! warning "Full access"
    The assistant can execute Python in your live notebook kernel and make
    destructive changes to notebook cells and runtime state without review.

Select **Full access** from the chat panel's **Notebook access** selector. Instead of the inspection and editing tools above, the assistant uses a different toolset oriented around running Python in the live kernel:

| Tool / capability | Description |
|-------------------|-------------|
| **execute_code** | Run Python in the notebook kernel's scratchpad. The assistant uses this for all notebook mutations — adding cells, updating code, inspecting variables, and running logic. |
| **gotchas** | On-demand reference for name redefinition, cached module proxies, and other notebook traps. |
| **notebook-improvements** | On-demand reference for improving, optimizing, or cleaning up an existing notebook. |
| **rich-representations** | On-demand reference for custom widgets, visual encodings, and interactive output. |

Full access loads the [marimo pair](../generate_with_ai/marimo_pair.md) skill as its system prompt, so the assistant follows the same conventions as external agent CLIs paired on your notebook.


## Related documentation

- [Model Context Protocol (MCP)](mcp.md) - Learn how to expose tools through the marimo MCP server
- [AI-assisted coding](ai_completion.md) - Learn about more AI coding features
