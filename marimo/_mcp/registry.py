# Copyright 2024 Marimo. All rights reserved.

from __future__ import annotations

from typing import Dict, List

from marimo._mcp.server import MCPServer


class MCPRegistry:
    """Registry for MCP servers.

    The registry maintains a collection of MCP servers and provides methods to
    register and retrieve them. Each server must have a unique name.
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._servers: Dict[str, MCPServer] = {}

    def register_server(self, server: MCPServer) -> None:
        """Register a server with the registry.

        Args:
            server: The server to register.
        """
        self._servers[server.name] = server

    def get_server(self, name: str) -> MCPServer | None:
        """Get a server by name.

        Args:
            name: The name of the server to retrieve.

        Returns:
            The server if found, None otherwise.
        """
        return self._servers.get(name)

    def list_servers(self) -> List[Dict[str, List[Dict[str, str]]]]:
        """List all registered servers and their functions.

        Returns:
            A list of dictionaries containing server information, where each dictionary
            contains the server name and lists of its tools, resources, and prompts.
            Each function entry includes the function name and description.
        """
        servers = []
        for server in self._servers.values():
            server_info = {
                "name": server.name,
                "tools": [
                    {"name": name, "description": fn.description}
                    for name, fn in server.tools.items()
                ],
                "resources": [
                    {"name": name, "description": fn.description}
                    for name, fn in server.resources.items()
                ],
                "prompts": [
                    {"name": name, "description": fn.description}
                    for name, fn in server.prompts.items()
                ],
            }
            servers.append(server_info)
        return servers

    def remove_server(self, name: str) -> None:
        """Remove a server from the registry.

        Args:
            name: The name of the server to remove.
        """
        if name in self._servers:
            del self._servers[name]

    def clear(self) -> None:
        """Remove all servers from the registry."""
        self._servers.clear()


# Global registry instance
registry = MCPRegistry()
