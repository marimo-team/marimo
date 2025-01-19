# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from marimo._runtime.context import get_context


@dataclass
class MCPFunction:
    """A function registered with an MCP server."""

    name: str
    description: str
    func: Callable


class MCPServer:
    """A MCP server that manages tools, resources, and prompts."""

    def __init__(self, name: str):
        """Initialize an MCP server.

        Args:
            name: The name of the server
        """
        self.name = name
        self.tools: Dict[str, MCPFunction] = {}
        self.resources: Dict[str, MCPFunction] = {}
        self.prompts: Dict[str, MCPFunction] = {}

        # Register with current context
        # TODO(mcp): how to get the current runtime context (session view)?
        ctx = get_context()
        if not hasattr(ctx, "mcp_servers"):
            ctx.mcp_servers = {}
        ctx.mcp_servers[name] = self

    def __del__(self):
        """Unregister server when deleted."""
        try:
            ctx = get_context()
            if hasattr(ctx, "mcp_servers") and self.name in ctx.mcp_servers:
                del ctx.mcp_servers[self.name]
        except Exception:
            # Context may not be available during cleanup
            pass

    def _register_function(
        self,
        func: Callable,
        registry: Dict[str, MCPFunction],
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Callable:
        """Register a function with this server.

        Args:
            func: The function to register
            registry: The registry to add the function to (tools, resources, or prompts)
            name: Optional name for the function (defaults to function name)
            description: Optional description (defaults to function docstring)
        """
        actual_name = name or func.__name__
        actual_description = description or inspect.getdoc(func) or ""

        registry[actual_name] = MCPFunction(
            name=actual_name, description=actual_description, func=func
        )
        return func

    def tool(
        self, name: Optional[str] = None, description: Optional[str] = None
    ):
        """Decorator to register a tool."""

        def decorator(func: Callable) -> Callable:
            return self._register_function(func, self.tools, name, description)

        return decorator

    def resource(
        self, name: Optional[str] = None, description: Optional[str] = None
    ):
        """Decorator to register a resource."""

        def decorator(func: Callable) -> Callable:
            return self._register_function(
                func, self.resources, name, description
            )

        return decorator

    def prompt(
        self, name: Optional[str] = None, description: Optional[str] = None
    ):
        """Decorator to register a prompt."""

        def decorator(func: Callable) -> Callable:
            return self._register_function(
                func, self.prompts, name, description
            )

        return decorator

    def add_tool(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        """Add a tool directly."""
        self._register_function(func, self.tools, name, description)

    def add_resource(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        """Add a resource directly."""
        self._register_function(func, self.resources, name, description)

    def add_prompt(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        """Add a prompt directly."""
        self._register_function(func, self.prompts, name, description)

    async def call_tool(self, name: str, **kwargs) -> Any:
        """Call a registered tool."""
        if name not in self.tools:
            raise ValueError(f"Tool {name} not found")
        return await self._maybe_await(self.tools[name].func(**kwargs))

    async def call_resource(self, name: str, **kwargs) -> Any:
        """Call a registered resource."""
        if name not in self.resources:
            raise ValueError(f"Resource {name} not found")
        return await self._maybe_await(self.resources[name].func(**kwargs))

    async def call_prompt(self, name: str, **kwargs) -> Any:
        """Call a registered prompt."""
        if name not in self.prompts:
            raise ValueError(f"Prompt {name} not found")
        return await self._maybe_await(self.prompts[name].func(**kwargs))

    async def execute_tool(self, name: str, **kwargs) -> Any:
        """Execute a tool by name."""
        return await self.call_tool(name, **kwargs)

    async def execute_resource(self, name: str, **kwargs) -> Any:
        """Execute a resource by name."""
        return await self.call_resource(name, **kwargs)

    async def execute_prompt(self, name: str, **kwargs) -> Any:
        """Execute a prompt by name."""
        return await self.call_prompt(name, **kwargs)

    async def evaluate_request(
        self, request_type: str, name: str, args: Dict[str, Any]
    ) -> Any:
        """Evaluate a request based on its type."""
        if request_type == "tool":
            return await self.execute_tool(name, **args)
        elif request_type == "resource":
            return await self.execute_resource(name, **args)
        elif request_type == "prompt":
            return await self.execute_prompt(name, **args)
        else:
            raise ValueError(f"Unknown request type: {request_type}")

    @staticmethod
    async def _maybe_await(result: Any) -> Any:
        """Convert result to awaitable if it isn't already."""
        if inspect.isawaitable(result):
            return await result
        return result
