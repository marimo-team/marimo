# Model Context Protocol (MCP)

!!! warning "Experimental Feature"
    MCP features are currently experimental and under active development. Features and APIs may change.

marimo supports the Model Context Protocol (MCP) in two ways: as an [MCP server](mcp.md#mcp-server) that exposes marimo's AI tools to external applications, and as an [MCP client](mcp.md#mcp-client) that connects [supported servers](mcp.md#supported-servers) to marimo's [chat panel](ai_completion.md#chat-panel).

## Prerequisites

Both MCP server and client features require the MCP dependencies. Run marimo with MCP support using one of the following methods:

/// tab | uv
```bash
# run with uv in a project
uv run --with="marimo[mcp]" marimo edit notebook.py --mcp --no-token
```
///

/// tab | uvx
```bash
# run with uvx anywhere
uvx "marimo[mcp]" edit notebook.py --mcp --no-token
```
///

/// tab | pip
```bash
# install with pip and a venv
pip install "marimo[mcp]"
marimo edit notebook.py --mcp --no-token
```
///

!!! note "Flags"
    The `--mcp` flag exposes an endpoint that provides access to your notebook data via the MCP server endpoint. Remove `--mcp` if you only want MCP Client features. The `--no-token` flag removes authentication, which should only be used for local development. Remove `--no-token` in production environments.

## MCP Server

marimo can expose its AI tools through an MCP server endpoint, allowing
external AI applications to interact with your notebooks. If your goal is to
have a coding agent manipulate a running notebook, see [marimo
pair](../generate_with_ai/marimo_pair.md) instead.

<video autoplay loop muted playsinline width="100%" height="100%" align="center">
  <source src="/_static/docs-mcp-server.mp4" type="video/mp4">
</video>

### Available tools

When connected to marimo's MCP server, external applications can access the following categories of tools.

#### Inspection

| Tool | Description |
|------|-------------|
| **get_active_notebooks** | List all currently active marimo notebooks. Returns summary statistics and notebook details including names, paths, and session IDs. Start here to discover which notebooks are available. |
| **get_lightweight_cell_map** | Get an overview of notebook structure showing a preview of each cell. Takes a `session_id` and optional `preview_lines` parameter. Returns cell IDs, preview text, line counts, cell types (code, markdown, SQL), runtime state (`idle`, `running`, `queued`, etc.), and `has_output`/`has_console_output` flags. |
| **get_cell_runtime_data** | Get detailed runtime information for one or more cells. Takes `session_id` and `cell_ids` (list) parameters. Returns full cell code, error details, runtime metadata (execution time, runtime state), and variables defined by each cell. |
| **get_cell_outputs** | Get execution output from one or more cells. Takes `session_id` and `cell_ids` (list) parameters. Returns visual output (HTML, charts, tables, etc.) with mimetype, stdout messages, and stderr messages for each cell. |
| **get_cell_dependency_graph** | Get the cell dependency graph showing variable ownership and cell relationships. Takes `session_id` and optional `cell_id` and `depth` parameters. Returns cell dependency info (defined variables with kind and runtime type, referenced variables, parent/child cells), a variable ownership map, multiply-defined variables, and cycle information. Use `cell_id` to center on a specific cell and `depth` to limit traversal hops. |

#### Data

| Tool | Description |
|------|-------------|
| **get_tables_and_variables** | Get information about variables and data tables in a session. Takes `session_id` and `variable_names` parameters (empty list returns all). Returns table metadata (columns, primary keys, indexes, row counts) and variable values with data types. |
| **get_database_tables** | Get database schema information with optional query filtering. Takes `session_id` and optional `query` parameter (supports regex). Returns tables with connection name, database, schema, and table details. |

#### Debugging

| Tool | Description |
|------|-------------|
| **get_notebook_errors** | Get all errors in the notebook organized by cell. Takes `session_id` parameter. Returns error summary (total errors, affected cells) and per-cell error details (type, message, traceback). |
| **lint_notebook** | Get all marimo lint errors in the notebook. Takes a `session_id` parameter. Returns lint errors as defined in the [lint rules documentation](../lint_rules/index.md). |

#### Reference

| Tool | Description |
|------|-------------|
| **get_marimo_rules** | Returns marimo's rules and best practices for AI assistants. |

### Available prompts

When connected to marimo's MCP server, external applications can access the following prompts:

| Prompt | Description |
|--------|-------------|
| **active_notebooks** | Get current active notebooks and their session IDs and file paths. Returns session IDs and file paths for all active marimo notebook sessions, along with guidance on using these IDs with marimo MCP tools. |
| **errors_summary** | Get error summaries for all active notebooks. Returns a summary of all errors across active notebooks organized by notebook and cell, including error types, messages, and affected cell IDs. |

### Connecting external applications

marimo's MCP server works with any MCP-compatible application. Below are setup instructions for some commonly used applications:

!!! tip "Connection details"
    Replace `PORT` with your marimo server port in the examples below. If authentication is enabled, append `?access_token=YOUR_TOKEN` to the URL and replace `YOUR_TOKEN` with your marimo access token.

#### Claude Code

Use Claude Code's CLI to connect to marimo:

```bash
claude mcp add --transport http marimo http://localhost:PORT/mcp/server
```

#### Cursor

Configure Cursor to connect to marimo's MCP server:

```json
{
  "mcpServers": {
    "marimo": {
      "url": "http://localhost:PORT/mcp/server"
    }
  }
}
```

#### VS Code

Create a .vscode/mcp.json file in your workspace and configure it to connect to marimo's MCP server:

```json
{
  "servers": {
    "marimo": {
      "type": "http",
      "url": "http://localhost:PORT/mcp/server"
    }
  }
}
```

### DNS rebinding protection

marimo's MCP server enables DNS rebinding protection by default, which validates the `Host` header on incoming requests. This is common when using proxies, gateways (e.g., ECS), CDNs (Cloudflare), or custom domains, where the forwarded `Host` header won't match the expected local host, causing `421 Misdirected Request` or `Invalid Host Header` errors. Pass `--mcp-allow-remote` to disable this check:

```bash
marimo edit notebook.py --mcp --mcp-allow-remote
```

## MCP Client

marimo can connect to external MCP servers to add additional tools and context to the [chat panel](ai_completion.md#chat-panel).

### Supported servers

marimo currently supports the following MCP servers:

| Server | Description |
|--------|-------------|
| `marimo` | Provides marimo's official documentation, API reference, and code examples |
| `context7` | Fetches up-to-date, version-specific documentation and code examples from official sources |


Support for custom MCP server configuration is not yet available.

### Configuration

Enable MCP client servers through the marimo settings UI:

<div align="center">
<figure>
<img src="/_static/docs-mcp-client-settings.png" width="740px"/>
<figcaption>Enable MCP servers in the AI settings panel.</figcaption>
</figure>
</div>

Alternatively, configure MCP servers in your marimo configuration file:

```toml title="marimo.toml"
[mcp]
presets = ["marimo", "context7"]
```

Configured servers provide tools to the [chat panel](ai_completion.md#chat-panel)
with **Read only** or **Suggest edits** access. These access levels restrict
marimo's built-in notebook tools. They do not restrict what connected MCP tools
can do.
