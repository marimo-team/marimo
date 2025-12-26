# Copyright 2026 Marimo. All rights reserved.
"""MCP (Model Context Protocol) client implementation for marimo."""

from __future__ import annotations

from marimo._server.ai.mcp.client import (
    MCPClient,
    MCPServerConnection,
    MCPServerStatus,
    get_mcp_client,
)
from marimo._server.ai.mcp.config import (
    MCP_PRESETS,
    MCPConfigComparator,
    MCPConfigDiff,
    MCPServerDefinition,
    MCPServerDefinitionFactory,
    append_presets,
)
from marimo._server.ai.mcp.transport import (
    MCPTransportConnector,
    MCPTransportRegistry,
    MCPTransportType,
    StdioTransportConnector,
    StreamableHTTPTransportConnector,
)
from marimo._server.ai.mcp.types import MCPToolArgs

__all__ = [
    # Client classes
    "MCPClient",
    "MCPServerConnection",
    "MCPServerStatus",
    "get_mcp_client",
    # Config classes
    "MCP_PRESETS",
    "MCPConfigComparator",
    "MCPConfigDiff",
    "MCPServerDefinition",
    "MCPServerDefinitionFactory",
    "append_presets",
    # Transport classes
    "MCPTransportConnector",
    "MCPTransportRegistry",
    "MCPTransportType",
    "StdioTransportConnector",
    "StreamableHTTPTransportConnector",
    # Types
    "MCPToolArgs",
]
