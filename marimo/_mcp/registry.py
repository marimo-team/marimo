# Copyright 2024 Marimo. All rights reserved.

from __future__ import annotations

from marimo._mcp.server import MCPServer


# TODO(mcp): implement MCPRegistry
class MCPRegistry:
    def __init__(self):
        self.servers = {}

    def register_server(self, server: MCPServer) -> None:
        self.servers[server.name] = server

    def get_server(self, name: str) -> MCPServer:
        return self.servers[name]
