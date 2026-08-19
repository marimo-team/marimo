# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from enum import Enum
from typing import TYPE_CHECKING

from marimo._utils.typing import override

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from typing import TypeGuard

    from marimo._config.config import (
        MCPServerConfig,
        MCPServerStdioConfig,
        MCPServerStreamableHttpConfig,
    )
    from marimo._server.ai.mcp.config import MCPServerDefinition
    from mcp.client import Transport
    from mcp.shared._stream_protocols import ReadStream, WriteStream
    from mcp.shared.message import SessionMessage


def _is_stdio_config(
    config: MCPServerConfig,
) -> TypeGuard[MCPServerStdioConfig]:
    return "command" in config


def _is_streamable_http_config(
    config: MCPServerConfig,
) -> TypeGuard[MCPServerStreamableHttpConfig]:
    return "url" in config


class MCPTransportType(str, Enum):
    """Supported MCP transport types."""

    # based on https://modelcontextprotocol.io/docs/concepts/transports
    STDIO = "stdio"
    STREAMABLE_HTTP = "streamable_http"


class MCPTransportConnector(ABC):
    """Abstract base class for MCP transport connectors."""

    @abstractmethod
    def create(self, server_def: MCPServerDefinition) -> Transport:
        """Create a transport for an MCP server.

        Args:
            server_def: Server definition with transport-specific parameters

        Returns:
            A transport managed by the MCP client.
        """


class StdioTransportConnector(MCPTransportConnector):
    """STDIO transport connector for process-based MCP servers."""

    @override
    def create(self, server_def: MCPServerDefinition) -> Transport:
        from mcp import StdioServerParameters
        from mcp.client.stdio import stdio_client

        config = server_def.config
        if not _is_stdio_config(config):
            raise ValueError("STDIO transport requires a command")

        # Set up environment variables for the server process
        env = os.environ.copy()
        env.update(config.get("env") or {})

        # Configure server parameters
        server_params = StdioServerParameters(
            command=config["command"],
            args=config.get("args") or [],
            env=env,
        )

        return stdio_client(server_params)


class StreamableHTTPTransportConnector(MCPTransportConnector):
    """Streamable HTTP transport connector for modern HTTP-based MCP servers."""

    @override
    def create(self, server_def: MCPServerDefinition) -> Transport:
        import httpx2

        from mcp.client.streamable_http import streamable_http_client

        config = server_def.config
        if not _is_streamable_http_config(config):
            raise ValueError("Streamable HTTP transport requires a URL")

        @asynccontextmanager
        async def transport() -> AsyncGenerator[
            tuple[
                ReadStream[SessionMessage | Exception],
                WriteStream[SessionMessage],
            ]
        ]:
            timeout = httpx2.Timeout(server_def.timeout, read=300.0)
            async with httpx2.AsyncClient(
                headers=config.get("headers", {}),
                follow_redirects=True,
                timeout=timeout,
            ) as http_client:
                async with streamable_http_client(
                    config["url"], http_client=http_client
                ) as streams:
                    yield streams

        return transport()


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
