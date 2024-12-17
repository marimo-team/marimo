# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Callable


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, Callable[..., Any]] = {}

    def register(
        self,
        agent_fn: Callable[..., Any],
        name: str = "default",
    ) -> None:
        self._agents[name] = agent_fn

    def get_agent(
        self,
        name: str = "default",
    ) -> Callable[..., Any]:
        if name not in self._agents:
            raise ValueError(f"Agent name '{name}' is not registered.")
        return self._agents[name]
