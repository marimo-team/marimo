# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Union

if TYPE_CHECKING:
    from typing import Protocol, TypedDict

    from anyio.streams.memory import (
        MemoryObjectReceiveStream,
        MemoryObjectSendStream,
    )

    from mcp.shared.message import SessionMessage

    class MCPToolMeta(TypedDict):
        """Metadata that marimo adds to MCP tools."""

        server_name: str
        namespaced_name: str

    class MCPToolWithMeta(Protocol):
        """MCP Tool with marimo-specific metadata."""

        name: str
        description: str | None
        inputSchema: dict[str, Any]
        meta: MCPToolMeta


# Type alias that matches the MCP SDK's CallToolRequestParams.arguments type
MCPToolArgs = Optional[dict[str, Any]]

# Type alias for MCP transport connection streams
TransportConnectorResponse = tuple[
    "MemoryObjectReceiveStream[Union[SessionMessage, Exception]]",
    "MemoryObjectSendStream[SessionMessage]",
]
