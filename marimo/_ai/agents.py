# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Callable

from marimo._output.rich_help import mddoc
from marimo._runtime.context import ContextNotInitializedError, get_context


@mddoc
def register_agent(run_fn: Callable[..., Any], name: str = "default") -> None:
    """Register an LLM agent."""
    try:
        _registry = get_context().agent_registry
        _registry.register(run_fn, name)
    except ContextNotInitializedError:
        # Registration may be picked up later, but there is nothing to do
        # at this point.
        pass


@mddoc
async def run_agent(prompt: str, name: str = "default") -> Any:
    """
    Run an LLM agent.
    """
    try:
        _registry = get_context().agent_registry
        agent_fn = _registry.get_agent(name)
        return agent_fn(prompt)
    except ContextNotInitializedError:
        pass
