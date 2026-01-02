# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from typing import Union

    from anyio.streams.memory import (
        MemoryObjectReceiveStream,
        MemoryObjectSendStream,
    )

    from mcp.shared.message import SessionMessage


# Type alias that matches the MCP SDK's CallToolRequestParams.arguments type
MCPToolArgs = Optional[dict[str, Any]]

# Type alias for MCP transport connection streams
TransportConnectorResponse = tuple[
    "MemoryObjectReceiveStream[Union[SessionMessage, Exception]]",
    "MemoryObjectSendStream[SessionMessage]",
]
