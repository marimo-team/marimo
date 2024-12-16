# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Callable


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, Callable] = {}

    def register(
        self,
        agent_fn: Callable,
        name: str = "default",
    ) -> None:
        self._agents[name] = agent_fn

    def get_agent(
        self,
        name: str = "default",
    ) -> Callable:
        if name not in self._agents:
            raise ValueError(f"Agent name '{name}' is not registered.")
        return self._agents[name]
