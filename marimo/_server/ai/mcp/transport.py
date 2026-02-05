# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from contextlib import AsyncExitStack

    from marimo._config.config import (
        MCPServerStdioConfig,
        MCPServerStreamableHttpConfig,
    )
    from marimo._server.ai.mcp.config import MCPServerDefinition
    from marimo._server.ai.mcp.types import TransportConnectorResponse


class MCPTransportType(str, Enum):
    """Supported MCP transport types."""

    # based on https://modelcontextprotocol.io/docs/concepts/transports
    STDIO = "stdio"
    STREAMABLE_HTTP = "streamable_http"


class MCPTransportConnector(ABC):
    """Abstract base class for MCP transport connectors."""

    @abstractmethod
    async def connect(
        self, server_def: MCPServerDefinition, exit_stack: AsyncExitStack
    ) -> TransportConnectorResponse:
        """Connect to the MCP server and return read/write streams.

        Args:
            server_def: Server definition with transport-specific parameters
            exit_stack: Async exit stack for resource management

        Returns:
            Tuple of (read_stream, write_stream) for the ClientSession
        """
        pass


class StdioTransportConnector(MCPTransportConnector):
    """STDIO transport connector for process-based MCP servers."""

    async def connect(
        self, server_def: MCPServerDefinition, exit_stack: AsyncExitStack
    ) -> TransportConnectorResponse:
        # Import MCP SDK components for stdio transport
        from mcp import StdioServerParameters
        from mcp.client.stdio import stdio_client

        # Type narrowing for mypy
        assert "command" in server_def.config
        config = cast("MCPServerStdioConfig", server_def.config)

        # Set up environment variables for the server process
        env = os.environ.copy()
        env.update(config.get("env") or {})

        # Configure server parameters
        server_params = StdioServerParameters(
            command=config["command"],
            args=config.get("args") or [],
            env=env,
        )

        # Establish connection with proper resource management
        read, write, *_ = await exit_stack.enter_async_context(
            stdio_client(server_params)
        )

        return read, write


class StreamableHTTPTransportConnector(MCPTransportConnector):
    """Streamable HTTP transport connector for modern HTTP-based MCP servers."""

    async def connect(
        self, server_def: MCPServerDefinition, exit_stack: AsyncExitStack
    ) -> TransportConnectorResponse:
        # Import MCP SDK components for streamable HTTP transport
        from mcp.client.streamable_http import streamablehttp_client

        # Type narrowing for mypy
        assert "url" in server_def.config
        config = cast("MCPServerStreamableHttpConfig", server_def.config)

        # Establish streamable HTTP connection
        read, write, *_ = await exit_stack.enter_async_context(
            streamablehttp_client(
                config["url"],
                headers=config.get("headers", {}),
                timeout=server_def.timeout,
            )
        )

        return read, write


class MCPTransportRegistry:
    """Registry for MCP transport connectors."""

    def __init__(self) -> None:
        self._connectors: dict[MCPTransportType, MCPTransportConnector] = {
            MCPTransportType.STDIO: StdioTransportConnector(),
            MCPTransportType.STREAMABLE_HTTP: StreamableHTTPTransportConnector(),
        }

    def get_connector(
        self, transport_type: MCPTransportType
    ) -> MCPTransportConnector:
        """Get the appropriate transport connector for the given transport type.

        Args:
            transport_type: The type of transport to connect with

        Returns:
            Transport connector instance

        Raises:
            ValueError: If transport type is not supported
        """
        if transport_type not in self._connectors:
            raise ValueError(f"Unsupported transport type: {transport_type}")
        return self._connectors[transport_type]
