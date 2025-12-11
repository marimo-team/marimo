# AI tools

!!! warning "Experimental Feature"
    Tools are currently experimental and under active development. Tool definitions and availability may change.

marimo exposes a set of tools that allow AI assistants to interact with your notebooks. These tools enable AI agents to read notebook content, inspect cell runtime data, access variables, handle errors, and more.

## Using tools

These tools are available when using the [chat panel in ask mode](ai_completion.md#chat-panel). External AI applications can also access these tools through the [marimo MCP server](mcp.md#mcp-server).

## Available tools

### Inspection

| Tool | Description |
|------|-------------|
| **get_active_notebooks** | List all currently active marimo notebooks. Returns summary statistics and notebook details including names, paths, and session IDs. Start here to discover which notebooks are available. |
| **get_lightweight_cell_map** | Get an overview of notebook structure showing a preview of each cell. Takes a `session_id` and optional `preview_lines` parameter. Returns cell IDs, preview text, line counts, and cell types (code, markdown, SQL). |
| **get_cell_runtime_data** | Get detailed runtime information for a specific cell. Takes `session_id` and `cell_id` parameters. Returns full cell code, error details, runtime metadata (execution time, runtime state), and variables defined by the cell. |
| **get_cell_outputs** | Get execution output from a specific cell. Takes `session_id` and `cell_id` parameters. Returns visual output (HTML, charts, tables, etc.) with mimetype, stdout messages, and stderr messages. |

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

### Editing (Agent mode only)

!!! note "Availability"
    These tools are only available when using the [chat panel in agent mode](ai_completion.md#chat-panel). They are not exposed through the [MCP server](mcp.md#mcp-server).

| Tool | Description |
|------|-------------|
| **edit_notebook** | Add, remove, or update cells in the notebook. Takes cell operations and modifications as parameters. Allows the AI agent to generate diffs that modify notebook structure and content. |
| **run_stale_cells** | Run cells that are stale (outdated due to upstream changes). Triggers execution of affected cells to update the notebook state. |

## Related documentation

- [Model Context Protocol (MCP)](mcp.md) - Learn how to expose tools through the marimo MCP server
- [AI-assisted coding](ai_completion.md) - Learn about more AI coding features
