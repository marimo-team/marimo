# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, TypeVar

from marimo._messaging.ops import MCPEvaluationResult
from marimo._runtime.requests import MCPEvaluationRequest

T = TypeVar("T")


@dataclass
class MCPFunction:
    """A function registered with an MCP server.

    Attributes:
        name: The name of the function
        description: A description of what the function does
        func: The actual function to call
        schema: Optional JSON schema for function parameters
    """

    name: str
    description: str
    func: Callable
    schema: Optional[Dict[str, Any]] = None


@dataclass
class MCPServer:
    """A Marimo Control Protocol server that manages tools, resources, and prompts.

    The MCP server provides a way to register and execute functions that can be called
    from the frontend. Functions are categorized into:
    - tools: Functions that perform actions
    - resources: Functions that provide data
    - prompts: Functions that generate text/prompts
    """

    name: str
    tools: Dict[str, MCPFunction] = field(default_factory=dict)
    resources: Dict[str, MCPFunction] = field(default_factory=dict)
    prompts: Dict[str, MCPFunction] = field(default_factory=dict)

    def _register_function(
        self,
        func: Callable[..., T],
        registry: Dict[str, MCPFunction],
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Callable[..., T]:
        """Register a function with this server.

        Args:
            func: The function to register
            registry: The registry to add the function to (tools, resources, or prompts)
            name: Optional name for the function (defaults to function name)
            description: Optional description (defaults to function docstring)

        Returns:
            The original function (allowing use as a decorator)
        """
        actual_name = name or func.__name__
        actual_description = description or inspect.getdoc(func) or ""

        registry[actual_name] = MCPFunction(
            name=actual_name,
            description=actual_description,
            func=func,
        )
        return func

    def tool(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Callable[[Callable[..., T]], Callable[..., T]]:
        """Decorator to register a tool.

        Args:
            name: Optional name for the tool (defaults to function name)
            description: Optional description (defaults to function docstring)
        """

        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            return self._register_function(func, self.tools, name, description)

        return decorator

    def resource(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Callable[[Callable[..., T]], Callable[..., T]]:
        """Decorator to register a resource.

        Args:
            name: Optional name for the resource (defaults to function name)
            description: Optional description (defaults to function docstring)
        """

        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            return self._register_function(
                func, self.resources, name, description
            )

        return decorator

    def prompt(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Callable[[Callable[..., T]], Callable[..., T]]:
        """Decorator to register a prompt.

        Args:
            name: Optional name for the prompt (defaults to function name)
            description: Optional description (defaults to function docstring)
        """

        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            return self._register_function(
                func, self.prompts, name, description
            )

        return decorator

    async def evaluate_request(
        self,
        request: MCPEvaluationRequest,
    ) -> MCPEvaluationResult:
        """Evaluate a request based on its type.

        Args:
            request: The request to evaluate

        Returns:
            MCPEvaluationResult containing the result or error

        Raises:
            ValueError: If request is invalid or function not found
        """
        try:
            registry = {
                "tool": self.tools,
                "resource": self.resources,
                "prompt": self.prompts,
            }[request.request_type]
        except KeyError:
            raise ValueError(
                f"Unknown request type: {request.request_type}"
            ) from None

        if request.name not in registry:
            raise ValueError(
                f"{request.request_type.capitalize()} '{request.name}' not found"
            )

        try:
            func = registry[request.name].func
            result = await self._maybe_await(func(**request.args))
            return MCPEvaluationResult(
                mcp_evaluation_id=request.mcp_evaluation_id,
                result=result,
            )
        except Exception:
            # TODO(mcp): Add error handling
            return MCPEvaluationResult(
                mcp_evaluation_id=request.mcp_evaluation_id,
                result=None,
            )

    @staticmethod
    async def _maybe_await(result: Any) -> Any:
        """Convert result to awaitable if it isn't already."""
        if inspect.isawaitable(result):
            return await result
        return result
