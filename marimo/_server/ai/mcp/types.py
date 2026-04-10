# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from anyio.streams.memory import (
        MemoryObjectReceiveStream,
        MemoryObjectSendStream,
    )

    from mcp.shared.message import SessionMessage


# Type alias that matches the MCP SDK's CallToolRequestParams.arguments type
MCPToolArgs = dict[str, Any] | None

# Type alias for MCP transport connection streams
TransportConnectorResponse = tuple[
    "MemoryObjectReceiveStream[SessionMessage | Exception]",
    "MemoryObjectSendStream[SessionMessage]",
]
