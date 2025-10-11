# Model Context Protocol (MCP)

!!! warning "Experimental Feature"
    MCP features are currently experimental and under active development. Features and APIs may change.

marimo supports the Model Context Protocol (MCP) in two ways: as an [MCP server](mcp.md#mcp-server) that exposes marimo's AI tools to external applications, and as an [MCP client](mcp.md#mcp-client) that connects [supported servers](mcp.md#supported-servers) to marimo's [chat panel](ai_completion.md#chat-panel).

## Prerequisites

Both MCP server and client features require the MCP dependencies. Install marimo with MCP support:

/// tab | uv
```bash
# run with uv in a project
uv run --with="marimo[mcp]" marimo edit notebook.py
```
///

/// tab | uvx
```bash
# run with uvx anywhere
uvx "marimo[mcp]" edit notebook.py
```
///

/// tab | pip
```bash
# install with pip and a venv
pip install "marimo[mcp]"
marimo edit notebook.py
```
///

## MCP Server

marimo can expose its [AI tools](tools.md) through an MCP server endpoint, allowing external AI applications to interact with your notebooks.

### Enabling the server

Add the `--mcp` flag when starting marimo:

```bash
marimo edit notebook.py --mcp
```

!!! tip "Development mode"
    Add `--no-token` to disable authentication for local development.

### Available tools

When connected to marimo's MCP server, external applications can access all [AI tools](tools.md).

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

## MCP Client

marimo can connect to external MCP servers to add additional tools and context to the [chat panel](ai_completion.md#chat-panel).

### Supported servers

marimo currently supports the following preset MCP servers:

| Server | Description |
|--------|-------------|
| `marimo` | Access to marimo documentation and examples |
| `context7` | Code search and navigation across your codebase |

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

Once configured, tools from these servers will be automatically available in the [chat panel when using ask mode](ai_completion.md#chat-panel).

!!! info "Custom MCP servers"
    Support for custom MCP server configuration is not yet available.

## Related documentation

- [AI tools](tools.md) - Available tools exposed by the MCP server
- [AI-assisted coding](ai_completion.md#chat-panel) - Using the chat panel with MCP tools
